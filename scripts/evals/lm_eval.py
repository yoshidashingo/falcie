#!/usr/bin/env python3
"""Base-LM evaluation: bits-per-byte / perplexity on held-out text (fal'Cie L-005).

This is the metric a *base* (pre-instruction) language model is judged on, distinct
from the answer-checking harness (`harness.py`) used for instruction models. It
trains the dependency-free n-gram baseline (`scripts/model/ngram_lm.py`) on a train
split and reports bits-per-byte (BPB) and perplexity, overall and per language, on a
disjoint held-out slice — at several orders so the "model learns" trend is visible.

A uniform model scores 8.0 bits/byte (log2 256); any learned model must beat that.

    python3 scripts/evals/lm_eval.py --corpus data/bakeoff/corpus.jsonl --orders 0 1 2 3
    python3 scripts/evals/lm_eval.py --corpus evals/tokenizer/probes.jsonl --smoke --assert-max-bpb 8.0
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "model"))

import ngram_lm as NLM  # noqa: E402

DEFAULT_CORPUS = ROOT / "data" / "bakeoff" / "corpus.jsonl"
REPORT_DIR = ROOT / "docs" / "evals"


def _rel(path: Path) -> str:
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return resolved.name


def current_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                             capture_output=True, text=True)
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def load_corpus(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        rec = json.loads(line)
        for field in ("language", "text"):
            if field not in rec:
                raise ValueError(f"{path}:{line_no}: missing field {field!r}")
        records.append(rec)
    if not records:
        raise ValueError(f"{path}: empty corpus")
    return records


def split_per_source(records: list[dict[str, Any]], eval_frac: float
                     ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Deterministic per-(language, source) tail split, disjoint train/eval."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for rec in records:
        key = (rec["language"], rec.get("source", rec["language"]))
        groups.setdefault(key, []).append(rec)
    train: list[dict[str, Any]] = []
    eval_: list[dict[str, Any]] = []
    for key in sorted(groups):
        items = sorted(groups[key], key=lambda r: r.get("id", ""))
        n = len(items)
        if n < 2:
            train.extend(items)
            continue
        cut = max(1, min(n - 1, int(n * (1 - eval_frac))))
        train.extend(items[:cut])
        eval_.extend(items[cut:])
    return train, eval_


def _agg_bpb(model: NLM.NgramLM, texts: list[str]) -> float:
    """Byte-weighted aggregate BPB over multiple texts (0.0 if no bytes)."""
    total_bits = 0.0
    total_bytes = 0
    for t in texts:
        nb = len(t.encode("utf-8"))
        if nb:
            total_bits += model.bits_per_byte(t) * nb
            total_bytes += nb
    return round(total_bits / total_bytes, 4) if total_bytes else 0.0


def evaluate(corpus_path: Path, orders: list[int], eval_frac: float, smoke: bool) -> dict[str, Any]:
    records = load_corpus(corpus_path)
    if smoke:
        train, held = records, records
    else:
        train, held = split_per_source(records, eval_frac)
    train_texts = [r["text"] for r in train]
    if not smoke:
        # Drop held-out rows whose exact text also appears in train (short repeated
        # boilerplate the corpus dedup didn't collapse) so held-out is text-disjoint.
        train_set = set(train_texts)
        held = [r for r in held if r["text"] not in train_set]
    langs = sorted({r["language"] for r in held})
    held_by_lang = {lang: [r["text"] for r in held if r["language"] == lang] for lang in langs}
    held_all = [r["text"] for r in held]

    results: list[dict[str, Any]] = []
    for order in sorted(set(orders)):
        model = NLM.NgramLM.train(train_texts, order=order)
        results.append({
            "order": order,
            "bits_per_byte": _agg_bpb(model, held_all),
            "by_language": {lang: _agg_bpb(model, held_by_lang[lang]) for lang in langs},
        })
    best = min(results, key=lambda r: r["bits_per_byte"])
    return {
        "harness_version": "lm-1.0",
        "metric": "bits_per_byte",
        "corpus": _rel(corpus_path),
        "mode": "smoke (train==eval)" if smoke else "held-out",
        "commit_sha": current_commit(),
        "model": "ngram-baseline (byte-level, interpolated)",
        "uniform_baseline_bpb": NLM.UNIFORM_BPB,
        "train_bytes": sum(len(t.encode("utf-8")) for t in train_texts),
        "heldout_bytes": sum(len(t.encode("utf-8")) for t in held_all),
        "results": results,
        "best": {"order": best["order"], "bits_per_byte": best["bits_per_byte"],
                 "perplexity": round(2.0 ** best["bits_per_byte"], 2)},
    }


def render_markdown(report: dict[str, Any]) -> str:
    L: list[str] = []
    L.append("# Base-LM Evaluation — bits-per-byte (n-gram baseline)")
    L.append("")
    L.append("> Generated by `scripts/evals/lm_eval.py`. Do not edit by hand.")
    L.append("> The n-gram model is a **baseline floor, not a capability claim**; a real")
    L.append("> model (M2+) plugs into the same metric. Lower bits-per-byte is better;")
    L.append(f"> a uniform model scores {report['uniform_baseline_bpb']} bits/byte.")
    L.append("")
    L.append(f"- commit: `{report['commit_sha']}`")
    L.append(f"- corpus: `{report['corpus']}` ({report['mode']}; held-out is regenerable, not committed)")
    L.append(f"- model: {report['model']}")
    L.append(f"- train bytes: {report['train_bytes']}, held-out bytes: {report['heldout_bytes']}")
    b = report["best"]
    L.append(f"- **best: order {b['order']} -> {b['bits_per_byte']} bits/byte "
             f"(perplexity {b['perplexity']})**")
    L.append("")
    langs = sorted({l for r in report["results"] for l in r["by_language"]})
    L.append("## bits-per-byte by order")
    L.append("")
    L.append("| order | overall | " + " | ".join(langs) + " |")
    L.append("| ---: | ---: | " + " | ".join("---:" for _ in langs) + " |")
    for r in report["results"]:
        cells = [str(r["order"]), str(r["bits_per_byte"])]
        cells += [str(r["by_language"].get(l, "-")) for l in langs]
        L.append("| " + " | ".join(cells) + " |")
    L.append("")
    L.append(f"Uniform baseline (no model): {report['uniform_baseline_bpb']} bits/byte.")
    L.append("")
    return "\n".join(L) + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    ap.add_argument("--orders", type=int, nargs="+", default=[0, 1, 2, 3])
    ap.add_argument("--eval-frac", type=float, default=0.12)
    ap.add_argument("--smoke", action="store_true", help="Train and eval on the same corpus (CLI smoke).")
    ap.add_argument("--output", type=Path)
    ap.add_argument("--assert-max-bpb", type=float, default=None,
                    help="Exit non-zero unless the best bits-per-byte is below this (gate: must beat uniform 8.0).")
    args = ap.parse_args(argv[1:])

    try:
        report = evaluate(args.corpus, args.orders, args.eval_frac, args.smoke)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        args.output.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")
        print(f"wrote {_rel(args.output)} (best BPB={report['best']['bits_per_byte']})")
    elif args.assert_max_bpb is not None:
        print(f"best BPB={report['best']['bits_per_byte']} (order {report['best']['order']})")
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))

    if args.assert_max_bpb is not None:
        best = report["best"]["bits_per_byte"]
        if not best < args.assert_max_bpb:
            print(f"error: best BPB {best} not below {args.assert_max_bpb}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
