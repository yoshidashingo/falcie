#!/usr/bin/env python3
"""Stage U-D1: ingestion & normalization for the fal'Cie data pipeline.

This is the first stage of the ``ingest -> dedup -> filter -> contamination ->
aggregate`` pipeline. It turns raw documents (either a JSONL file of records or a
plain-text file with one document per line) into normalized :class:`Record`
objects with stable, unique ids.

Ingestion is deterministic: each raw text is normalized with
:func:`records.normalize_text`, records whose normalized form is empty are
dropped, and each survivor is assigned an id via :func:`records.make_id` keyed on
its *original input index* (so duplicate texts still get unique ids). The output
is the canonical JSONL shape consumed by every downstream stage.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import records as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def ingest_records(raw_texts: list[str], source: str, start_index: int = 0) -> list[R.Record]:
    """Normalize raw texts into Records, dropping empties.

    Each text is normalized with :func:`records.normalize_text`. Records whose
    normalized text is empty are dropped. Survivors keep their *original* input
    index (offset by ``start_index``) when deriving the id, so two identical raw
    texts at different positions still receive distinct, stable ids.

    ``start_index`` offsets every id. Pass the running document count when ingesting
    a *new shard of the same source* so the shards get disjoint ids (otherwise each
    shard restarts at index 0 and identical (index, text) pairs collide).
    """
    out: list[R.Record] = []
    for offset, raw in enumerate(raw_texts):
        text = R.normalize_text(raw)
        if not text:
            continue
        out.append(R.Record(R.make_id(source, start_index + offset, text), text, source))
    return out


def read_input_texts(path: Path) -> list[str]:
    """Read raw document texts from a single input file.

    A ``.jsonl`` file is parsed as one JSON record per line; the ``text`` field of
    each record is taken as a document. Any other file is read as plain text with
    one document per line.
    """
    path = Path(path)
    if path.suffix == ".jsonl":
        texts: list[str] = []
        for line_no, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
            if not isinstance(data, dict):
                raise ValueError(f"{path}:{line_no}: record must be an object")
            value = data.get("text")
            if not isinstance(value, str):
                raise ValueError(f"{path}:{line_no}: text must be a string")
            texts.append(value)
        return texts
    # Segment plain text by the SAME line model as normalize_text (\r\n/\r/\n only),
    # not str.splitlines() which would also split on VT/FF/NEL/LS/PS. Drop a single
    # trailing empty element so a final newline does not add a phantom document
    # (this matches splitlines() for the common case without the exotic splits).
    unified = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    lines = unified.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


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
    parser.add_argument(
        "input",
        nargs="+",
        type=Path,
        help="Input file(s). '.jsonl' reads each record's text field; "
        "any other file is read as one document per line.",
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Source name recorded on every output record.",
    )
    parser.add_argument(
        "--start-index",
        type=int,
        default=0,
        help="Id index offset. Pass the prior shard's document count when ingesting "
        "a new shard of the same source so shard ids stay disjoint.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write JSONL records here. Without it, print a JSON summary.",
    )
    args = parser.parse_args(argv[1:])
    if args.start_index < 0:
        parser.error("--start-index must be non-negative")

    raw_texts: list[str] = []
    for path in args.input:
        raw_texts.extend(read_input_texts(path))

    records = ingest_records(raw_texts, args.source, start_index=args.start_index)

    if args.output:
        R.write_records(args.output, records)
        summary = {
            "source": args.source,
            "inputs": [_rel(path) for path in args.input],
            "raw": len(raw_texts),
            "ingested": len(records),
            "dropped": len(raw_texts) - len(records),
            "output": _rel(args.output),
        }
    else:
        summary = {
            "source": args.source,
            "inputs": [_rel(path) for path in args.input],
            "raw": len(raw_texts),
            "ingested": len(records),
            "dropped": len(raw_texts) - len(records),
        }

    sys.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
