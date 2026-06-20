#!/usr/bin/env python3
"""Run the fal'Cie scored evaluation harness over a suite (unit U-E3).

Until a real model exists, this drives the harness with a built-in reference
predictor so the scoring path is exercised end to end:

    python3 scripts/evals/run_eval.py --predictor gold    # must score accuracy 1.0
    python3 scripts/evals/run_eval.py --predictor empty   # must score accuracy 0.0
    python3 scripts/evals/run_eval.py evals/suites/smoke-scored.jsonl --output evals/results/smoke.json

When a model is available, register its ``predict(task) -> str`` in place of the
reference predictors. The report shape is the one `evaluation-plan.md` requires.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import harness as H  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SUITE = ROOT / "evals" / "suites" / "smoke-scored.jsonl"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("suite", nargs="?", default=str(DEFAULT_SUITE))
    ap.add_argument("--predictor", choices=sorted(H.REFERENCE_PREDICTORS), default="gold",
                    help="Built-in reference predictor (a real model plugs in here later).")
    ap.add_argument("--model-id", default=None, help="Override the reported model id.")
    ap.add_argument("--output", type=Path, help="Write JSON report (and .md sibling) here.")
    ap.add_argument("--format", choices=["json", "md"], default="json")
    ap.add_argument("--assert-accuracy", type=float, default=None,
                    help="Exit non-zero unless overall accuracy equals this value "
                         "(CI gate: gold must score 1.0, empty must score 0.0).")
    args = ap.parse_args(argv[1:])

    suite_path = Path(args.suite)
    try:
        tasks = H.load_suite(suite_path)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    predictor = H.REFERENCE_PREDICTORS[args.predictor]
    model_id = args.model_id or f"reference:{args.predictor}"
    report = H.run_suite(tasks, predictor, model_id, suite_path)

    if args.output:
        # --output always writes both a JSON report and a .md sibling (ignores --format).
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        args.output.with_suffix(".md").write_text(H.render_markdown(report), encoding="utf-8")
        print(f"wrote {args.output} (accuracy={report['summary']['accuracy']})")
    elif args.assert_accuracy is not None:
        # Gate mode: keep output to one line.
        print(f"{args.predictor}: accuracy={report['summary']['accuracy']} "
              f"({report['summary']['passed']}/{report['summary']['task_count']})")
    else:
        print(H.render_markdown(report) if args.format == "md"
              else json.dumps(report, ensure_ascii=False, indent=2))

    if args.assert_accuracy is not None:
        actual = report["summary"]["accuracy"]
        if abs(actual - args.assert_accuracy) > 1e-9:
            print(f"error: accuracy {actual} != expected {args.assert_accuracy}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
