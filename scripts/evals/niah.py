#!/usr/bin/env python3
"""Needle-in-a-haystack (NIAH) long-context retrieval eval (fal'Cie L-008).

Long-context capability must be validated before claiming it (roadmap; `m2-plan.md`;
ADR-004 gates context extension on needle-in-a-haystack). This synthesizes NIAH
tasks — a unique "needle" fact embedded in filler text at a chosen depth, with a
retrieval question — and scores a predictor across a **length x depth grid**,
producing a retrieval matrix. Dependency-free; deterministic (no RNG).

A predictor is ``Callable[[task], str]`` (same shape as the scored harness). The
built-in reference predictors validate the eval **without a model**:
  * ``gold`` retrieves every needle -> accuracy 1.0
  * ``empty`` retrieves none -> 0.0
  * ``window:<N>`` is a prefix-window stand-in: it "sees" only the first N chars, so
    it retrieves short/shallow needles and misses long/deep ones — proving the matrix
    has real length x depth structure, not a flat result.

    python3 scripts/evals/niah.py --predictor gold --assert-accuracy 1.0
    python3 scripts/evals/niah.py --predictor window --window 1500 --format md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any
from collections.abc import Callable

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import metrics as M  # noqa: E402

DEFAULT_LENGTHS = [200, 1000, 4000]
DEFAULT_DEPTHS = [0.0, 0.25, 0.5, 0.75, 1.0]

# Neutral filler (no incidental needles); cycled to reach a target length.
FILLER = [
    "The archive contains routine maintenance logs from the facility.",
    "Daily status reports were filed on schedule without incident.",
    "倉庫の在庫は定期的に点検され記録されている。",
    "Shipments were processed and the manifests were reconciled.",
    "会議の議事録は共有フォルダに保管されている。",
    "The weather remained mild throughout the reporting period.",
]

Predictor = Callable[[dict[str, Any]], str]


def make_needle(index: int) -> tuple[str, str, str, str]:
    """Deterministic (key, value, statement, question) for needle ``index``."""
    digest = hashlib.sha1(f"niah-needle-{index}".encode("utf-8")).hexdigest()[:8].upper()
    key = f"access-code-{index}"
    value = f"FALCIE-{digest}"
    statement = f"Note: the secret {key} is {value}."
    question = f"What is the secret {key}? Answer with the value only."
    return key, value, statement, question


def _filler(n_chars: int) -> str:
    parts: list[str] = []
    total = 0
    i = 0
    while total < n_chars:
        s = FILLER[i % len(FILLER)]
        parts.append(s)
        total += len(s) + 1
        i += 1
    return " ".join(parts)[:n_chars]


def build_haystack(length: int, depth: float, statement: str) -> tuple[str, int]:
    """Return (haystack_text, needle_char_pos): the needle ``statement`` inserted at
    ~``depth`` through ``length`` chars of filler."""
    filler = _filler(length)
    pos = int(depth * len(filler))
    text = filler[:pos] + " " + statement + " " + filler[pos:]
    return text, pos + 1


def generate_tasks(lengths: list[int], depths: list[float]) -> list[dict[str, Any]]:
    """One NIAH task per (length, depth) cell, with a unique needle each."""
    tasks: list[dict[str, Any]] = []
    idx = 0
    # Dedup + sort so every (length, depth) cell is unique (no id collision, no
    # silently-overwritten matrix cell), independent of the caller's ordering.
    for length in sorted(set(lengths)):
        for depth in sorted(set(depths)):
            key, value, statement, question = make_needle(idx)
            haystack, needle_pos = build_haystack(length, depth, statement)
            tasks.append({
                "id": f"niah-L{length}-D{depth}",
                "area": "long_context",
                "language": "en",
                "prompt": f"{haystack}\n\n{question}",
                "answer": value,
                "metric": "includes",
                "length": length,
                "depth": depth,
                "needle_pos": needle_pos,
            })
            idx += 1
    return tasks


# -- reference predictors ---------------------------------------------------

def gold_predictor(task: dict[str, Any]) -> str:
    return str(task["answer"])


def empty_predictor(task: dict[str, Any]) -> str:
    return ""


def window_predictor(window: int) -> Predictor:
    """A prefix-window stand-in: retrieves only if the needle falls within the first
    ``window`` chars (so it misses long/deep needles)."""
    def predict(task: dict[str, Any]) -> str:
        return str(task["answer"]) if task["needle_pos"] < window else ""
    return predict


# -- scoring ----------------------------------------------------------------

def _acc(passed: int, total: int) -> float:
    return round(passed / total, 4) if total else 0.0


def run_niah(tasks: list[dict[str, Any]], predictor: Predictor) -> dict[str, Any]:
    lengths = sorted({t["length"] for t in tasks})
    depths = sorted({t["depth"] for t in tasks})
    matrix: dict[int, dict[float, int]] = {ln: {} for ln in lengths}
    passed_total = 0
    for task in tasks:
        prediction = predictor(task)
        ok = M.score(task["metric"], prediction, str(task["answer"]), task)
        matrix[task["length"]][task["depth"]] = int(ok)
        passed_total += int(ok)

    by_length = {ln: _acc(sum(matrix[ln].values()), len(matrix[ln])) for ln in lengths}
    by_depth = {
        d: _acc(sum(matrix[ln][d] for ln in lengths if d in matrix[ln]),
                sum(1 for ln in lengths if d in matrix[ln]))
        for d in depths
    }
    return {
        "eval": "needle-in-a-haystack",
        "lengths": lengths,
        "depths": depths,
        "summary": {"task_count": len(tasks), "passed": passed_total,
                    "accuracy": _acc(passed_total, len(tasks))},
        "by_length": by_length,
        "by_depth": by_depth,
        "matrix": {str(ln): {str(d): matrix[ln][d] for d in depths if d in matrix[ln]}
                   for ln in lengths},
    }


def render_markdown(report: dict[str, Any]) -> str:
    L: list[str] = []
    L.append("# Needle-in-a-Haystack (long-context retrieval)")
    L.append("")
    s = report["summary"]
    L.append(f"- **accuracy: {s['accuracy']}** ({s['passed']}/{s['task_count']})")
    L.append("")
    depths = report["depths"]
    L.append("## Retrieval matrix (1 = found) — rows: context length, cols: needle depth")
    L.append("")
    L.append("| length \\ depth | " + " | ".join(f"{int(d*100)}%" for d in depths) + " | by length |")
    L.append("| --- | " + " | ".join(":-:" for _ in depths) + " | ---: |")
    for ln in report["lengths"]:
        cells = [str(report["matrix"][str(ln)].get(str(d), "-")) for d in depths]
        L.append(f"| {ln} | " + " | ".join(cells) + f" | {report['by_length'][ln]} |")
    L.append("| **by depth** | " + " | ".join(str(report["by_depth"][d]) for d in depths) + " |  |")
    L.append("")
    return "\n".join(L) + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--predictor", choices=["gold", "empty", "window"], default="gold")
    ap.add_argument("--window", type=int, default=1500, help="prefix-window size for --predictor window")
    ap.add_argument("--lengths", type=int, nargs="+", default=DEFAULT_LENGTHS)
    ap.add_argument("--depths", type=float, nargs="+", default=DEFAULT_DEPTHS)
    ap.add_argument("--format", choices=["json", "md"], default="json")
    ap.add_argument("--assert-accuracy", type=float, default=None,
                    help="Exit non-zero unless overall accuracy equals this (gate: gold must be 1.0).")
    args = ap.parse_args(argv[1:])

    tasks = generate_tasks(args.lengths, args.depths)
    predictors: dict[str, Predictor] = {
        "gold": gold_predictor, "empty": empty_predictor,
        "window": window_predictor(args.window),
    }
    report = run_niah(tasks, predictors[args.predictor])

    if args.assert_accuracy is not None:
        print(f"{args.predictor}: accuracy={report['summary']['accuracy']} "
              f"({report['summary']['passed']}/{report['summary']['task_count']})")
    elif args.format == "md":
        print(render_markdown(report))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))

    if args.assert_accuracy is not None:
        if abs(report["summary"]["accuracy"] - args.assert_accuracy) > 1e-9:
            print(f"error: accuracy {report['summary']['accuracy']} != {args.assert_accuracy}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
