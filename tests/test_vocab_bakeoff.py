#!/usr/bin/env python3
"""Tests for the vocab-size bakeoff metrics (fal'Cie L-003, unit U-T5).

These cover the pure decision/metric logic — train/eval splitting, embedding-cost
math, and candidate selection — without running the (slow) BPE trainer, so they
stay in the fast unit suite that ``scripts/run_checks.py`` gates on.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts" / "tokenizer"))

import vocab_bakeoff as vb  # noqa: E402


def _recs(lang: str, n: int) -> list[dict[str, str]]:
    return [
        {"id": f"{lang}-{i:03d}", "language": lang, "domain": "lit", "text": f"{lang} text {i}"}
        for i in range(n)
    ]


def _recs_src(lang: str, source: str, n: int) -> list[dict[str, str]]:
    return [
        {"id": f"{source}-{i:03d}", "language": lang, "domain": "lit", "source": source,
         "text": f"{source} text {i}"}
        for i in range(n)
    ]


class TestSplit(unittest.TestCase):
    def test_partition_is_disjoint_and_complete(self) -> None:
        records = _recs("ja", 50) + _recs("en", 50)
        train, eval_ = vb.split_train_eval(records, eval_frac=0.2)
        train_ids = {r["id"] for r in train}
        eval_ids = {r["id"] for r in eval_}
        self.assertEqual(train_ids & eval_ids, set(), "train and eval must be disjoint")
        self.assertEqual(train_ids | eval_ids, {r["id"] for r in records}, "must cover all records")

    def test_both_languages_present_in_eval(self) -> None:
        records = _recs("ja", 50) + _recs("en", 50)
        _, eval_ = vb.split_train_eval(records, eval_frac=0.2)
        langs = {r["language"] for r in eval_}
        self.assertEqual(langs, {"ja", "en"})

    def test_deterministic(self) -> None:
        records = _recs("ja", 30) + _recs("en", 20)
        a = vb.split_train_eval(records, eval_frac=0.15)
        b = vb.split_train_eval(records, eval_frac=0.15)
        self.assertEqual([r["id"] for r in a[0]], [r["id"] for r in b[0]])
        self.assertEqual([r["id"] for r in a[1]], [r["id"] for r in b[1]])

    def test_singleton_language_stays_in_train_no_leak(self) -> None:
        records = _recs("ja", 10) + _recs("code", 1)
        train, eval_ = vb.split_train_eval(records, eval_frac=0.2)
        self.assertIn("code-000", {r["id"] for r in train})
        self.assertNotIn("code-000", {r["id"] for r in eval_})
        # still disjoint
        self.assertEqual({r["id"] for r in train} & {r["id"] for r in eval_}, set())

    def test_eval_samples_every_source(self) -> None:
        # Per-source split: eval must draw from BOTH works, not just one.
        records = _recs_src("ja", "work_a", 20) + _recs_src("ja", "work_b", 20)
        train, eval_ = vb.split_train_eval(records, eval_frac=0.2)
        eval_sources = {r["source"] for r in eval_}
        self.assertEqual(eval_sources, {"work_a", "work_b"})
        self.assertEqual({r["id"] for r in train} & {r["id"] for r in eval_}, set())


class TestEmbedCost(unittest.TestCase):
    def test_params_are_vocab_times_dmodel(self) -> None:
        cost = vb.embed_cost(effective_vocab=4096, d_model=2048)
        self.assertEqual(cost["embed_params"], 4096 * 2048)
        self.assertEqual(cost["embed_params_millions"], round(4096 * 2048 / 1e6, 2))
        self.assertEqual(cost["d_model"], 2048)

    def test_cost_grows_with_vocab(self) -> None:
        small = vb.embed_cost(1024, 2048)["embed_params"]
        big = vb.embed_cost(8192, 2048)["embed_params"]
        self.assertLess(small, big)


def _cand(name: str, ja_tpc: float, vocab: int, collapsed: bool, beats: bool) -> dict:
    return {
        "name": name,
        "effective_vocab_size": vocab,
        "collapsed": collapsed,
        "japanese_gate": {
            "byte_ja_tokens_per_char": 3.0,
            "candidate_ja_tokens_per_char": ja_tpc,
            "beats_byte_baseline": beats,
            "improvement_pct": round((1 - ja_tpc / 3.0) * 100, 1),
        },
        "embedding_cost": vb.embed_cost(vocab, 2048),
    }


class TestChoose(unittest.TestCase):
    def test_picks_lowest_japanese_tokens_per_char(self) -> None:
        cands = [
            _cand("bpe-1024", 1.4, 1024, False, True),
            _cand("bpe-2048", 1.1, 2048, False, True),
            _cand("bpe-4096", 1.2, 4096, False, True),
        ]
        self.assertEqual(vb.choose(cands)["name"], "bpe-2048")

    def test_tie_breaks_toward_smaller_embedding(self) -> None:
        cands = [
            _cand("bpe-4096", 1.20, 4096, False, True),
            _cand("bpe-2048", 1.20, 2048, False, True),
        ]
        self.assertEqual(vb.choose(cands)["name"], "bpe-2048")

    def test_excludes_collapsed_and_gate_failures(self) -> None:
        cands = [
            _cand("bpe-512", 0.9, 512, True, True),    # collapsed -> excluded
            _cand("bpe-1024", 0.8, 1024, False, False),  # fails gate -> excluded
            _cand("bpe-2048", 1.3, 2048, False, True),   # only eligible
        ]
        self.assertEqual(vb.choose(cands)["name"], "bpe-2048")

    def test_none_when_no_eligible(self) -> None:
        cands = [_cand("bpe-512", 0.9, 512, True, True)]
        self.assertIsNone(vb.choose(cands)["name"])

    def test_no_knee_recommends_largest(self) -> None:
        # Each doubling still improves ja tokens/char by >=10% -> no knee, pick largest.
        cands = [
            _cand("bpe-512", 1.3, 512, False, True),
            _cand("bpe-1024", 1.0, 1024, False, True),
            _cand("bpe-2048", 0.8, 2048, False, True),
        ]
        result = vb.choose(cands)
        self.assertEqual(result["name"], "bpe-2048")
        self.assertFalse(result["cost_knee_reached"])

    def test_knee_recommends_size_before(self) -> None:
        # Doubling 1024->2048 improves <10% -> knee; recommend the smaller 1024.
        cands = [
            _cand("bpe-1024", 1.00, 1024, False, True),
            _cand("bpe-2048", 0.95, 2048, False, True),
        ]
        result = vb.choose(cands)
        self.assertEqual(result["name"], "bpe-1024")
        self.assertTrue(result["cost_knee_reached"])


class TestLoadCorpus(unittest.TestCase):
    def test_rejects_missing_field(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.jsonl"
            p.write_text(json.dumps({"id": "x", "language": "ja", "text": "hi"}) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                vb.load_corpus(p)  # missing "domain"

    def test_rejects_empty(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.jsonl"
            p.write_text("\n\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                vb.load_corpus(p)


if __name__ == "__main__":
    unittest.main()
