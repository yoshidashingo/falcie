#!/usr/bin/env python3
"""Scored evaluation harness for fal'Cie (unit U-E2).

Runs a *predictor* over a scored task suite and aggregates accuracy overall and
by area/language, producing a versioned report in the shape `evaluation-plan.md`
asks for. Dependency-free; reuses the metrics in ``metrics.py``.

A **predictor** is ``Callable[[dict], str]`` — given a task it returns the model's
answer string. Real models plug in here later; the built-in reference predictors
(`gold`, `empty`, `echo`) let the harness be validated *without* a model: `gold`
must score 1.0 and `empty` must score 0.0, which proves the scoring path is wired
correctly.

A scored suite is JSONL, one task per line:
    {"id","area","language","prompt","answer","metric"[,"choices"]}
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import metrics as M  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
HARNESS_VERSION = "1.0"
REQUIRED_FIELDS = {"id", "area", "language", "prompt", "answer", "metric"}

Predictor = Callable[[dict[str, Any]], str]


def _rel(path: Path) -> str:
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return resolved.name


def current_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
            capture_output=True, text=True,
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def load_suite(path: Path) -> list[dict[str, Any]]:
    """Load and validate a scored JSONL suite. Raises ValueError on a bad task."""
    tasks: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            task = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
        missing = REQUIRED_FIELDS - task.keys()
        if missing:
            raise ValueError(f"{path}:{line_no}: missing fields: {sorted(missing)}")
        if task["metric"] not in M.METRICS:
            raise ValueError(f"{path}:{line_no}: unknown metric {task['metric']!r}")
        if not str(task["answer"]).strip():
            # Keeps the empty-predictor invariant structural: no task can be passed
            # by an empty answer (which would weaken the empty->0.0 gate).
            raise ValueError(f"{path}:{line_no}: answer must be a non-empty string")
        if task["metric"] == "multiple_choice":
            choices = task.get("choices")
            if not isinstance(choices, list) or not choices:
                raise ValueError(f"{path}:{line_no}: multiple_choice needs a non-empty 'choices' list")
            if str(task["answer"]).strip() not in {str(c).strip() for c in choices}:
                raise ValueError(f"{path}:{line_no}: answer {task['answer']!r} not in choices {choices}")
        if task["id"] in seen:
            raise ValueError(f"{path}:{line_no}: duplicate id {task['id']!r}")
        seen.add(task["id"])
        tasks.append(task)
    if not tasks:
        raise ValueError(f"{path}: no tasks found")
    return tasks


# -- reference predictors (no model required) -------------------------------

def gold_predictor(task: dict[str, Any]) -> str:
    """Returns the correct answer — the harness must score this 1.0."""
    return str(task["answer"])


def empty_predictor(task: dict[str, Any]) -> str:
    """Returns nothing — the harness must score this 0.0."""
    return ""


def echo_predictor(task: dict[str, Any]) -> str:
    """Returns the prompt — a non-trivial wrong baseline."""
    return str(task["prompt"])


REFERENCE_PREDICTORS: dict[str, Predictor] = {
    "gold": gold_predictor,
    "empty": empty_predictor,
    "echo": echo_predictor,
}


# -- scoring ----------------------------------------------------------------

def _acc(passed: int, total: int) -> float:
    return round(passed / total, 4) if total else 0.0


def run_suite(
    tasks: list[dict[str, Any]],
    predictor: Predictor,
    model_id: str,
    suite_path: Path,
    *,
    commit_sha: str | None = None,
) -> dict[str, Any]:
    """Run ``predictor`` over ``tasks`` and aggregate a scored report."""
    per_task: list[dict[str, Any]] = []
    by_area: dict[str, list[int]] = defaultdict(lambda: [0, 0])      # [passed, total]
    by_language: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    passed_total = 0

    for task in tasks:
        prediction = predictor(task)
        passed = M.score(task["metric"], prediction, str(task["answer"]), task)
        passed_total += int(passed)
        by_area[task["area"]][0] += int(passed)
        by_area[task["area"]][1] += 1
        by_language[task["language"]][0] += int(passed)
        by_language[task["language"]][1] += 1
        per_task.append({
            "id": task["id"], "area": task["area"], "language": task["language"],
            "metric": task["metric"], "passed": passed,
            "prediction": prediction[:120],
        })

    return {
        "harness_version": HARNESS_VERSION,
        "suite": _rel(suite_path),
        "model_id": model_id,
        "commit_sha": current_commit() if commit_sha is None else commit_sha,
        "summary": {
            "task_count": len(tasks),
            "passed": passed_total,
            "accuracy": _acc(passed_total, len(tasks)),
        },
        "by_area": {a: {"passed": p, "total": t, "accuracy": _acc(p, t)}
                    for a, (p, t) in sorted(by_area.items())},
        "by_language": {l: {"passed": p, "total": t, "accuracy": _acc(p, t)}
                        for l, (p, t) in sorted(by_language.items())},
        "known_failures": [e["id"] for e in per_task if not e["passed"]],
        "tasks": per_task,
    }


def render_markdown(report: dict[str, Any]) -> str:
    L: list[str] = []
    L.append("# Evaluation Report")
    L.append("")
    L.append(f"- harness_version: `{report['harness_version']}`")
    L.append(f"- suite: `{report['suite']}`")
    L.append(f"- model_id: `{report['model_id']}`")
    L.append(f"- commit: `{report['commit_sha']}`")
    s = report["summary"]
    L.append(f"- **accuracy: {s['accuracy']}** ({s['passed']}/{s['task_count']})")
    L.append("")
    L.append("## By area")
    L.append("")
    L.append("| area | accuracy | passed/total |")
    L.append("| --- | ---: | ---: |")
    for area, v in report["by_area"].items():
        L.append(f"| {area} | {v['accuracy']} | {v['passed']}/{v['total']} |")
    L.append("")
    L.append("## By language")
    L.append("")
    L.append("| language | accuracy | passed/total |")
    L.append("| --- | ---: | ---: |")
    for lang, v in report["by_language"].items():
        L.append(f"| {lang} | {v['accuracy']} | {v['passed']}/{v['total']} |")
    L.append("")
    if report["known_failures"]:
        L.append(f"## Known failures\n\n{', '.join(report['known_failures'])}\n")
    return "\n".join(L) + "\n"
