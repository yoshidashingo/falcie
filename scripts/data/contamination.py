#!/usr/bin/env python3
"""Contamination check stage (U-D4) for the fal'Cie data pipeline.

Training data must not overlap evaluation benchmarks: a model that has already
seen a benchmark item during pretraining produces meaningless scores. This stage
flags (and optionally removes) records whose text overlaps a known benchmark.

A record is considered *contaminated* when either:

  * its normalized text exactly equals a normalized benchmark text, or
  * its character n-gram Jaccard similarity against any benchmark text is at
    least ``threshold``.

Each record is annotated with ``meta['contaminated']`` (bool) and
``meta['contamination_score']`` (float in [0, 1]) — the maximum Jaccard against
any benchmark, rounded. The flag is decided on that same rounded score, so the two
never disagree. The transform is deterministic given its inputs.

Threshold semantics: the score rule is ``score >= threshold``. With no benchmarks
nothing is contaminated. ``threshold == 0.0`` therefore flags *every* record that
has at least one benchmark to compare against (``0.0 >= 0.0``) — a degenerate
setting to avoid with ``--remove``.

Benchmarks default to the tokenizer probe fixture
(``evals/tokenizer/probes.jsonl``). Override with ``--benchmarks`` pointing at a
``.jsonl`` file (reads each line's ``text`` field) or a ``.txt`` file (one
benchmark text per line).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import records as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BENCHMARKS = ROOT / "evals" / "tokenizer" / "probes.jsonl"

_SCORE_NDIGITS = 4


def _benchmark_profiles(
    benchmark_texts: list[str], ngram: int
) -> tuple[set[str], list[set[str]]]:
    """Precompute normalized exact set + n-gram shingle sets for benchmarks.

    Returns ``(normalized_texts, shingle_sets)`` where ``normalized_texts`` is the
    set of normalized benchmark strings (for the exact-match rule) and
    ``shingle_sets`` is one char-n-gram set per benchmark (for the Jaccard rule).
    Computed once so each record is compared against the prepared benchmarks.
    """
    normalized: set[str] = set()
    shingles: list[set[str]] = []
    for text in benchmark_texts:
        norm = R.normalize_text(text)
        normalized.add(norm)
        shingles.append(R.char_ngrams(norm, ngram))
    return normalized, shingles


def _score_record(
    text: str,
    normalized_benchmarks: set[str],
    benchmark_shingles: list[set[str]],
    threshold: float,
    ngram: int,
) -> tuple[bool, float]:
    """Return ``(contaminated, score)`` for a single record text.

    ``score`` is the maximum Jaccard against any benchmark shingle set (0.0 when
    there are no benchmarks). A record is contaminated when its normalized text
    exactly matches a benchmark or when ``score >= threshold``.
    """
    norm = R.normalize_text(text)
    record_shingles = R.char_ngrams(norm, ngram)

    max_score = 0.0
    for shingles in benchmark_shingles:
        score = R.jaccard(record_shingles, shingles)
        if score > max_score:
            max_score = score

    # Round once and decide on the rounded value so the persisted
    # ``contamination_score`` can never disagree with the ``contaminated`` flag.
    max_score = round(max_score, _SCORE_NDIGITS)
    exact_match = norm in normalized_benchmarks
    # Only the score rule needs a benchmark to compare against; with no benchmarks
    # nothing is contaminated (so ``--remove`` can never wipe a corpus by mistake).
    score_hit = bool(benchmark_shingles) and max_score >= threshold
    contaminated = exact_match or score_hit
    return contaminated, max_score


def flag_contaminated(
    records: list[R.Record],
    benchmark_texts: list[str],
    threshold: float = 0.8,
    ngram: int = 5,
) -> list[R.Record]:
    """Return records annotated with contamination metadata.

    Each returned record carries ``meta['contaminated']`` (bool) and
    ``meta['contamination_score']`` (the rounded maximum Jaccard against any
    benchmark). Input order is preserved; records are otherwise unchanged.
    """
    normalized_benchmarks, benchmark_shingles = _benchmark_profiles(benchmark_texts, ngram)

    annotated: list[R.Record] = []
    for record in records:
        contaminated, score = _score_record(
            record.text, normalized_benchmarks, benchmark_shingles, threshold, ngram
        )
        annotated.append(
            record.with_meta(contaminated=contaminated, contamination_score=score)
        )
    return annotated


def remove_contaminated(
    records: list[R.Record],
    benchmark_texts: list[str],
    threshold: float = 0.8,
    ngram: int = 5,
) -> list[R.Record]:
    """Return only the non-contaminated records (a subsequence of the input).

    The kept records are annotated exactly as :func:`flag_contaminated` would,
    so downstream stages see the contamination metadata on the survivors.
    """
    return [
        record
        for record in flag_contaminated(records, benchmark_texts, threshold, ngram)
        if not record.meta.get("contaminated")
    ]


def load_benchmarks(path: Path) -> list[str]:
    """Load benchmark texts from a ``.jsonl`` (``text`` field) or ``.txt`` file.

    ``.jsonl`` files are parsed one JSON object per line, reading the ``text``
    field. Any other suffix (``.txt`` and friends) is read as one benchmark text
    per line. Blank lines are skipped in both modes.
    """
    path = Path(path)
    if path.suffix == ".jsonl":
        texts: list[str] = []
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
            if not isinstance(data, dict):
                raise ValueError(f"{path}:{line_no}: benchmark line must be an object")
            text = data.get("text")
            if not isinstance(text, str) or not text:
                raise ValueError(f"{path}:{line_no}: text must be a non-empty string")
            texts.append(text)
        return texts

    return [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _rel(path: Path) -> str:
    """Repo-relative string — committed output must not embed absolute paths
    (repo Git rule). Falls back to the basename for paths outside the repo."""
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return resolved.name


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="input records JSONL")
    parser.add_argument(
        "--benchmarks",
        type=Path,
        default=DEFAULT_BENCHMARKS,
        help="benchmark file (.jsonl reads text field / .txt one per line)",
    )
    parser.add_argument("--threshold", type=float, default=0.8)
    parser.add_argument("--ngram", type=int, default=5)
    parser.add_argument(
        "--remove",
        action="store_true",
        help="drop contaminated records instead of only flagging them",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv[1:])

    records = R.read_records(args.input)
    benchmark_texts = load_benchmarks(args.benchmarks)

    flagged = flag_contaminated(records, benchmark_texts, args.threshold, args.ngram)
    contaminated_count = sum(1 for rec in flagged if rec.meta.get("contaminated"))

    if args.remove:
        result = [rec for rec in flagged if not rec.meta.get("contaminated")]
        print(
            f"benchmarks={_rel(args.benchmarks)} input={len(records)} "
            f"contaminated={contaminated_count} removed={contaminated_count} "
            f"kept={len(result)}"
        )
    else:
        result = flagged
        print(
            f"benchmarks={_rel(args.benchmarks)} input={len(records)} "
            f"flagged={contaminated_count}"
        )

    if args.output:
        R.write_records(args.output, result)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
