#!/usr/bin/env python3
"""Tests for the needle-in-a-haystack long-context eval (fal'Cie L-008, unit U-E5)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts" / "evals"))

import niah as NH  # noqa: E402


class TestGenerate(unittest.TestCase):
    def test_grid_size_and_fields(self) -> None:
        tasks = NH.generate_tasks([200, 1000], [0.0, 0.5, 1.0])
        self.assertEqual(len(tasks), 6)  # 2 lengths x 3 depths
        for t in tasks:
            for field in ("id", "prompt", "answer", "metric", "length", "depth", "needle_pos"):
                self.assertIn(field, t)
            # the needle's answer value actually appears in the prompt (retrievable)
            self.assertIn(t["answer"], t["prompt"])

    def test_unique_needle_per_cell(self) -> None:
        answers = [t["answer"] for t in NH.generate_tasks([200, 1000], [0.0, 0.5, 1.0])]
        self.assertEqual(len(answers), len(set(answers)))

    def test_deterministic(self) -> None:
        a = NH.generate_tasks([500], [0.0, 0.5])
        b = NH.generate_tasks([500], [0.0, 0.5])
        self.assertEqual([t["prompt"] for t in a], [t["prompt"] for t in b])

    def test_distinct_depths_get_distinct_ids(self) -> None:
        # sub-1% depths must not collide on the same id
        ids = [t["id"] for t in NH.generate_tasks([500], [0.0, 0.001])]
        self.assertEqual(len(ids), len(set(ids)))

    def test_dedups_repeated_grid_values(self) -> None:
        # repeated lengths/depths collapse to unique cells (no overwritten matrix cell)
        tasks = NH.generate_tasks([500, 500], [0.0, 0.0, 0.5])
        self.assertEqual(len(tasks), 2)  # 1 unique length x 2 unique depths


class TestRun(unittest.TestCase):
    def setUp(self) -> None:
        self.tasks = NH.generate_tasks(NH.DEFAULT_LENGTHS, NH.DEFAULT_DEPTHS)

    def test_gold_is_perfect(self) -> None:
        rep = NH.run_niah(self.tasks, NH.gold_predictor)
        self.assertEqual(rep["summary"]["accuracy"], 1.0)
        for ln_acc in rep["by_length"].values():
            self.assertEqual(ln_acc, 1.0)

    def test_empty_is_zero(self) -> None:
        rep = NH.run_niah(self.tasks, NH.empty_predictor)
        self.assertEqual(rep["summary"]["accuracy"], 0.0)

    def test_window_has_length_depth_structure(self) -> None:
        rep = NH.run_niah(self.tasks, NH.window_predictor(1500))
        # not trivially flat
        self.assertGreater(rep["summary"]["accuracy"], 0.0)
        self.assertLess(rep["summary"]["accuracy"], 1.0)
        # short context fully retrieved; long context degraded
        self.assertEqual(rep["by_length"][200], 1.0)
        self.assertLess(rep["by_length"][4000], 1.0)
        # deep placement is worse than shallow at long context
        self.assertEqual(rep["matrix"]["4000"]["0.0"], 1)
        self.assertEqual(rep["matrix"]["4000"]["1.0"], 0)

    def test_report_shape(self) -> None:
        rep = NH.run_niah(self.tasks, NH.gold_predictor)
        for field in ("eval", "lengths", "depths", "summary", "by_length", "by_depth", "matrix"):
            self.assertIn(field, rep)


if __name__ == "__main__":
    unittest.main()
