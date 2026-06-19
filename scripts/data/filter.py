#!/usr/bin/env python3
"""Quality filtering stage (unit U-D3) for the fal'Cie data pipeline.

This is the ``filter`` step of ``ingest -> dedup -> filter -> contamination ->
aggregate``. It drops low-quality records using a small set of cheap, language-
agnostic heuristics. Each heuristic is a per-record predicate over the record's
text, so filtering is a pure, deterministic, order-preserving subsequence
selection: it never reorders, mutates, or merges records, it only keeps or drops.

The thresholds live in a JSON-compatible YAML config (loaded with ``json.loads``,
the same dependency-free convention as ``validate_manifest.py``) merged over a
permissive default where every check is disabled. With the default config nothing
is dropped, which makes the stage a safe no-op until thresholds are chosen.

Config keys (all optional; an absent or ``None`` ratio disables that check):

  * ``min_chars`` (int, default 1) — drop text shorter than this many characters.
  * ``max_chars`` (int|None, default None) — drop text longer than this.
  * ``max_symbol_ratio`` (float|None) — drop if the fraction of characters that
    are neither alphanumeric nor whitespace exceeds this.
  * ``max_whitespace_ratio`` (float|None) — drop if the fraction of whitespace
    characters exceeds this.
  * ``max_repeat_line_ratio`` (float|None) — drop if the fraction of lines that
    duplicate an earlier line exceeds this.

Because every predicate depends only on the record's own text (not on other
records or position), ``filter_records`` is idempotent: filtering an already
filtered list keeps exactly the same records.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import records as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]

# Permissive defaults: only ``min_chars`` is active (and at its minimum), every
# ratio check is disabled. Under these defaults nothing is dropped (property 5).
DEFAULT_CONFIG: dict[str, Any] = {
    "min_chars": 1,
    "max_chars": None,
    "max_symbol_ratio": None,
    "max_whitespace_ratio": None,
    "max_repeat_line_ratio": None,
}


def _symbol_ratio(text: str) -> float:
    """Fraction of characters that are neither alphanumeric nor whitespace."""
    if not text:
        return 0.0
    symbols = sum(1 for ch in text if not ch.isalnum() and not ch.isspace())
    return symbols / len(text)


def _whitespace_ratio(text: str) -> float:
    """Fraction of characters that are whitespace."""
    if not text:
        return 0.0
    spaces = sum(1 for ch in text if ch.isspace())
    return spaces / len(text)


def _repeat_line_ratio(text: str) -> float:
    """Fraction of lines that are exact duplicates of an earlier line.

    The first occurrence of each distinct line is not counted as a repeat; only
    later identical lines are. An empty text (no lines) has a ratio of 0.0.
    """
    # str.split("\n") always yields at least one element (""-> [""]), so an empty
    # text is a single empty line with a 0.0 repeat ratio — no empty-list guard needed.
    lines = text.split("\n")
    seen: set[str] = set()
    repeats = 0
    for line in lines:
        if line in seen:
            repeats += 1
        else:
            seen.add(line)
    return repeats / len(lines)


def passes_filters(text: str, cfg: dict[str, Any]) -> bool:
    """Return ``True`` if ``text`` should be kept under ``cfg``.

    ``cfg`` is merged over :data:`DEFAULT_CONFIG`, so a partial config only needs
    to specify the keys it wants to override. A ``None`` (or missing) ratio
    threshold disables that particular check.
    """
    merged = {**DEFAULT_CONFIG, **cfg}

    min_chars = merged["min_chars"]
    if min_chars is not None and len(text) < min_chars:
        return False

    max_chars = merged["max_chars"]
    if max_chars is not None and len(text) > max_chars:
        return False

    max_symbol_ratio = merged["max_symbol_ratio"]
    if max_symbol_ratio is not None and _symbol_ratio(text) > max_symbol_ratio:
        return False

    max_whitespace_ratio = merged["max_whitespace_ratio"]
    if max_whitespace_ratio is not None and _whitespace_ratio(text) > max_whitespace_ratio:
        return False

    max_repeat_line_ratio = merged["max_repeat_line_ratio"]
    if max_repeat_line_ratio is not None and _repeat_line_ratio(text) > max_repeat_line_ratio:
        return False

    return True


def filter_records(records: list[R.Record], cfg: dict[str, Any]) -> list[R.Record]:
    """Keep only the records whose text passes :func:`passes_filters`.

    Order-preserving: the result is a subsequence of ``records``. Pure and
    deterministic given the inputs, and idempotent because each predicate looks
    only at its own record's text.
    """
    return [record for record in records if passes_filters(record.text, cfg)]


def load_config(path: Path) -> dict[str, Any]:
    """Load a JSON-compatible YAML filter config merged over the defaults.

    Mirrors ``validate_manifest.load_json_compatible_yaml``: configs currently
    use JSON syntax (valid YAML) so the standard-library ``json`` parser is
    enough. The loaded object is merged *over* :data:`DEFAULT_CONFIG`.
    """
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: not JSON-compatible YAML: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path}: filter config root must be an object")
    return {**DEFAULT_CONFIG, **value}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Input JSONL record file")
    parser.add_argument(
        "--config",
        type=Path,
        help="JSON-compatible YAML filter config (merged over defaults)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Where to write kept records as JSONL (omit to only report counts)",
    )
    args = parser.parse_args(argv[1:])

    cfg = load_config(args.config) if args.config else dict(DEFAULT_CONFIG)

    records = R.read_records(args.input)
    kept = filter_records(records, cfg)
    removed = len(records) - len(kept)

    if args.output:
        R.write_records(args.output, kept)

    print(f"kept {len(kept)} removed {removed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
