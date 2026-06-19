#!/usr/bin/env python3
"""Deduplicate fal'Cie dataset records (stage U-D2, stdlib only).

This is the ``dedup`` stage of the data pipeline
``ingest -> dedup -> filter -> contamination -> aggregate``. It removes
redundant documents in two complementary modes:

* **Exact** — two records whose ``text`` has the same SHA-1 content hash collapse
  to a single record. The first occurrence in input order is kept.
* **Near-duplicate** (optional) — when ``near_dup_threshold`` is given, a record
  is also dropped if the Jaccard similarity of its character n-gram shingles with
  *any already-kept* record is ``>=`` the threshold. At ``threshold == 1.0`` a
  record is dropped when its n-gram shingle *set* equals an earlier kept record's
  set — a strictly looser collapse than exact-text identity (e.g. anagrams at
  small ``n``, or a substring whose repetition yields the same shingle set). Exact
  text identity is already guaranteed by the content-hash pass above; the 1.0
  near-dup pass is the looser set-equality collapse. ``threshold == 0.0`` collapses
  every record into the first (``0.0 >= 0.0``), so it is a degenerate setting.

Both modes preserve input order and keep the first surviving occurrence, so the
output is always a subsequence of the input and the transform is deterministic
given its inputs. Determinism plus subsequence-preservation are what make the
idempotence property (``dedup(dedup(x)) == dedup(x)``) hold and testable.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import records as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def dedup(
    records: list[R.Record],
    near_dup_threshold: float | None = None,
    ngram: int = 5,
) -> list[R.Record]:
    """Return ``records`` with duplicate documents removed (first kept, order preserved).

    Exact duplicates (equal ``content_hash(text)``) always collapse to the first
    occurrence. If ``near_dup_threshold`` is not ``None``, a record is additionally
    dropped when its ``char_ngrams(text, ngram)`` Jaccard with any already-kept
    record is ``>= near_dup_threshold``.

    The result is a subsequence of the input; ``len(result) <= len(records)``.
    """
    kept: list[R.Record] = []
    seen_hashes: set[str] = set()
    kept_shingles: list[set[str]] = []

    for record in records:
        digest = R.content_hash(record.text)
        if digest in seen_hashes:
            continue

        if near_dup_threshold is not None:
            shingles = R.char_ngrams(record.text, ngram)
            if any(
                R.jaccard(shingles, existing) >= near_dup_threshold
                for existing in kept_shingles
            ):
                continue
            kept_shingles.append(shingles)

        seen_hashes.add(digest)
        kept.append(record)

    return kept


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
    parser.add_argument("input", type=Path, help="Input JSONL record file")
    parser.add_argument(
        "--near-dup-threshold",
        type=float,
        default=None,
        help="Drop records with Jaccard >= this value against any kept record",
    )
    parser.add_argument(
        "--ngram",
        type=int,
        default=5,
        help="Character n-gram size for near-duplicate shingles (default: 5)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write kept records as JSONL to this path (default: stdout summary only)",
    )
    args = parser.parse_args(argv[1:])

    if args.near_dup_threshold is not None and not (0.0 <= args.near_dup_threshold <= 1.0):
        parser.error("--near-dup-threshold must be in [0.0, 1.0]")
    if args.ngram <= 0:
        parser.error("--ngram must be a positive integer")

    records = R.read_records(args.input)
    kept = dedup(records, near_dup_threshold=args.near_dup_threshold, ngram=args.ngram)

    removed = len(records) - len(kept)
    print(f"input: {_rel(args.input)}")
    print(f"kept: {len(kept)}")
    print(f"removed: {removed}")

    if args.output is not None:
        R.write_records(args.output, kept)
        print(f"output: {_rel(args.output)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
