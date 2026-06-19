#!/usr/bin/env python3
"""Aggregate dataset records into a corpus report (unit U-D5, stdlib only).

This is the terminal reporting stage of the data pipeline
``ingest -> dedup -> filter -> contamination -> aggregate``. It reads one or
more JSONL record files, totals their size, and breaks the totals down by
``source`` so the corpus composition is auditable before training.

The aggregation is a pure fold over the records, so it is deterministic and
*additive*: aggregating ``a + b`` yields the same totals as summing the
aggregates of ``a`` and ``b`` independently. That additivity is what makes the
report safe to compute shard-by-shard and what the property tests pin down.

Two sizes are tracked per record: ``chars`` (``len(text)``, Unicode codepoints)
and ``bytes`` (``len(text.encode("utf-8"))``), because tokenizer budgets care
about bytes while human-facing counts care about characters.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(Path(__file__).resolve().parent))

from records import Record, read_records  # noqa: E402


def aggregate(records: list[Record]) -> dict[str, Any]:
    """Fold records into a corpus report.

    Returns a dict with keys:

      * ``total_records`` — number of records.
      * ``total_chars`` — sum of ``len(text)`` over all records.
      * ``total_bytes`` — sum of ``len(text.encode("utf-8"))`` over all records.
      * ``by_source`` — ``{source: {"records", "chars", "bytes"}}``, sorted by
        source name for deterministic output.
      * ``mean_chars`` — ``total_chars / total_records`` (``0`` if empty).

    The fold is deterministic and additive in the record list.
    """
    total_records = 0
    total_chars = 0
    total_bytes = 0
    by_source: dict[str, dict[str, int]] = {}

    for record in records:
        chars = len(record.text)
        num_bytes = len(record.text.encode("utf-8"))

        total_records += 1
        total_chars += chars
        total_bytes += num_bytes

        bucket = by_source.get(record.source)
        if bucket is None:
            bucket = {"records": 0, "chars": 0, "bytes": 0}
            by_source[record.source] = bucket
        bucket["records"] += 1
        bucket["chars"] += chars
        bucket["bytes"] += num_bytes

    ordered_sources = {source: by_source[source] for source in sorted(by_source)}
    mean_chars = total_chars / total_records if total_records else 0.0

    return {
        "total_records": total_records,
        "total_chars": total_chars,
        "total_bytes": total_bytes,
        "by_source": ordered_sources,
        "mean_chars": mean_chars,
    }


def render_markdown(report: dict[str, Any]) -> str:
    """Render an aggregation report as a Markdown document."""
    lines: list[str] = []
    lines.append("# Dataset Aggregation Report")
    lines.append("")
    lines.append(f"- total_records: {report['total_records']}")
    lines.append(f"- total_chars: {report['total_chars']}")
    lines.append(f"- total_bytes: {report['total_bytes']}")
    lines.append(f"- mean_chars: {report['mean_chars']}")
    lines.append("")

    lines.append("## By source")
    lines.append("")
    lines.append("| source | records | chars | bytes |")
    lines.append("| --- | ---: | ---: | ---: |")
    for source, vals in report["by_source"].items():
        lines.append(
            f"| {source} | {vals['records']} | {vals['chars']} | {vals['bytes']} |"
        )
    lines.append("")

    return "\n".join(lines) + "\n"


def render_json(report: dict[str, Any]) -> str:
    """Render an aggregation report as pretty-printed JSON."""
    return json.dumps(report, ensure_ascii=False, indent=2) + "\n"


def _rel(path: Path) -> str:
    """Repo-relative string — committed reports must not embed absolute paths
    (repo Git rule). Falls back to the basename for paths outside the repo."""
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return resolved.name


def aggregate_paths(paths: list[Path]) -> dict[str, Any]:
    """Read every JSONL file in ``paths`` and aggregate across all of them.

    Record ids must be unique *across* the inputs, matching the within-file
    uniqueness ``read_records`` enforces — otherwise a shard-by-shard total would
    silently double-count a record that appears in two shards. A collision raises
    ``ValueError``. (Use ``ingest --start-index`` to keep same-source shards
    disjoint.)
    """
    records: list[Record] = []
    seen_ids: set[str] = set()
    for path in paths:
        for record in read_records(path):
            if record.id in seen_ids:
                raise ValueError(f"{path}: duplicate id across inputs: {record.id}")
            seen_ids.add(record.id)
            records.append(record)
    return aggregate(records)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "inputs",
        nargs="+",
        type=Path,
        help="One or more JSONL record files to aggregate across.",
    )
    parser.add_argument("--format", choices=["json", "md"], default="json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv[1:])

    report = aggregate_paths(args.inputs)
    # Record which files contributed, repo-relative so committed output never
    # embeds an absolute path.
    report = {"inputs": [_rel(path) for path in args.inputs], **report}

    if args.format == "md":
        output = render_markdown(report)
    else:
        output = render_json(report)

    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
