#!/usr/bin/env python3
"""Tests for the unified evaluation runner (fal'Cie L-009, unit U-E6)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts" / "evals"))
sys.path.insert(0, str(_ROOT / "scripts" / "model"))

import evaluate as EV  # noqa: E402

PROBES = _ROOT / "evals" / "tokenizer" / "probes.jsonl"


def _run(model: str):
    return EV.evaluate(f"ref:{model}", model, lm_corpus=PROBES, lm_smoke=True, commit_sha="test")


class TestUnifiedReport(unittest.TestCase):
    def test_report_has_required_fields(self) -> None:
        rep = _run("gold")
        for field in ("model_id", "status", "harness_version", "component_versions",
                      "commit_sha", "dimensions", "score_table", "known_failures"):
            self.assertIn(field, rep)
        self.assertEqual(rep["commit_sha"], "test")

    def test_score_table_covers_three_dimensions(self) -> None:
        rep = _run("gold")
        dims = {row["dimension"] for row in rep["score_table"]}
        self.assertEqual(dims, {"scored_qa", "base_lm", "long_context_niah"})

    def test_gold_reference_invariants(self) -> None:
        d = _run("gold")["dimensions"]
        self.assertEqual(d["scored_qa"]["score"], 1.0)
        self.assertEqual(d["long_context_niah"]["score"], 1.0)
        self.assertLess(d["base_lm"]["score"], 8.0)  # beats uniform

    def test_empty_reference_invariants(self) -> None:
        rep = _run("empty")
        d = rep["dimensions"]
        self.assertEqual(d["scored_qa"]["score"], 0.0)
        self.assertEqual(d["long_context_niah"]["score"], 0.0)
        # every scored task is a known failure for the empty predictor
        self.assertTrue(rep["known_failures"])

    def test_markdown_renders(self) -> None:
        md = EV.render_markdown(_run("gold"))
        self.assertIn("Score table", md)
        self.assertIn("scored_qa", md)
        self.assertIn("not a capability claim", md)
        self.assertIn("n-gram reference floor", md)  # base-LM honesty at the table


class TestAssertReferenceGate(unittest.TestCase):
    def test_gold_passes(self) -> None:
        self.assertEqual(
            EV.main(["evaluate.py", "--model", "gold", "--lm-smoke", "--assert-reference"]), 0)

    def test_undefined_invariant_predictor_is_rejected(self) -> None:
        # echo has no defined invariant -> --assert-reference must refuse (not no-op pass)
        self.assertEqual(
            EV.main(["evaluate.py", "--model", "echo", "--lm-smoke", "--assert-reference"]), 1)


if __name__ == "__main__":
    unittest.main()
