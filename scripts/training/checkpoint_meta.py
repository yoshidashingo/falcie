#!/usr/bin/env python3
"""Checkpoint metadata for fal'Cie (unit U-I2, stdlib only).

Reproducibility is a fal'Cie North Star: a released checkpoint must record
exactly which inputs produced it. This module captures the metadata listed under
docs/training-plan.md "Checkpoint Metadata" — model identity, the architecture
config, the tokenizer version, the training token count, the dataset-manifest and
training-config content hashes, the commit SHA, the license, and the intended
lifecycle status (experiment / candidate / release).

The public API mirrors the shape of the dataset-manifest validator:

- :func:`validate_metadata` returns a list of human-readable error strings
  (empty list == valid), so callers can decide whether to warn or fail.
- :func:`build_metadata` assembles a validated plain ``dict`` from keyword
  arguments, raising :class:`ValueError` if the result is invalid.
- :func:`save_metadata` / :func:`load_metadata` persist and reload metadata as
  JSON-compatible YAML (the repo's dependency-free convention).
- :func:`hashes_for` is a convenience that derives the
  ``(training_config_hash, dataset_manifest_hash)`` pair from a config value and
  a manifest path using the shared :mod:`config` helpers.

The hashes are sourced from ``scripts/common/config.py`` (``config_hash`` /
``file_hash``), keeping a single canonical definition of "what produced this".
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "common"))

import config as CFG  # noqa: E402

SCHEMA_PATH = ROOT / "configs" / "training" / "checkpoint.schema.yaml"

# Required metadata fields and their expected python types. ``architecture`` is a
# nested object; the rest are scalars handled explicitly below.
REQUIRED_STRING_FIELDS: tuple[str, ...] = (
    "model_name",
    "model_size",
    "tokenizer_version",
    "dataset_manifest_hash",
    "training_config_hash",
    "commit_sha",
    "license",
)

REQUIRED_FIELDS: frozenset[str] = frozenset(
    REQUIRED_STRING_FIELDS
    + (
        "architecture",
        "training_token_count",
        "intended_status",
    )
)

INTENDED_STATUS: frozenset[str] = frozenset({"experiment", "candidate", "release"})


def validate_metadata(meta: dict[str, Any]) -> list[str]:
    """Return a list of error strings for ``meta``; empty list means valid.

    Checks every required field is present and well-typed: the string fields are
    non-empty strings, ``architecture`` is an object, ``training_token_count`` is a
    non-negative integer, and ``intended_status`` is one of the allowed enum values.
    Unknown fields are rejected, matching the schema's ``additionalProperties: false``
    so a typo'd or stray key cannot slip through (the schema and this validator are
    kept in agreement by ``test_checkpoint_meta.py``).
    """
    if not isinstance(meta, dict):
        return ["metadata root must be an object"]

    errors: list[str] = []

    missing = sorted(REQUIRED_FIELDS - meta.keys())
    if missing:
        errors.append(f"missing required fields: {', '.join(missing)}")

    extra = sorted(meta.keys() - REQUIRED_FIELDS)
    if extra:
        errors.append(f"unexpected fields: {', '.join(extra)}")

    for field in REQUIRED_STRING_FIELDS:
        if field in meta:
            value = meta.get(field)
            if not isinstance(value, str) or not value:
                errors.append(f"{field} must be a non-empty string")

    if "architecture" in meta and not isinstance(meta.get("architecture"), dict):
        errors.append("architecture must be an object")

    if "training_token_count" in meta:
        count = meta.get("training_token_count")
        # bool is a subclass of int; reject it explicitly to avoid True == 1.
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            errors.append("training_token_count must be a non-negative integer")

    if "intended_status" in meta and meta.get("intended_status") not in INTENDED_STATUS:
        errors.append(
            f"intended_status must be one of {sorted(INTENDED_STATUS)}"
        )

    return errors


def build_metadata(
    *,
    model_name: str,
    model_size: str,
    architecture: dict[str, Any],
    tokenizer_version: str,
    training_token_count: int,
    dataset_manifest_hash: str,
    training_config_hash: str,
    commit_sha: str,
    license: str,
    intended_status: str,
) -> dict[str, Any]:
    """Assemble a validated checkpoint-metadata ``dict`` from its fields.

    Returns a plain dict (insertion-ordered to match the schema) and raises
    :class:`ValueError` if the assembled metadata does not validate.
    """
    meta: dict[str, Any] = {
        "model_name": model_name,
        "model_size": model_size,
        "architecture": architecture,
        "tokenizer_version": tokenizer_version,
        "training_token_count": training_token_count,
        "dataset_manifest_hash": dataset_manifest_hash,
        "training_config_hash": training_config_hash,
        "commit_sha": commit_sha,
        "license": license,
        "intended_status": intended_status,
    }
    errors = validate_metadata(meta)
    if errors:
        raise ValueError("invalid checkpoint metadata: " + "; ".join(errors))
    return meta


def hashes_for(config: dict[str, Any], manifest_path: Path) -> tuple[str, str]:
    """Return ``(training_config_hash, dataset_manifest_hash)`` for the inputs.

    ``training_config_hash`` is the canonical content hash of the config value
    (key-order invariant); ``dataset_manifest_hash`` is the byte hash of the
    manifest file. Both come from the shared :mod:`config` module so the repo has a
    single definition of each.
    """
    return CFG.config_hash(config), CFG.file_hash(Path(manifest_path))


def save_metadata(path: Path, meta: dict[str, Any]) -> None:
    """Write ``meta`` to ``path`` as pretty-printed JSON-compatible YAML."""
    text = json.dumps(meta, ensure_ascii=False, indent=2) + "\n"
    Path(path).write_text(text, encoding="utf-8")


def load_metadata(path: Path) -> dict[str, Any]:
    """Load checkpoint metadata from ``path`` (JSON-compatible YAML)."""
    path = Path(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: not JSON-compatible YAML: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path}: metadata root must be an object")
    return value


def _rel(path: Path) -> str:
    """Repo-relative string — committed reports must not embed absolute paths
    (repo Git rule). Falls back to the basename for paths outside the repo."""
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return resolved.name


def main(argv: list[str]) -> int:
    """CLI: validate a checkpoint metadata file and print ok/errors."""
    args = argv[1:]
    if len(args) != 1:
        print("usage: checkpoint_meta.py <meta.json>", file=sys.stderr)
        return 2

    path = Path(args[0])
    try:
        meta = load_metadata(path)
    except (OSError, ValueError) as exc:
        print(f"{_rel(path)}: {exc}", file=sys.stderr)
        return 1

    errors = validate_metadata(meta)
    if errors:
        print(f"{_rel(path)}: invalid", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print(f"{_rel(path)}: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
