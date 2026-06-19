#!/usr/bin/env python3
"""Compare tokenizer candidates and emit a selection report (fal'Cie unit U-T3).

This supports the roadmap **M1 exit criterion** "tokenizer candidate is selected
with evidence" by scoring reference baselines and trained byte-level BPE candidates
on the stable probe fixture.

Honesty model (this is the important part):
  * With the default corpus the BPE candidates are trained on the very probe texts
    they are scored on. On a 7-line, ~780-byte fixture that is **memorization**, not
    compression — each probe collapses to ~1 token. So in this "smoke" mode the
    report **does not recommend** a candidate; it only proves the selection pipeline
    runs end to end and discloses the memorization explicitly.
  * Pass ``--corpus <held-out corpus>`` to train on data disjoint from the probes.
    Only then does the report emit an evidence-based recommendation.

Dependency-free. Reuses the compression scorer in ``score_tokenizer.py`` and the
trainer in ``bpe.py``.
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
from train_bpe import read_corpus  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROBES = ROOT / "evals" / "tokenizer" / "probes.jsonl"
TOK_CONFIG = ROOT / "configs" / "tokenizer" / "evaluation.yaml"
DEFAULT_VOCAB_SIZES = [512, 1024, 2048]


def _rel(path: Path) -> str:
    """Repo-relative string for ``path`` — committed artifacts must not embed
    absolute filesystem paths (repo Git rule)."""
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return resolved.name


def current_commit() -> str:
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


def report_directory() -> Path:
    try:
        config = json.loads(TOK_CONFIG.read_text(encoding="utf-8"))
        rel = config.get("report_directory", "docs/tokenizers")
    except (OSError, json.JSONDecodeError):
        rel = "docs/tokenizers"
    return ROOT / rel


def build_candidates(
    corpus: list[str], vocab_sizes: list[int]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return (name -> token-count callable) and candidate metadata.

    Candidates are the reference baselines (from ``score_tokenizer``) plus one
    trained byte-level BPE model per requested vocab size. Byte-identical BPE models
    are de-duplicated: when two requested sizes collapse to the same merges (the tiny
    corpus exhausts pairs), a single candidate carries both requested sizes. Only the
    BPE models are real, round-trip-safe tokenizers; the baselines bracket the space.
    """
    tokenizers: dict[str, Any] = dict(st.TOKENIZERS)  # byte / char / whitespace
    meta: list[dict[str, Any]] = [
        {"name": name, "kind": "reference", "round_trip_safe": name == "byte"}
        for name in st.TOKENIZERS
    ]

    seen: dict[tuple[Any, ...], str] = {}
    for vocab_size in sorted(set(vocab_sizes)):
        model = bpe.BPEModel.train(corpus, vocab_size=vocab_size)
        key = tuple(model.merges)
        if key in seen:
            existing = next(m for m in meta if m["name"] == seen[key])
            existing["requested_vocab_sizes"].append(vocab_size)
            continue
        name = f"bpe-{vocab_size}"
        seen[key] = name
        tokenizers[name] = model.token_count
        meta.append(
            {
                "name": name,
                "kind": "bpe",
                "round_trip_safe": True,
                "requested_vocab_sizes": [vocab_size],
                "effective_vocab_size": model.vocab_size,
                "learned_merges": len(model.merges),
                "collapsed": model.vocab_size < vocab_size,
            }
        )
    return tokenizers, meta


