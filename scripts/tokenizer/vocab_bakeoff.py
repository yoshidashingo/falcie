#!/usr/bin/env python3
"""Vocabulary-size bakeoff: Japanese fertility vs embedding cost (fal'Cie L-003).

Trains byte-level BPE at several vocab sizes on a held-out public-domain corpus
and measures, on a disjoint eval slice, the two quantities ADR-003 hinges on:

  1. **Japanese fertility** — tokens/char on Japanese, and whether the candidate
     beats the byte baseline (the byte tokenizer never compresses, so its
     Japanese tokens/char is the number a real subword vocab must beat).
  2. **Embedding-parameter cost** — effective_vocab x d_model, the price a larger
     vocabulary charges to the embedding + output matrices.

This is the in-phase proxy for the full 64k/128k/256k bakeoff: the pure-Python
trainer is O(merges x corpus) and no large corpus may be committed
(`data-policy.md`), so the full sweep is deferred to M2 (real corpus + a faster,
dependency-managed trainer). The harness, metrics, and methodology live here.

Dependency-free. Reuses `bpe.py` (trainer), `score_tokenizer.py` (per-language
scoring), and `special_tokens.py` (the reserved special-token set).

Build the corpus first:
    python3 scripts/data/fetch_corpus.py

Then run:
    python3 scripts/tokenizer/vocab_bakeoff.py --corpus data/bakeoff/corpus.jsonl \
        --vocab-size 512 --vocab-size 1024 --vocab-size 2048 --vocab-size 4096
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

import bpe  # noqa: E402
import score_tokenizer as st  # noqa: E402
import special_tokens as stk  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS = ROOT / "data" / "bakeoff" / "corpus.jsonl"
DEFAULT_VOCAB_SIZES = [512, 1024, 2048, 4096]
DEFAULT_D_MODEL = 2048
DEFAULT_EVAL_FRAC = 0.12
REPORT_DIR = ROOT / "docs" / "tokenizers"


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


def load_corpus(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        rec = json.loads(line)
        for field in ("id", "language", "domain", "text"):
            if field not in rec:
                raise ValueError(f"{path}:{line_no}: missing field {field!r}")
        records.append(rec)
    if not records:
        raise ValueError(f"{path}: empty corpus — run scripts/data/fetch_corpus.py first")
    return records


def split_train_eval(
    records: list[dict[str, Any]], eval_frac: float
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Deterministic held-out split: the last ``eval_frac`` of **each source**
    (grouped by (language, source), ordered by id) goes to eval; the rest train.

    Splitting per source rather than per language means the eval slice samples
    *every* source, so the Japanese fertility number is not measured on a single
    work. The split stays disjoint (a record is never in both)."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for rec in records:
        key = (rec["language"], rec.get("source", rec["language"]))
        groups.setdefault(key, []).append(rec)
    train: list[dict[str, Any]] = []
    eval_: list[dict[str, Any]] = []
    for key in sorted(groups):
        items = sorted(groups[key], key=lambda r: r["id"])
        n = len(items)
        if n < 2:
            # Too few records to hold out without leaking; keep them in train.
            train.extend(items)
            continue
        cut = max(1, min(n - 1, int(n * (1 - eval_frac))))
        train.extend(items[:cut])
        eval_.extend(items[cut:])
    return train, eval_


def embed_cost(effective_vocab: int, d_model: int) -> dict[str, Any]:
    params = effective_vocab * d_model
    return {
        "d_model": d_model,
        "embed_params": params,
        "embed_params_millions": round(params / 1e6, 2),
        "note": "single embedding matrix (vocab x d_model); tied input/output "
                "embeddings assume the same matrix is reused for the LM head.",
    }


def build_report(
    corpus_path: Path, vocab_sizes: list[int], d_model: int, eval_frac: float
) -> dict[str, Any]:
    records = load_corpus(corpus_path)
    train, eval_ = split_train_eval(records, eval_frac)
    train_texts = [r["text"] for r in train]

    def lang_bytes(recs: list[dict[str, Any]]) -> dict[str, int]:
        out: dict[str, int] = {}
        for r in recs:
            out[r["language"]] = out.get(r["language"], 0) + len(r["text"].encode("utf-8"))
        return out

    # Reference baselines on the eval slice (byte = the JP gate threshold).
    baselines = {
        name: st.score(eval_, name, st.TOKENIZERS[name])
        for name in ("byte", "char")
    }
    byte_ja = baselines["byte"]["by_language"].get("ja", {}).get("tokens_per_char")

    candidates: list[dict[str, Any]] = []
    for vocab_size in sorted(set(vocab_sizes)):
        model = bpe.BPEModel.train(
            train_texts, vocab_size=vocab_size, special_tokens=stk.SPECIAL_TOKENS
        )
        report = st.score(eval_, f"bpe-{vocab_size}", model.token_count)
        ja_bucket = report["by_language"].get("ja", {})
        ja_tpc = ja_bucket.get("tokens_per_char")
        gate = None
        if ja_tpc is not None and byte_ja:
            gate = {
                "byte_ja_tokens_per_char": byte_ja,
                "candidate_ja_tokens_per_char": ja_tpc,
                "beats_byte_baseline": ja_tpc < byte_ja,
                "improvement_pct": round((1 - ja_tpc / byte_ja) * 100, 1),
            }
        candidates.append({
            "name": f"bpe-{vocab_size}",
            "requested_vocab_size": vocab_size,
            "effective_vocab_size": model.vocab_size,
            "learned_merges": len(model.merges),
            "collapsed": model.vocab_size < vocab_size,
            "overall": report["overall"],
            "by_language": report["by_language"],
            "japanese_gate": gate,
            "embedding_cost": embed_cost(model.vocab_size, d_model),
        })

    recommendation = choose(candidates)
    return {
        "commit_sha": current_commit(),
        "corpus": _rel(corpus_path),
        "corpus_manifest": "configs/data/bakeoff-corpus.manifest.json",
        "d_model": d_model,
        "eval_frac": eval_frac,
        "train": {"records": len(train), "by_language_bytes": lang_bytes(train)},
        "eval": {"records": len(eval_), "by_language_bytes": lang_bytes(eval_)},
        "baselines": {name: baselines[name]["by_language"] for name in baselines},
        "candidates": candidates,
        "recommendation": recommendation,
        "scope_note": (
            "In-phase proxy for the full 64k/128k/256k bakeoff. The pure-Python BPE "
            "trainer is O(merges x corpus) and no large corpus may be committed "
            "(data-policy.md), so the full sweep is deferred to M2 (real corpus + a "
            "faster, dependency-managed trainer). What generalizes here is the trend "
            "and the methodology, not the absolute vocab size."
        ),
    }


def choose(candidates: list[dict[str, Any]], knee_tol: float = 0.10) -> dict[str, Any]:
    """Pick a vocab size that balances Japanese fertility against embedding cost.

    Japanese fertility decreases monotonically with vocab size in this regime, so
    "lowest tokens/char" alone always names the largest candidate — which is why a
    naive pick and the cost argument disagree. Instead we look for the **cost
    knee**: the first doubling whose Japanese-fertility gain falls below
    ``knee_tol`` (default 10%). If a knee exists in range, recommend the size just
    before it (near-best fertility, half the embedding cost). If no knee is reached
    — each doubling still pays off — the largest tested size is genuinely best here,
    and we say so explicitly rather than implying a knee that the data does not show.
    """
    eligible = [
        c for c in candidates
        if not c["collapsed"] and (c.get("japanese_gate") or {}).get("beats_byte_baseline")
    ]
    if not eligible:
        return {"name": None, "cost_knee_reached": False,
                "reason": "no non-collapsed candidate beat the byte Japanese baseline"}

    ordered = sorted(eligible, key=lambda c: c["effective_vocab_size"])
    steps: list[tuple[dict[str, Any], float]] = []
    for prev, cur in zip(ordered, ordered[1:]):
        pj = prev["japanese_gate"]["candidate_ja_tokens_per_char"]
        cj = cur["japanese_gate"]["candidate_ja_tokens_per_char"]
        steps.append((cur, (pj - cj) / pj if pj else 0.0))

    knee = next((cur for cur, rel in steps if rel < knee_tol), None)
    if knee is not None:
        pick = ordered[max(0, ordered.index(knee) - 1)]
        note = (f"Cost knee reached: scaling past {pick['name']} cuts Japanese tokens/char "
                f"by < {int(knee_tol * 100)}% per doubling while the embedding matrix doubles, "
                f"so {pick['name']} is the cost-aware pick.")
        basis = "cost-aware knee"
    else:
        pick = min(ordered, key=lambda c: c["japanese_gate"]["candidate_ja_tokens_per_char"])
        worst = min((rel for _, rel in steps), default=1.0)
        note = (f"No cost knee within the tested range — each doubling still cut Japanese "
                f"tokens/char by >= {int(worst * 100)}%, so the largest tested vocab "
                f"({pick['name']}) is best here. The knee is expected at larger vocab; the "
                f"production size is fixed by the full 64k/128k/256k run at M2.")
        basis = "best fertility (no knee in range)"

    g = pick["japanese_gate"]
    return {
        "name": pick["name"],
        "basis": basis,
        "cost_knee_reached": knee is not None,
        "japanese_tokens_per_char": g["candidate_ja_tokens_per_char"],
        "improvement_vs_byte_pct": g["improvement_pct"],
        "effective_vocab_size": pick["effective_vocab_size"],
        "embedding_params_millions": pick["embedding_cost"]["embed_params_millions"],
        "reason": note,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    L: list[str] = []
    L.append("# Tokenizer Vocab-Size Bakeoff")
    L.append("")
    L.append("> Generated by `scripts/tokenizer/vocab_bakeoff.py`. Do not edit by hand.")
    L.append("")
    L.append(f"- commit: `{payload['commit_sha']}`")
    L.append(f"- corpus: `{payload['corpus']}` (held-out; provenance in `{payload['corpus_manifest']}`)")
    L.append(f"- d_model (for embedding cost): {payload['d_model']}")
    tb = payload["train"]["by_language_bytes"]
    eb = payload["eval"]["by_language_bytes"]
    L.append(f"- train: {payload['train']['records']} paras "
             f"(ja={tb.get('ja',0)}B en={tb.get('en',0)}B code={tb.get('code',0)}B)")
    L.append(f"- eval (held-out): {payload['eval']['records']} paras "
             f"(ja={eb.get('ja',0)}B en={eb.get('en',0)}B code={eb.get('code',0)}B)")
    L.append("")
    L.append(f"> {payload['scope_note']}")
    L.append("")

    rec = payload["recommendation"]
    L.append("## Recommendation")
    L.append("")
    if rec["name"]:
        L.append(f"**{rec['name']}** (basis: {rec.get('basis', 'n/a')}) — "
                 f"Japanese tokens/char={rec['japanese_tokens_per_char']} "
                 f"({rec['improvement_vs_byte_pct']}% better than the byte baseline), "
                 f"effective vocab={rec['effective_vocab_size']}, "
                 f"embedding ≈{rec['embedding_params_millions']}M params.")
        L.append("")
        L.append(f"Rationale: {rec['reason']}")
    else:
        L.append(f"_{rec['reason']}_")
    L.append("")

    byte_ja = None
    for c in payload["candidates"]:
        if c.get("japanese_gate"):
            byte_ja = c["japanese_gate"]["byte_ja_tokens_per_char"]
            break
    L.append("## Japanese fertility vs embedding cost")
    L.append("")
    if byte_ja is not None:
        L.append(f"Byte baseline (Japanese) = **{byte_ja} tokens/char** — every candidate must beat it.")
        L.append("")
        L.append("> This byte baseline is computed live on *this held-out corpus's* eval slice, "
                 "so it differs from the 7-probe fixture baseline (2.7255 in "
                 "`baseline-reference.md`). The gate compares each candidate to the same eval "
                 "slice it is scored on. The Japanese eval slice samples every Aozora source "
                 "(per-source held-out split); absolute values are a small-scale proxy — only "
                 "the trend generalizes.")
        L.append("")
    L.append("| candidate | eff. vocab | collapsed | ja tokens/char | beats byte | improvement | embed (M params) |")
    L.append("| --- | ---: | :-: | ---: | :-: | ---: | ---: |")
    for c in payload["candidates"]:
        g = c.get("japanese_gate") or {}
        L.append(
            f"| {c['name']} | {c['effective_vocab_size']} | {'yes' if c['collapsed'] else 'no'} "
            f"| {g.get('candidate_ja_tokens_per_char', '-')} "
            f"| {'yes' if g.get('beats_byte_baseline') else 'no'} "
            f"| {str(g.get('improvement_pct', '-')) + '%' if g else '-'} "
            f"| {c['embedding_cost']['embed_params_millions']} |"
        )
    L.append("")

    L.append("## Overall compression (eval slice)")
    L.append("")
    L.append("| candidate | tokens/char | tokens/byte | merges |")
    L.append("| --- | ---: | ---: | ---: |")
    for c in payload["candidates"]:
        o = c["overall"]
        L.append(f"| {c['name']} | {o['tokens_per_char']} | {o['tokens_per_byte']} | {c['learned_merges']} |")
    L.append("")

    langs = sorted({lang for c in payload["candidates"] for lang in c["by_language"]})
    L.append("## By language — tokens/char (eval slice)")
    L.append("")
    L.append("| candidate | " + " | ".join(langs) + " |")
    L.append("| --- | " + " | ".join("---:" for _ in langs) + " |")
    for c in payload["candidates"]:
        cells = [c["name"]]
        for lang in langs:
            b = c["by_language"].get(lang)
            cells.append(str(b["tokens_per_char"]) if b else "-")
        L.append("| " + " | ".join(cells) + " |")
    L.append("")
    return "\n".join(L) + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    ap.add_argument("--vocab-size", type=int, action="append", dest="vocab_sizes")
    ap.add_argument("--d-model", type=int, default=DEFAULT_D_MODEL)
    ap.add_argument("--eval-frac", type=float, default=DEFAULT_EVAL_FRAC)
    ap.add_argument("--output-dir", type=Path, default=REPORT_DIR)
    ap.add_argument("--no-write", action="store_true", help="Print JSON; do not write report files.")
    args = ap.parse_args(argv[1:])

    vocab_sizes = args.vocab_sizes or DEFAULT_VOCAB_SIZES
    payload = build_report(args.corpus, vocab_sizes, args.d_model, args.eval_frac)
    markdown = render_markdown(payload)

    if args.no_write:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "vocab-bakeoff-report.md").write_text(markdown, encoding="utf-8")
    (args.output_dir / "vocab-bakeoff-report.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {_rel(args.output_dir / 'vocab-bakeoff-report.md')}")
    print(f"wrote {_rel(args.output_dir / 'vocab-bakeoff-report.json')}")
    rec = payload["recommendation"]
    print(f"recommended: {rec['name'] or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
