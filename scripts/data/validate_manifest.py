#!/usr/bin/env python3
"""Validate fal'Cie JSON-compatible YAML dataset manifests.

This intentionally uses only the Python standard library. Manifests currently
use JSON syntax with a .yaml extension, which is valid YAML and easy to validate
before the project adopts a dependency-managed Python environment.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "configs" / "data" / "manifest.schema.yaml"

REQUIRED_FIELDS = {
    "name",
    "version",
    "source",
    "license",
    "license_review",
    "use",
    "languages",
    "domains",
    "estimated_tokens",
    "retrieval_script",
    "processing_config",
    "filters",
    "status",
    "pii_policy",
    "contamination_check",
}

ENUMS = {
    "license_review": {"compatible", "needs_review", "restricted", "rejected"},
    "use": {
        "pretraining",
        "supervised_fine_tuning",
        "preference_training",
        "evaluation",
        "tokenizer",
    },
    "status": {"candidate", "approved", "quarantined", "rejected", "deprecated"},
}

CHECK_STATUS = {"not_started", "planned", "complete", "not_applicable"}
LANGUAGE_RE = re.compile(r"^[a-z]{2,3}(-[A-Z]{2})?$")
DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


def load_json_compatible_yaml(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: not JSON-compatible YAML: {exc}") from exc

    if not isinstance(value, dict):
        raise ValueError(f"{path}: manifest root must be an object")
    return value


def require_non_empty_string(manifest: dict[str, Any], field: str) -> list[str]:
    value = manifest.get(field)
    if not isinstance(value, str) or not value:
        return [f"{field} must be a non-empty string"]
    return []


def validate_string_list(manifest: dict[str, Any], field: str) -> list[str]:
    value = manifest.get(field)
    if not isinstance(value, list) or not value:
        return [f"{field} must be a non-empty array"]
    if not all(isinstance(item, str) and item for item in value):
        return [f"{field} must contain only non-empty strings"]
    if len(value) != len(set(value)):
        return [f"{field} must not contain duplicates"]
    return []


def validate_check_object(manifest: dict[str, Any], field: str) -> list[str]:
    value = manifest.get(field)
    if not isinstance(value, dict):
        return [f"{field} must be an object"]

    errors: list[str] = []
    if not isinstance(value.get("required"), bool):
        errors.append(f"{field}.required must be a boolean")
    if not isinstance(value.get("method"), str) or not value.get("method"):
        errors.append(f"{field}.method must be a non-empty string")
    if value.get("status") not in CHECK_STATUS:
        errors.append(f"{field}.status must be one of {sorted(CHECK_STATUS)}")
    return errors


def validate_manifest(path: Path) -> list[str]:
    manifest = load_json_compatible_yaml(path)
    errors: list[str] = []

    missing = sorted(REQUIRED_FIELDS - manifest.keys())
    if missing:
        errors.append(f"missing required fields: {', '.join(missing)}")

    for field in [
        "name",
        "version",
        "source",
        "license",
        "retrieval_script",
        "processing_config",
    ]:
        errors.extend(require_non_empty_string(manifest, field))

    for field, allowed in ENUMS.items():
        if manifest.get(field) not in allowed:
            errors.append(f"{field} must be one of {sorted(allowed)}")

    errors.extend(validate_string_list(manifest, "languages"))
    for language in manifest.get("languages", []):
        if isinstance(language, str) and not LANGUAGE_RE.match(language):
            errors.append(f"languages contains invalid tag: {language}")

    errors.extend(validate_string_list(manifest, "domains"))
    errors.extend(validate_string_list(manifest, "filters"))

    estimated_tokens = manifest.get("estimated_tokens")
    if not isinstance(estimated_tokens, int) or estimated_tokens < 0:
        errors.append("estimated_tokens must be a non-negative integer")

    errors.extend(validate_check_object(manifest, "pii_policy"))
    errors.extend(validate_check_object(manifest, "contamination_check"))

    reviewed_at = manifest.get("reviewed_at")
    if reviewed_at is not None and (
        not isinstance(reviewed_at, str) or not DATE_RE.match(reviewed_at)
    ):
        errors.append("reviewed_at must use YYYY-MM-DD")

    return errors


def main(argv: list[str]) -> int:
    paths = [Path(arg) for arg in argv[1:]]
    if not paths:
        paths = [ROOT / "configs" / "data" / "example-manifest.yaml"]

    # Ensure the schema remains parseable even though this lightweight validator
    # implements only the project-specific checks above.
    load_json_compatible_yaml(SCHEMA_PATH)

    failed = False
    for path in paths:
        errors = validate_manifest(path)
        if errors:
            failed = True
            print(f"{path}: invalid", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
        else:
            print(f"{path}: ok")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
