#!/usr/bin/env python3
"""Shared dataset-record helpers for the fal'Cie data pipeline (stdlib only).

A *record* is one text document flowing through the pipeline
``ingest -> dedup -> filter -> contamination -> aggregate``, persisted as JSONL
(one JSON object per line) with a stable schema:

    {"id": "<unique stable id>", "text": "<content>", "source": "<source name>",
     "meta": { ... optional provenance ... }}

Every stage reads and writes this shape via :func:`read_records` / :func:`write_records`
so the stages compose. Normalization is deterministic and idempotent, which is what
makes the downstream dedup/filter/contamination properties testable.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Record:
    """One text document with a stable id and source provenance."""

    id: str
    text: str
    source: str
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"id": self.id, "text": self.text, "source": self.source}
        if self.meta:
            data["meta"] = self.meta
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any], where: str = "record") -> "Record":
        if not isinstance(data, dict):
            raise ValueError(f"{where}: record must be an object")
        for field_name in ("id", "text", "source"):
            value = data.get(field_name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{where}: {field_name} must be a non-empty string")
        meta = data.get("meta", {})
        if not isinstance(meta, dict):
            raise ValueError(f"{where}: meta must be an object")
        return cls(id=data["id"], text=data["text"], source=data["source"], meta=dict(meta))

    def with_meta(self, **updates: Any) -> "Record":
        """Return a copy with ``meta`` updated (records are frozen)."""
        merged = {**self.meta, **updates}
        return Record(id=self.id, text=self.text, source=self.source, meta=merged)


def normalize_text(text: str) -> str:
    """Deterministic, idempotent text normalization.

    Applies Unicode NFC, unifies newlines (``\\r\\n``/``\\r`` -> ``\\n``), strips
    trailing spaces/tabs per line, and trims leading/trailing blank lines. Each step
    is idempotent, so ``normalize_text(normalize_text(x)) == normalize_text(x)``.
    """
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip(" \t") for line in text.split("\n")]
    while lines and lines[0] == "":
        lines.pop(0)
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def content_hash(text: str) -> str:
    """Stable SHA-1 hex digest of ``text`` (used for exact deduplication)."""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def make_id(source: str, index: int, text: str) -> str:
    """Derive a stable record id from source + position + content."""
    digest = hashlib.sha1(f"{source}\x00{index}\x00{text}".encode("utf-8")).hexdigest()
    return f"{source}-{digest[:16]}"


def char_ngrams(text: str, n: int = 5) -> set[str]:
    """Character n-gram shingles of ``text`` for near-duplicate comparison.

    Text shorter than ``n`` yields a single shingle (the whole text) so short
    documents still compare exactly rather than collapsing to the empty set.
    """
    if n <= 0:
        raise ValueError("n must be positive")
    if len(text) < n:
        return {text} if text else set()
    return {text[i : i + n] for i in range(len(text) - n + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity of two shingle sets (1.0 if both empty, 0.0 if one empty)."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union


def read_records(path: Path) -> list[Record]:
    """Load and validate a JSONL record file (ids must be unique)."""
    path = Path(path)
    records: list[Record] = []
    seen_ids: set[str] = set()
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
        record = Record.from_dict(data, where=f"{path}:{line_no}")
        if record.id in seen_ids:
            raise ValueError(f"{path}:{line_no}: duplicate id: {record.id}")
        seen_ids.add(record.id)
        records.append(record)
    return records


def write_records(path: Path, records: list[Record]) -> None:
    """Write records as JSONL (UTF-8, one object per line)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(record.to_dict(), ensure_ascii=False) for record in records]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