def choose_recommendation(
    reports: list[dict[str, Any]], meta: list[dict[str, Any]], smoke: bool
) -> dict[str, Any]:
    """Recommend a candidate — but only when trained on a held-out corpus.

    In smoke mode (train == eval) no candidate is recommended; the numbers are
    memorization. Otherwise pick the BPE candidate with the lowest tokens/byte,
    tie-broken toward the smaller effective vocabulary, with a data-driven rationale.
    """
    if smoke:
        return {
            "name": None,
            "smoke": True,
            "reason": "No candidate recommended: smoke run (BPE candidates were "
            "trained on the same probe texts they are scored on), so the numbers "
            "reflect memorization, not generalization. Re-run with "
            "`--corpus <held-out corpus>` for an evidence-based recommendation.",
        }

    by_name = {m["name"]: m for m in meta}
    bpe_reports = [r for r in reports if by_name[r["tokenizer"]]["kind"] == "bpe"]
    if not bpe_reports:
        return {"name": None, "smoke": False, "reason": "no BPE candidate was scored"}

    def sort_key(report: dict[str, Any]) -> tuple[float, int]:
        return (
            report["overall"]["tokens_per_byte"],
            by_name[report["tokenizer"]]["effective_vocab_size"],
        )

    ranked = sorted(bpe_reports, key=sort_key)
    best = ranked[0]
    if len(ranked) == 1:
        why = "the only round-trip-safe BPE candidate scored."
    else:
        best_key, second_key = sort_key(best), sort_key(ranked[1])
        if best_key[0] < second_key[0]:
            why = "strictly lowest overall tokens/byte among round-trip-safe BPE candidates."
        elif best_key[1] != second_key[1]:
            why = "lowest overall tokens/byte (tied); broken toward the smaller effective vocabulary."
        else:
            why = "lowest overall tokens/byte (tied on vocab too); broken by candidate order."
    return {
        "name": best["tokenizer"],
        "smoke": False,
        "tokens_per_byte": best["overall"]["tokens_per_byte"],
        "tokens_per_char": best["overall"]["tokens_per_char"],
        "effective_vocab_size": by_name[best["tokenizer"]]["effective_vocab_size"],
        "reason": why,
    }


