#!/usr/bin/env python3
"""Summarize tokenizer probe fixtures.

This does not score a tokenizer yet. It validates the probe JSONL and reports
character/byte coverage so tokenizer candidates can be compared against a stable
fixture later.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROBES = ROOT / "evals" / "tokenizer" / "probes.jsonl"
REQUIRED_FIELDS = {"id", "language", "domain", "text"}


def load_probes(path: Path) -> list[dict[str, Any]]:
    probes: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            probe = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc

        missing = REQUIRED_FIELDS - probe.keys()
        if missing:
            raise ValueError(f"{path}:{line_no}: missing fields: {sorted(missing)}")
        for field in REQUIRED_FIELDS:
            if not isinstance(probe[field], str) or not probe[field]:
                raise ValueError(f"{path}:{line_no}: {field} must be a non-empty string")
        if probe["id"] in seen_ids:
            raise ValueError(f"{path}:{line_no}: duplicate id: {probe['id']}")
        seen_ids.add(probe["id"])
        probes.append(probe)

    if not probes:
        raise ValueError(f"{path}: no probes found")
    return probes


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT_PROBES
    probes = load_probes(path)

    language_counts = Counter(probe["language"] for probe in probes)
    domain_counts = Counter(probe["domain"] for probe in probes)
    characters = sum(len(probe["text"]) for probe in probes)
    bytes_ = sum(len(probe["text"].encode("utf-8")) for probe in probes)

    print(f"probe_file: {path}")
    print(f"probes: {len(probes)}")
    print(f"characters: {characters}")
    print(f"bytes: {bytes_}")
    print("languages:")
    for language, count in sorted(language_counts.items()):
        print(f"  {language}: {count}")
    print("domains:")
    for domain, count in sorted(domain_counts.items()):
        print(f"  {domain}: {count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
