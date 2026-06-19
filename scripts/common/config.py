#!/usr/bin/env python3
"""Reproducible config loading and content hashing (unit U-I1, stdlib only).

Reproducibility is a fal'Cie North Star: every run must be reconstructable from
its inputs. That requires *stable* identifiers for configs and data files so a
checkpoint can record exactly which config and dataset produced it. This module
provides those identifiers:

- :func:`load_config` parses the project's JSON-compatible YAML configs (the same
  ``json.loads`` convention the validators use).
- :func:`config_hash` hashes a config *value* canonically, so two dicts that differ
  only in key order hash identically (order of mapping keys is not semantically
  meaningful; list order is).
- :func:`file_hash` hashes raw file bytes (for a dataset manifest or any artifact).

These hashes feed checkpoint metadata (unit U-I2) as ``training_config_hash`` /
``dataset_manifest_hash``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

_CHUNK = 1 << 20  # 1 MiB streaming read for file hashing


def load_config(path: Path) -> dict[str, Any]:
    """Load a JSON-compatible YAML config as a dict.

    Mirrors the dependency-free convention used across the repo: configs are
    authored in JSON syntax (valid YAML) and parsed with the standard library.
    """
    path = Path(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: not JSON-compatible YAML: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path}: config root must be an object")
    return value


def canonical_json(value: Any) -> str:
    """Serialize ``value`` canonically: sorted mapping keys, compact separators.

    Deterministic and stable across key orderings, so it is a sound basis for a
    content hash. List order is preserved (it is significant); only mapping key
    order is normalized.
    """
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def config_hash(value: Any) -> str:
    """SHA-256 of the canonical serialization of ``value`` (key-order invariant)."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    """SHA-256 of a file's raw bytes, read in chunks so large files stream."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()