def smoke_evidence(reports: list[dict[str, Any]], meta: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Quantify the memorization in smoke mode: per-probe token counts of the
    most-compressing BPE candidate."""
    by_name = {m["name"]: m for m in meta}
    bpe_reports = [r for r in reports if by_name[r["tokenizer"]]["kind"] == "bpe"]
    if not bpe_reports:
        return None
    tightest = min(bpe_reports, key=lambda r: r["overall"]["tokens_per_byte"])
    per_probe_tokens = [p["tokens"] for p in tightest["per_probe"]]
    return {
        "candidate": tightest["tokenizer"],
        "per_probe_tokens": per_probe_tokens,
        "note": f"{tightest['tokenizer']} encodes the {len(per_probe_tokens)} probes to "
        f"{per_probe_tokens} tokens — essentially one token per memorized probe, which "
        f"is why tokens/byte looks near-zero. This is not a compression result.",
    }


def _requested_label(candidate: dict[str, Any]) -> str:
    sizes = candidate.get("requested_vocab_sizes")
    return ", ".join(str(s) for s in sizes) if sizes else ""


def render_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Tokenizer Selection Report")
    lines.append("")
    lines.append("> Generated by `scripts/tokenizer/select_tokenizer.py`. Do not edit by hand.")
    lines.append("")
    lines.append(f"- commit: `{payload['commit_sha']}`")
    lines.append(f"- mode: {'smoke (train == eval)' if payload['smoke'] else 'held-out corpus'}")
    lines.append(f"- probe_file: `{payload['probe_file']}`")
    lines.append(f"- train_corpus: `{payload['train_corpus']}`")
    lines.append(f"- probes: {payload['probe_count']}")
    lines.append("")

    rec = payload["recommendation"]
    lines.append("## Recommendation")
    lines.append("")
    if rec["name"]:
        lines.append(
            f"**{rec['name']}** — tokens/byte={rec['tokens_per_byte']}, "
            f"tokens/char={rec['tokens_per_char']}, "
            f"effective vocab={rec['effective_vocab_size']}."
        )
        lines.append("")
        lines.append(f"Rationale: {rec['reason']}")
    else:
        lines.append(f"_{rec['reason']}_")
    lines.append("")
    if payload["smoke"] and payload.get("smoke_evidence"):
        lines.append(f"> Memorization check: {payload['smoke_evidence']['note']}")
        lines.append("")

    lines.append("## Overall compression")
    lines.append("")
    lines.append("| candidate | kind | round-trip | requested | eff. vocab | tokens/byte | tokens/char |")
    lines.append("| --- | --- | :-: | --- | ---: | ---: | ---: |")
    by_name = {m["name"]: m for m in payload["candidates"]}
    for report in payload["reports"]:
        m = by_name[report["tokenizer"]]
        o = report["overall"]
        lines.append(
            f"| {report['tokenizer']} | {m['kind']} | "
            f"{'yes' if m['round_trip_safe'] else 'no'} | {_requested_label(m)} | "
            f"{m.get('effective_vocab_size', '')} "
            f"| {o['tokens_per_byte']} | {o['tokens_per_char']} |"
        )
    lines.append("")

    lines.append("## By language (tokens/byte)")
    lines.append("")
    languages = sorted({lang for r in payload["reports"] for lang in r["by_language"]})
    lines.append("| candidate | " + " | ".join(languages) + " |")
    lines.append("| --- | " + " | ".join("---:" for _ in languages) + " |")
    for report in payload["reports"]:
        cells = [report["tokenizer"]]
        for lang in languages:
            bucket = report["by_language"].get(lang)
            cells.append(str(bucket["tokens_per_byte"]) if bucket else "-")
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probes", type=Path, default=DEFAULT_PROBES)
    parser.add_argument(
        "--corpus",
        type=Path,
        help="Held-out corpus to train BPE candidates on. Without it, the probe "
        "texts are used (a smoke run that recommends nothing).",
    )
    parser.add_argument(
        "--vocab-size",
        type=int,
        action="append",
        dest="vocab_sizes",
        help="BPE vocab size to train a candidate at. Repeatable.",
    )
    parser.add_argument("--output-dir", type=Path, help="Override the report directory.")
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Validate/score only; print JSON to stdout and do not write report files.",
    )
    args = parser.parse_args(argv[1:])

    probes = st.load_probes(args.probes)
    smoke = args.corpus is None
    if smoke:
        train_corpus = [probe["text"] for probe in probes]
        train_corpus_label = f"{_rel(args.probes)} (probe texts; smoke)"
    else:
        train_corpus = read_corpus(args.corpus)
        train_corpus_label = _rel(args.corpus)

    vocab_sizes = args.vocab_sizes if args.vocab_sizes else DEFAULT_VOCAB_SIZES
    tokenizers, candidates = build_candidates(train_corpus, vocab_sizes)
    reports = [st.score(probes, name, tokenizers[name]) for name in tokenizers]
    recommendation = choose_recommendation(reports, candidates, smoke)

    payload: dict[str, Any] = {
        "commit_sha": current_commit(),
        "smoke": smoke,
        "probe_file": _rel(args.probes),
        "train_corpus": train_corpus_label,
        "probe_count": len(probes),
        "candidates": candidates,
        "recommendation": recommendation,
        "smoke_evidence": smoke_evidence(reports, candidates) if smoke else None,
        "reports": reports,
    }

    markdown = render_markdown(payload)

    if args.no_write:
        print(json.dumps({k: v for k, v in payload.items() if k != "reports"}, ensure_ascii=False, indent=2))
        return 0

    out_dir = args.output_dir or report_directory()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "selection-report.md").write_text(markdown, encoding="utf-8")
    (out_dir / "selection-report.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {_rel(out_dir / 'selection-report.md')}")
    print(f"wrote {_rel(out_dir / 'selection-report.json')}")
    if recommendation["name"]:
        print(f"recommended: {recommendation['name']} (tokens/byte={recommendation['tokens_per_byte']})")
    else:
        print("recommended: none (smoke run — see report)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
