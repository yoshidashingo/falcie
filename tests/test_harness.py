#!/usr/bin/env python3
"""Tests for the scored evaluation harness (fal'Cie L-004, unit U-E2)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts" / "evals"))

import harness as H  # noqa: E402

SUITE = _ROOT / "evals" / "suites" / "smoke-scored.jsonl"


def _write(tmp: Path, rows: list[dict]) -> Path:
    p = tmp / "suite.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    return p


class TestLoadSuite(unittest.TestCase):
    def test_loads_committed_suite(self) -> None:
        tasks = H.load_suite(SUITE)
        self.assertGreaterEqual(len(tasks), 5)

    def test_rejects_missing_field(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = _write(Path(d), [{"id": "x", "area": "a", "language": "en", "prompt": "p", "answer": "1"}])
            with self.assertRaises(ValueError):
                H.load_suite(p)  # missing metric

    def test_rejects_unknown_metric(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = _write(Path(d), [{"id": "x", "area": "a", "language": "en", "prompt": "p",
                                  "answer": "1", "metric": "bogus"}])
            with self.assertRaises(ValueError):
                H.load_suite(p)

    def test_rejects_duplicate_id(self) -> None:
        task = {"id": "dup", "area": "a", "language": "en", "prompt": "p", "answer": "1", "metric": "exact_match"}
        with tempfile.TemporaryDirectory() as d:
            p = _write(Path(d), [task, dict(task)])
            with self.assertRaises(ValueError):
                H.load_suite(p)

    def test_rejects_empty_answer(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = _write(Path(d), [{"id": "x", "area": "a", "language": "en", "prompt": "p",
                                  "answer": "", "metric": "exact_match"}])
            with self.assertRaises(ValueError):
                H.load_suite(p)

    def test_multiple_choice_requires_choices(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = _write(Path(d), [{"id": "x", "area": "a", "language": "en", "prompt": "p",
                                  "answer": "C", "metric": "multiple_choice"}])
            with self.assertRaises(ValueError):
                H.load_suite(p)

    def test_multiple_choice_answer_must_be_in_choices(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = _write(Path(d), [{"id": "x", "area": "a", "language": "en", "prompt": "p",
                                  "answer": "Z", "metric": "multiple_choice", "choices": ["A", "B", "C"]}])
            with self.assertRaises(ValueError):
                H.load_suite(p)


class TestRunSuite(unittest.TestCase):
    def setUp(self) -> None:
        self.tasks = H.load_suite(SUITE)

    def test_gold_scores_perfect(self) -> None:
        rep = H.run_suite(self.tasks, H.gold_predictor, "ref:gold", SUITE, commit_sha="test")
        self.assertEqual(rep["summary"]["accuracy"], 1.0)
        self.assertEqual(rep["known_failures"], [])
        for area in rep["by_area"].values():
            self.assertEqual(area["accuracy"], 1.0)

    def test_empty_scores_zero(self) -> None:
        rep = H.run_suite(self.tasks, H.empty_predictor, "ref:empty", SUITE, commit_sha="test")
        self.assertEqual(rep["summary"]["accuracy"], 0.0)
        self.assertEqual(len(rep["known_failures"]), rep["summary"]["task_count"])

    def test_report_shape(self) -> None:
        rep = H.run_suite(self.tasks, H.gold_predictor, "ref:gold", SUITE, commit_sha="abc")
        for field in ("harness_version", "suite", "model_id", "commit_sha",
                      "summary", "by_area", "by_language", "known_failures", "tasks"):
            self.assertIn(field, rep)
        self.assertEqual(rep["commit_sha"], "abc")
        self.assertEqual(rep["model_id"], "ref:gold")

    def test_partial_predictor_aggregates_by_area(self) -> None:
        # A predictor that only answers math tasks correctly.
        def math_only(task: dict) -> str:
            return str(task["answer"]) if task["area"] == "math" else ""
        rep = H.run_suite(self.tasks, math_only, "ref:math", SUITE, commit_sha="test")
        self.assertEqual(rep["by_area"]["math"]["accuracy"], 1.0)
        self.assertEqual(rep["by_area"]["knowledge"]["accuracy"], 0.0)
        self.assertGreater(rep["summary"]["accuracy"], 0.0)
        self.assertLess(rep["summary"]["accuracy"], 1.0)


if __name__ == "__main__":
    unittest.main()
