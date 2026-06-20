#!/usr/bin/env python3
"""Tests for the byte n-gram baseline LM (fal'Cie L-005, unit U-M1)."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts" / "model"))

import ngram_lm as N  # noqa: E402

TRAIN = [
    "the quick brown fox jumps over the lazy dog. " * 30,
    "吾輩は猫である。名前はまだ無い。どこで生れたか見当がつかぬ。" * 30,
]
HELD = "the quick brown fox runs. 吾輩は猫だ。"


class TestDistribution(unittest.TestCase):
    def test_sums_to_one_and_positive(self) -> None:
        for order in (0, 1, 2, 3):
            model = N.NgramLM.train(TRAIN, order=order)
            for ctx in (b"", b"t", b"the", b"\xe7\x8c"):
                dist = model.distribution(ctx)
                self.assertAlmostEqual(sum(dist), 1.0, places=9)
                self.assertTrue(all(p > 0 for p in dist))

    def test_prob_in_unit_interval(self) -> None:
        model = N.NgramLM.train(TRAIN, order=2)
        p = model.prob(b"th", ord("e"))
        self.assertGreater(p, 0.0)
        self.assertLessEqual(p, 1.0)


class TestBitsPerByte(unittest.TestCase):
    def test_finite_positive_below_uniform(self) -> None:
        model = N.NgramLM.train(TRAIN, order=2)
        bpb = model.bits_per_byte(HELD)
        self.assertGreater(bpb, 0.0)
        self.assertLess(bpb, N.UNIFORM_BPB)  # must beat a uniform model (8.0)

    def test_empty_text_is_zero(self) -> None:
        model = N.NgramLM.train(TRAIN, order=2)
        self.assertEqual(model.bits_per_byte(""), 0.0)

    def test_perplexity_matches_bpb(self) -> None:
        model = N.NgramLM.train(TRAIN, order=2)
        self.assertAlmostEqual(model.perplexity(HELD), 2.0 ** model.bits_per_byte(HELD), places=9)

    def test_higher_order_fits_training_better(self) -> None:
        # On training text, more context never hurts and here strictly helps.
        bpb0 = N.NgramLM.train(TRAIN, order=0).bits_per_byte(TRAIN[0])
        bpb2 = N.NgramLM.train(TRAIN, order=2).bits_per_byte(TRAIN[0])
        self.assertLess(bpb2, bpb0)

    def test_deterministic(self) -> None:
        a = N.NgramLM.train(TRAIN, order=3).bits_per_byte(HELD)
        b = N.NgramLM.train(TRAIN, order=3).bits_per_byte(HELD)
        self.assertEqual(a, b)


class TestEdges(unittest.TestCase):
    def test_negative_order_rejected(self) -> None:
        with self.assertRaises(ValueError):
            N.NgramLM(order=-1)

    def test_unseen_byte_still_positive(self) -> None:
        # A byte never seen in training must keep non-zero probability (uniform floor).
        model = N.NgramLM.train(["aaaa"], order=2)
        self.assertGreater(model.prob(b"aa", ord("z")), 0.0)

    def test_finite_bpb_under_fully_unseen_context(self) -> None:
        # Scoring high bytes under an ASCII-only model must stay finite (the floor).
        model = N.NgramLM.train(["only ascii letters here"], order=3)
        self.assertTrue(math.isfinite(model.bits_per_byte("ÿþ")))

    def test_floor_weight_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            N.NgramLM(order=2, floor_weight=0.0)


if __name__ == "__main__":
    unittest.main()
