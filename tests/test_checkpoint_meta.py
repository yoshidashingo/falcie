#!/usr/bin/env python3
"""Tests for unit U-I2 checkpoint metadata (``scripts/training/checkpoint_meta.py``).

Combines property-based tests (via the stdlib ``pbt`` harness) with example-based
tests. The four core properties are:

  1. ``save`` -> ``load`` round-trips to the original dict;
  2. ``build_metadata`` output always validates clean;
  3. ``validate_metadata`` flags each MISSING required field, and an invalid
     ``intended_status``;
  4. a negative ``training_token_count`` is rejected.

The example-based tests pin a concrete valid metadata document, each failure
mode, the ``hashes_for`` helper against the shared config hashes, the
JSON-compatible-YAML schema shape, and the CLI exit codes.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts" / "training"))
sys.path.insert(0, str(_ROOT / "scripts" / "common"))
sys.path.insert(0, str(_ROOT / "tests"))

import pbt  # noqa: E402
import config as CFG  # noqa: E402
import checkpoint_meta as CM  # noqa: E402


# A concrete, valid metadata document reused across tests.
VALID_META: dict = {
    "model_name": "falcie-tiny",
    "model_size": "0.5B",
    "architecture": {"layers": 12, "hidden": 768, "heads": 12},
    "tokenizer_version": "bpe-v1",
    "training_token_count": 1_000_000,
    "dataset_manifest_hash": "a" * 64,
    "training_config_hash": "b" * 64,
    "commit_sha": "deadbeef",
    "license": "Apache-2.0",
    "intended_status": "experiment",
}


def gen_meta(rng) -> dict:
    """Generate a structurally-valid metadata dict with varied field values."""
    return {
        "model_name": pbt.text(min_len=1, max_len=12)(rng) or "m",
        "model_size": pbt.sampled_from(["0.5B", "1B", "7B"])(rng),
        "architecture": {
            "layers": pbt.integers(1, 80)(rng),
            "hidden": pbt.integers(64, 8192)(rng),
        },
        "tokenizer_version": pbt.text(min_len=1, max_len=8)(rng) or "v",
        "training_token_count": pbt.integers(0, 10**12)(rng),
        "dataset_manifest_hash": pbt.text(min_len=1, max_len=64)(rng) or "h",
        "training_config_hash": pbt.text(min_len=1, max_len=64)(rng) or "h",
        "commit_sha": pbt.text(min_len=1, max_len=40)(rng) or "c",
        "license": pbt.sampled_from(["Apache-2.0", "MIT", "CC-BY-4.0"])(rng),
        "intended_status": pbt.sampled_from(sorted(CM.INTENDED_STATUS))(rng),
    }


class CheckpointMetaPropertyTests(unittest.TestCase):
    def test_save_load_round_trip(self) -> None:
        # Property (1): save -> load equals the original dict.
        def prop(meta: dict) -> bool:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "meta.json"
                CM.save_metadata(path, meta)
                return CM.load_metadata(path) == meta

        pbt.for_all(gen_meta, prop, label="save/load round-trip")

    def test_build_metadata_validates_clean(self) -> None:
        # Property (2): build_metadata output validates clean.
        def prop(meta: dict) -> bool:
            built = CM.build_metadata(
                model_name=meta["model_name"],
                model_size=meta["model_size"],
                architecture=meta["architecture"],
                tokenizer_version=meta["tokenizer_version"],
                training_token_count=meta["training_token_count"],
                dataset_manifest_hash=meta["dataset_manifest_hash"],
                training_config_hash=meta["training_config_hash"],
                commit_sha=meta["commit_sha"],
                license=meta["license"],
                intended_status=meta["intended_status"],
            )
            return CM.validate_metadata(built) == [] and built == meta

        pbt.for_all(gen_meta, prop, label="build validates clean")

    def test_missing_required_field_is_flagged(self) -> None:
        # Property (3a): dropping any single required field is flagged.
        fields = sorted(CM.REQUIRED_FIELDS)

        def prop(field: str) -> bool:
            broken = dict(VALID_META)
            del broken[field]
            errors = CM.validate_metadata(broken)
            return any(field in err for err in errors)

        pbt.for_all(pbt.sampled_from(fields), prop, label="missing field flagged")

    def test_invalid_intended_status_is_flagged(self) -> None:
        # Property (3b): a non-enum intended_status is rejected.
        def prop(status: str) -> bool:
            if status in CM.INTENDED_STATUS:
                return True  # only assert on invalid values
            broken = dict(VALID_META)
            broken["intended_status"] = status
            errors = CM.validate_metadata(broken)
            return any("intended_status" in err for err in errors)

        pbt.for_all(pbt.text(max_len=12), prop, label="invalid status flagged")

    def test_negative_token_count_rejected(self) -> None:
        # Property (4): negative training_token_count is rejected.
        def prop(neg: int) -> bool:
            broken = dict(VALID_META)
            broken["training_token_count"] = neg
            errors = CM.validate_metadata(broken)
            return any("training_token_count" in err for err in errors)

        pbt.for_all(pbt.integers(-(10**9), -1), prop, label="negative count rejected")


class CheckpointMetaExampleTests(unittest.TestCase):
    def test_valid_metadata_has_no_errors(self) -> None:
        self.assertEqual(CM.validate_metadata(VALID_META), [])

    def test_build_metadata_returns_plain_dict(self) -> None:
        built = CM.build_metadata(**VALID_META)
        self.assertIsInstance(built, dict)
        self.assertEqual(built, VALID_META)
        self.assertEqual(CM.validate_metadata(built), [])

    def test_build_metadata_raises_on_invalid(self) -> None:
        bad = dict(VALID_META)
        bad["intended_status"] = "nonsense"
        with self.assertRaises(ValueError):
            CM.build_metadata(**bad)

    def test_each_missing_field_flagged(self) -> None:
        for field in sorted(CM.REQUIRED_FIELDS):
            broken = dict(VALID_META)
            del broken[field]
            errors = CM.validate_metadata(broken)
            self.assertTrue(
                any(field in err for err in errors),
                msg=f"missing {field} not flagged: {errors}",
            )

    def test_empty_string_field_flagged(self) -> None:
        broken = dict(VALID_META)
        broken["model_name"] = ""
        errors = CM.validate_metadata(broken)
        self.assertTrue(any("model_name" in err for err in errors))

    def test_architecture_must_be_object(self) -> None:
        broken = dict(VALID_META)
        broken["architecture"] = "not-an-object"
        errors = CM.validate_metadata(broken)
        self.assertTrue(any("architecture" in err for err in errors))

    def test_invalid_intended_status(self) -> None:
        broken = dict(VALID_META)
        broken["intended_status"] = "prod"
        errors = CM.validate_metadata(broken)
        self.assertTrue(any("intended_status" in err for err in errors))

    def test_negative_token_count(self) -> None:
        broken = dict(VALID_META)
        broken["training_token_count"] = -1
        errors = CM.validate_metadata(broken)
        self.assertTrue(any("training_token_count" in err for err in errors))

    def test_bool_token_count_rejected(self) -> None:
        # bool is an int subclass; True must not pass as a token count.
        broken = dict(VALID_META)
        broken["training_token_count"] = True
        errors = CM.validate_metadata(broken)
        self.assertTrue(any("training_token_count" in err for err in errors))

    def test_non_dict_root_flagged(self) -> None:
        self.assertEqual(
            CM.validate_metadata(["not", "a", "dict"]),
            ["metadata root must be an object"],
        )

    def test_unknown_field_rejected(self) -> None:
        # A typo'd / stray key must be flagged, matching the schema's
        # additionalProperties: false (so a "model_id" typo for "model_name" fails).
        broken = dict(VALID_META)
        broken["model_id"] = "oops-typo"
        errors = CM.validate_metadata(broken)
        self.assertTrue(any("model_id" in err for err in errors), msg=str(errors))
        # The canonical valid doc (no extras) still passes.
        self.assertEqual(CM.validate_metadata(VALID_META), [])

    def test_save_load_round_trip_example(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "checkpoint.json"
            CM.save_metadata(path, VALID_META)
            self.assertEqual(CM.load_metadata(path), VALID_META)

    def test_hashes_for_matches_shared_helpers(self) -> None:
        config = {"lr": 0.001, "batch": 32, "schedule": ["warmup", "cosine"]}
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "manifest.yaml"
            manifest.write_text('{"name": "demo"}', encoding="utf-8")
            cfg_hash, man_hash = CM.hashes_for(config, manifest)
            self.assertEqual(cfg_hash, CFG.config_hash(config))
            self.assertEqual(man_hash, CFG.file_hash(manifest))

    def test_hashes_for_key_order_invariant(self) -> None:
        a = {"x": 1, "y": 2}
        b = {"y": 2, "x": 1}
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "m.yaml"
            manifest.write_text("{}", encoding="utf-8")
            self.assertEqual(CM.hashes_for(a, manifest)[0], CM.hashes_for(b, manifest)[0])

    def test_schema_is_json_compatible_yaml(self) -> None:
        schema = json.loads(CM.SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(set(schema["required"]), set(CM.REQUIRED_FIELDS))
        self.assertEqual(
            set(schema["properties"]["intended_status"]["enum"]),
            set(CM.INTENDED_STATUS),
        )
        # The validator rejects unknown fields, so the schema must too — keep the
        # two in agreement (the divergence an unenforced schema would allow).
        self.assertIs(schema.get("additionalProperties"), False)
        self.assertEqual(set(schema["properties"]), set(CM.REQUIRED_FIELDS))

    def test_cli_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "meta.json"
            CM.save_metadata(path, VALID_META)
            self.assertEqual(CM.main(["checkpoint_meta.py", str(path)]), 0)

    def test_cli_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "meta.json"
            broken = dict(VALID_META)
            del broken["license"]
            CM.save_metadata(path, broken)
            self.assertEqual(CM.main(["checkpoint_meta.py", str(path)]), 1)

    def test_cli_usage_error(self) -> None:
        self.assertEqual(CM.main(["checkpoint_meta.py"]), 2)

    def test_cli_bad_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.json"
            path.write_text("{not json", encoding="utf-8")
            self.assertEqual(CM.main(["checkpoint_meta.py", str(path)]), 1)


if __name__ == "__main__":
    unittest.main()
