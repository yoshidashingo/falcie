#!/usr/bin/env python3
"""Unified evaluation runner — one model, all dimensions, one report (fal'Cie L-009).

Consolidates the three eval dimensions into a single model-card-ready report:

  * **Scored QA** (`harness.py`)        — answer accuracy on a scored suite
  * **Base-LM** (`lm_eval.py`)          — bits-per-byte / perplexity on held-out text
  * **Long-context** (`niah.py`)        — needle-in-a-haystack retrieval matrix

This is the dependency-free part of roadmap M2's "evaluation runs automatically": a
real model (M2+) plugs in once as the text **predictor** + a base **LM**, and every
dimension is scored into one report shaped like `docs/evaluation-plan.md` (Reporting
Format). The built-in `gold`/`empty` reference models validate the runner without a
real model.

    python3 scripts/evals/evaluate.py --model gold --lm-smoke --format md
    python3 scripts/evals/evaluate.py --model gold --lm-smoke --assert-reference   # CI
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent / "model"))

import harness as H  # noqa: E402
import lm_eval as LE  # noqa: E402
import niah as NH  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
HARNESS_VERSION = "eval-1.0"
DEFAULT_SUITE = ROOT / "evals" / "suites" / "smoke-scored.jsonl"
DEFAULT_LM_CORPUS = ROOT / "evals" / "tokenizer" / "probes.jsonl"


def current_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                             capture_output=True, text=True)
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def evaluate(
    model_id: str,
    predictor_name: str,
    *,
    suite_path: Path = DEFAULT_SUITE,
    lm_corpus: Path = DEFAULT_LM_CORPUS,
    lm_orders: list[int] | None = None,
    lm_smoke: bool = True,
    niah_lengths: list[int] | None = None,
    niah_depths: list[float] | None = None,
    commit_sha: str | None = None,
) -> dict[str, Any]:
    """Run all three eval dimensions for one model and build a consolidated report.

    ``predictor_name`` selects the reference text predictor (gold/empty/echo) used
    for the QA and NIAH dimensions; the base-LM dimension uses the n-gram baseline
    on ``lm_corpus`` (the best available reference LM until a real model exists).
    """
    predictor = H.REFERENCE_PREDICTORS[predictor_name]

    # 1. Scored QA
    scored = H.run_suite(H.load_suite(suite_path), predictor, model_id, suite_path,
                         commit_sha=commit_sha)
    # 2. Base-LM bits-per-byte (the model's LM; reference = n-gram baseline)
    lm_orders = lm_orders or [0, 2]
    lm = LE.evaluate(lm_corpus, lm_orders, 0.12, lm_smoke)
    # 3. Long-context needle-in-a-haystack
    niah_tasks = NH.generate_tasks(niah_lengths or NH.DEFAULT_LENGTHS,
                                   niah_depths or NH.DEFAULT_DEPTHS)
    niah_rep = NH.run_niah(niah_tasks, predictor)

    dimensions = {
        "scored_qa": {
            "metric": "accuracy",
            "score": scored["summary"]["accuracy"],
            "by_area": {a: v["accuracy"] for a, v in scored["by_area"].items()},
            "known_failures": scored["known_failures"],
        },
        "base_lm": {
            "metric": "bits_per_byte (lower is better; n-gram reference floor)",
            "score": lm["best"]["bits_per_byte"],
            "perplexity": lm["best"]["perplexity"],
            "uniform_baseline": lm["uniform_baseline_bpb"],
            "orders_searched": lm_orders,
        },
        "long_context_niah": {
            "metric": "retrieval_accuracy",
            "score": niah_rep["summary"]["accuracy"],
            "by_depth": niah_rep["by_depth"],
        },
    }
    return {
        "model_id": model_id,
        "status": "reference-predictor (no trained model)",
        "harness_version": HARNESS_VERSION,
        "component_versions": {
            "scored": scored["harness_version"],
            "base_lm": lm["harness_version"],
            "niah": NH.HARNESS_VERSION,
        },
        # commit_sha governs only this top-level report; per-dimension sub-reports
        # derive their own commit internally and are not surfaced here.
        "commit_sha": current_commit() if commit_sha is None else commit_sha,
        "dimensions": dimensions,
        "score_table": [
            {"dimension": "scored_qa", "metric": "accuracy", "score": dimensions["scored_qa"]["score"]},
            {"dimension": "base_lm", "metric": "bits_per_byte", "score": dimensions["base_lm"]["score"]},
            {"dimension": "long_context_niah", "metric": "retrieval_accuracy",
             "score": dimensions["long_context_niah"]["score"]},
        ],
        "known_failures": [f"scored_qa:{i}" for i in dimensions["scored_qa"]["known_failures"]],
    }


def render_markdown(report: dict[str, Any]) -> str:
    L: list[str] = []
    L.append(f"# Evaluation Report — {report['model_id']}")
    L.append("")
    L.append(f"- status: {report['status']}")
    L.append(f"- harness: `{report['harness_version']}` "
             f"(scored `{report['component_versions']['scored']}`, "
             f"base_lm `{report['component_versions']['base_lm']}`, "
             f"niah `{report['component_versions']['niah']}`)")
    L.append(f"- commit: `{report['commit_sha']}`")
    L.append("")
    L.append("## Score table")
    L.append("")
    L.append("| dimension | metric | score |")
    L.append("| --- | --- | ---: |")
    for row in report["score_table"]:
        L.append(f"| {row['dimension']} | {row['metric']} | {row['score']} |")
    L.append("")
    d = report["dimensions"]
    L.append(f"- base-LM: {d['base_lm']['score']} bits/byte — **n-gram reference floor** "
             f"(perplexity {d['base_lm']['perplexity']}; uniform floor "
             f"{d['base_lm']['uniform_baseline']} bits/byte)")
    if report["known_failures"]:
        L.append(f"- known failures: {', '.join(report['known_failures'])}")
    L.append("")
    L.append("> Reference-predictor run — not a capability claim. A trained model (M2+) "
             "plugs in as the predictor + base-LM and is scored by the same runner.")
    L.append("")
    return "\n".join(L) + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", choices=sorted(H.REFERENCE_PREDICTORS), default="gold",
                    help="Reference text predictor for QA + NIAH (a real model plugs in here).")
    ap.add_argument("--model-id", default=None)
    ap.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    ap.add_argument("--lm-corpus", type=Path, default=DEFAULT_LM_CORPUS)
    ap.add_argument("--lm-smoke", action="store_true", help="Run the base-LM dimension in smoke mode.")
    ap.add_argument("--format", choices=["json", "md"], default="json")
    ap.add_argument("--output", type=Path)
    ap.add_argument("--assert-reference", action="store_true",
                    help="CI gate: verify the reference invariants for --model "
                         "(gold -> QA=1.0, NIAH=1.0, BPB<8; empty -> QA=0, NIAH=0).")
    args = ap.parse_args(argv[1:])

    model_id = args.model_id or f"reference:{args.model}"
    try:
        report = evaluate(model_id, args.model, suite_path=args.suite,
                          lm_corpus=args.lm_corpus, lm_smoke=args.lm_smoke)
    except (ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        args.output.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")
        print(f"wrote {args.output}")
    elif args.assert_reference:
        d = report["dimensions"]
        print(f"{model_id}: QA={d['scored_qa']['score']} NIAH={d['long_context_niah']['score']} "
              f"BPB={d['base_lm']['score']}")
    elif args.format == "md":
        print(render_markdown(report))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))

    if args.assert_reference:
        d = report["dimensions"]
        qa, niah_s, bpb = d["scored_qa"]["score"], d["long_context_niah"]["score"], d["base_lm"]["score"]
        if args.model == "gold":
            ok = qa == 1.0 and niah_s == 1.0 and bpb < 8.0
        elif args.model == "empty":
            ok = qa == 0.0 and niah_s == 0.0
        else:
            # No defined invariant (e.g. echo) — refuse rather than silently pass,
            # so --assert-reference can't be wired as a no-op gate.
            print(f"error: no reference invariant defined for --model {args.model}; use gold or empty",
                  file=sys.stderr)
            return 1
        if not ok:
            print(f"error: reference invariant failed for {args.model}: "
                  f"QA={qa} NIAH={niah_s} BPB={bpb}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
