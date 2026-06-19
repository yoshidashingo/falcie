#!/usr/bin/env python3
"""Minimal, resumable dataset loader for fal'Cie records (unit U-I3, stdlib only).

Training loops want to iterate over the data pipeline's records in an order that is
(a) reproducible, (b) optionally shuffled, and (c) resumable from a checkpoint. This
module provides exactly that on top of :mod:`records`, with no third-party deps:

* :func:`load_order` reorders an in-memory ``list[Record]`` through a *bounded
  streaming shuffle buffer* (a reservoir-style buffer of fixed capacity) and then
  skips the first ``start`` items of the result.
* :func:`iter_jsonl` is the convenience wrapper: read a JSONL file via
  :func:`records.read_records`, then apply :func:`load_order`.

Shuffle semantics (deterministic, dependency-free):

* ``shuffle_buffer <= 1`` — the buffer holds at most one item, so the output is the
  *original input order* unchanged (no randomness is consulted).
* ``shuffle_buffer > 1`` with a ``seed`` — items stream through a buffer of that
  capacity using a single ``random.Random(seed)``. The buffer fills to capacity;
  thereafter each incoming item evicts a uniformly-random buffered item (which is
  emitted) and takes its slot; once input is exhausted the buffer drains in random
  order. This is a permutation of the input (every item enters and leaves the buffer
  exactly once), and it is fully determined by ``(seed, shuffle_buffer)``.

``start`` skips the first ``start`` items of the resulting order, so resuming at
offset ``k`` yields ``load_order(..., start=0)[k:]`` for the same seed/buffer. With
``start == 0`` the output is therefore always a permutation of the input (no loss,
no duplication); with ``start > 0`` it is a suffix of that permutation.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import records as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def load_order(
    records: list[R.Record],
    *,
    seed: int | None = None,
    shuffle_buffer: int = 0,
    start: int = 0,
) -> list[R.Record]:
    """Return ``records`` reordered through a bounded shuffle buffer, skipping ``start``.

    With ``shuffle_buffer <= 1`` the order is the original input order. With
    ``shuffle_buffer > 1`` and a ``seed`` the items are streamed through a reservoir
    buffer of that capacity using ``random.Random(seed)``, giving a permutation that
    is deterministic for a fixed ``(seed, shuffle_buffer)``. ``start`` then drops the
    first ``start`` items of that order (resumable). For ``start == 0`` the result is
    a permutation of the input; for ``start > 0`` it is the matching suffix.
    """
    if start < 0:
        raise ValueError("start must be non-negative")

    if shuffle_buffer <= 1 or seed is None:
        ordered = list(records)
    else:
        ordered = _buffer_shuffle(records, seed=seed, capacity=shuffle_buffer)

    if start == 0:
        return ordered
    return ordered[start:]


def _buffer_shuffle(
    records: list[R.Record], *, seed: int, capacity: int
) -> list[R.Record]:
    """Stream ``records`` through a fixed-capacity reservoir buffer (seeded shuffle).

    Each item enters the buffer once and is emitted once, so the output is a
    permutation of the input. The eviction/drain choices are driven solely by a
    ``random.Random(seed)``, making the permutation deterministic given
    ``(seed, capacity)``.
    """
    rng = random.Random(seed)
    buffer: list[R.Record] = []
    out: list[R.Record] = []

    for record in records:
        if len(buffer) < capacity:
            buffer.append(record)
            continue
        # Buffer full: evict a uniformly-random slot, emit it, insert the newcomer.
        index = rng.randrange(len(buffer))
        out.append(buffer[index])
        buffer[index] = record

    # Drain the remaining buffer in random order.
    while buffer:
        index = rng.randrange(len(buffer))
        out.append(buffer[index])
        buffer[index] = buffer[-1]
        buffer.pop()

    return out


def iter_jsonl(
    path: Path,
    *,
    seed: int | None = None,
    shuffle_buffer: int = 0,
    start: int = 0,
) -> list[R.Record]:
    """Read records from ``path`` (via :func:`records.read_records`) then order them.

    Equivalent to ``load_order(read_records(path), seed=..., shuffle_buffer=...,
    start=...)``. Returns the (possibly shuffled, possibly suffix-trimmed) list.
    """
    return load_order(
        R.read_records(path),
        seed=seed,
        shuffle_buffer=shuffle_buffer,
        start=start,
    )


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
        "--seed",
        type=int,
        default=None,
        help="Seed for the shuffle buffer (required for shuffling to take effect)",
    )
    parser.add_argument(
        "--shuffle-buffer",
        type=int,
        default=0,
        help="Reservoir buffer size; <=1 keeps original order (default: 0)",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=0,
        help="Skip the first START items of the resulting order (default: 0)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Print at most LIMIT ids; with --count, cap the reported count too",
    )
    parser.add_argument(
        "--count",
        action="store_true",
        help="Print only the number of records, not their ids",
    )
    args = parser.parse_args(argv[1:])

    if args.start < 0:
        parser.error("--start must be non-negative")
    if args.limit is not None and args.limit < 0:
        parser.error("--limit must be non-negative")

    ordered = iter_jsonl(
        args.input,
        seed=args.seed,
        shuffle_buffer=args.shuffle_buffer,
        start=args.start,
    )

    if args.limit is not None:
        ordered = ordered[: args.limit]

    print(f"input: {_rel(args.input)}")
    if args.count:
        print(f"count: {len(ordered)}")
    else:
        print(f"count: {len(ordered)}")
        for record in ordered:
            print(record.id)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
