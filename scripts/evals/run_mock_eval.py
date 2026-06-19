#!/usr/bin/env python3
"""Run a deterministic mock/tiny-model evaluation over an eval config (unit U-I4).

This is the evaluation *hook* that exercises the full scoring path without any
real model inference. It reuses :func:`run_smoke_eval.load_json_compatible_yaml`
and :func:`run_smoke_eval.validate_config` to load and validate the eval config
(default ``configs/evals/smoke.yaml``), then runs a deterministic mock model and
a deterministic trivial metric over every task, emitting a JSON report.

The mock model is a pure, canned transform of the prompt -- it performs NO real
inference -- so every scored field in the report is fully reproducible. Only an
optional ``created_at`` timestamp is non-deterministic, and it is excluded from
the scored content by construction.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "evals"))

import run_smoke_eval as SMOKE  # noqa: E402

DEFAULT_CONFIG = ROOT / "configs" / "evals" / "smoke.yaml"
MOCK_MODEL_ID = "mock-deterministic-v1"


def _rel(path: Path) -> str:
    """Return ``path`` repo-relative, falling back to the basename if outside ROOT."""
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return resolved.name


def current_commit() -> str:
    """Return the current git commit sha, or ``"unknown"`` if unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"
    return result.stdout.strip()


def mock_model(prompt: str) -> str:
    """Deterministically transform ``prompt`` into a canned "answer".

    No real inference happens here. The transform is a pure function of the
    input string: a fixed prefix plus the normalized (whitespace-collapsed)
    prompt. Identical prompts always yield identical outputs, which is what the
    determinism property relies on. An all-whitespace or empty prompt collapses
    to an empty body, which the trivial metric then scores as not-passed.
    """
    collapsed = " ".join(prompt.split())
    if not collapsed:
        return ""
    return f"[mock] {collapsed}"


def score_task(task: dict[str, Any]) -> dict[str, Any]:
    """Run the mock model over one task and score it with the trivial metric."""
    output = mock_model(task["prompt"])
    passed = bool(output.strip())
    return {
        "id": task["id"],
        "area": task["area"],
        "type": task["type"],
        "output_len": len(output),
        "passed": passed,
    }


def build_report(
    config: dict[str, Any],
    config_path: Path,
    *,
    commit_sha: str | None = None,
) -> dict[str, Any]:
    """Build the deterministic mock-eval report for ``config``.

    Every field returned here is a deterministic function of ``config``,
    ``config_path``, and ``commit_sha`` -- there is no timestamp, so the whole
    report (not just the scored content) is reproducible. ``commit_sha`` is a
    seam for tests; when omitted it is read from git.
    """
    tasks = config["tasks"]
    scored = [score_task(task) for task in tasks]
    passed = sum(1 for entry in scored if entry["passed"])
    return {
        "eval_id": config["eval_id"],
        "version": config["version"],
        "config_path": _rel(config_path),
        "model_id": MOCK_MODEL_ID,
        "commit_sha": current_commit() if commit_sha is None else commit_sha,
        "tasks": scored,
        "summary": {
            "task_count": len(scored),
            "passed": passed,
            "status": "mock_scored",
        },
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", nargs="?", default=str(DEFAULT_CONFIG))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv[1:])

    config_path = Path(args.config)
    config = SMOKE.load_json_compatible_yaml(config_path)
    errors = SMOKE.validate_config(config)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1

    report = build_report(config, config_path)
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(output + "\n", encoding="utf-8")
        print(f"wrote mock eval report: {_rel(args.output)}")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
