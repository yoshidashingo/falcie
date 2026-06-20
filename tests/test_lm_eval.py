#!/usr/bin/env python3
"""Tests for the base-LM (bits-per-byte) evaluation (fal'Cie L-005, unit U-E4)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts" / "evals"))
sys.path.insert(0, str(_ROOT / "scripts" / "model"))

import lm_eval as LE  # noqa: E402
import ngram_lm as N  # noqa: E402


def _corpus(tmp: Path, rows: list[dict]) -> Path:
    p = tmp / "corpus.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    return p


def _rows(lang: str, source: str, n: int) -> list[dict]:
    return [{"id": f"{source}-{i:03d}", "language": lang, "source": source,
             "text": f"{lang} sample sentence number {i} with some words. "} for i in range(n)]


class TestLoadCorpus(unittest.TestCase):
    def test_rejects_missing_text(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = _corpus(Path(d), [{"language": "en"}])
            with self.assertRaises(ValueError):
                LE.load_corpus(p)

    def test_rejects_empty(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = _corpus(Path(d), [])
            with self.assertRaises(ValueError):
                LE.load_corpus(p)


class TestSplit(unittest.TestCase):
    def test_disjoint_and_per_source(self) -> None:
        records = _rows("ja", "work_a", 20) + _rows("ja", "work_b", 20)
        train, held = LE.split_per_source(records, eval_frac=0.2)
        self.assertEqual({r["id"] for r in train} & {r["id"] for r in held}, set())
        self.assertEqual({r["source"] for r in held}, {"work_a", "work_b"})


class TestAggBpb(unittest.TestCase):
    def test_empty_texts_zero(self) -> None:
        model = N.NgramLM.train(["abcabcabc"], order=1)
        self.assertEqual(LE._agg_bpb(model, []), 0.0)
        self.assertEqual(LE._agg_bpb(model, [""]), 0.0)

    def test_byte_weighted_between_components(self) -> None:
        model = N.NgramLM.train(["the cat sat on the mat. " * 20], order=2)
        agg = LE._agg_bpb(model, ["the cat", "the mat"])
        self.assertGreater(agg, 0.0)
        self.assertLess(agg, N.UNIFORM_BPB)


class TestEvaluate(unittest.TestCase):
    def test_smoke_reports_all_orders_and_beats_uniform(self) -> None:
        records = _rows("en", "a", 30) + _rows("ja", "b", 30)
        with tempfile.TemporaryDirectory() as d:
            p = _corpus(Path(d), records)
            report = LE.evaluate(p, orders=[0, 1, 2], eval_frac=0.2, smoke=True)
        self.assertEqual([r["order"] for r in report["results"]], [0, 1, 2])
        self.assertLess(report["best"]["bits_per_byte"], N.UNIFORM_BPB)
        self.assertIn("en", report["results"][0]["by_language"])
        self.assertIn("ja", report["results"][0]["by_language"])
        self.assertEqual(report["uniform_baseline_bpb"], 8.0)


if __name__ == "__main__":
    unittest.main()
