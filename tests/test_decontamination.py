#!/usr/bin/env python3
"""Tests for the benchmark index + decontamination wiring (fal'Cie L-007, unit U-D6)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts" / "data"))

import build_benchmark_index as BBI  # noqa: E402
import contamination as C  # noqa: E402
import records as R  # noqa: E402

INDEX = _ROOT / "evals" / "benchmark-index.jsonl"


class TestIndex(unittest.TestCase):
    def test_committed_index_in_sync_with_suites(self) -> None:
        # The committed index must equal a fresh build (no drift from the suites).
        fresh = BBI._serialize(BBI.build_index())
        self.assertEqual(INDEX.read_text(encoding="utf-8"), fresh,
                         "evals/benchmark-index.jsonl is stale; rebuild it")

    def test_non_empty_and_unique_ids(self) -> None:
        index = BBI.build_index()
        self.assertGreater(len(index), 0)
        ids = [r["id"] for r in index]
        self.assertEqual(len(ids), len(set(ids)))

    def test_includes_prompts_and_answers(self) -> None:
        texts = {r["text"] for r in BBI.build_index()}
        # a scored-suite prompt and a probe text must both be protected
        self.assertIn("What is the capital of France? Answer with the city name only.", texts)
        self.assertTrue(any("fal'Cie" in t for t in texts))


class TestDecontamination(unittest.TestCase):
    def setUp(self) -> None:
        self.bench = C.load_benchmarks(INDEX)

    def test_planted_benchmark_is_flagged_and_removed(self) -> None:
        planted = R.Record(
            id="c1",
            text="What is the capital of France? Answer with the city name only.",
            source="web",
        )
        clean = R.Record(
            id="c2",
            text="A completely unrelated paragraph about distributed systems and queues.",
            source="web",
        )
        flagged = C.flag_contaminated([planted, clean], self.bench)
        by_id = {r.id: r for r in flagged}
        self.assertTrue(by_id["c1"].meta["contaminated"])
        self.assertFalse(by_id["c2"].meta["contaminated"])

        kept = C.remove_contaminated([planted, clean], self.bench)
        self.assertEqual([r.id for r in kept], ["c2"])

    def test_near_duplicate_prompt_is_flagged(self) -> None:
        # A lightly-edited copy of a benchmark prompt should still be caught.
        near = R.Record(
            id="c3",
            text="What is the capital of France?? Answer with the city name only!!",
            source="web",
        )
        flagged = C.flag_contaminated([near], self.bench, threshold=0.8)
        self.assertTrue(flagged[0].meta["contaminated"])

    def test_legit_doc_containing_short_token_is_not_removed(self) -> None:
        # Safety property: a real training doc that merely contains a short
        # answer-like token must NOT be flagged (no over-removal of good data).
        docs = [
            R.Record(id="g1", text="The meeting is at 7 PM with 7 people in the room.", source="web"),
            R.Record(id="g2", text="東京は日本の首都で、多くの企業や大学が集まっている。", source="web"),
            R.Record(id="g3", text="When the build is DONE we ship Paris to production.", source="web"),
        ]
        flagged = C.flag_contaminated(docs, self.bench)
        self.assertTrue(all(not r.meta["contaminated"] for r in flagged),
                        "legitimate docs containing short tokens were over-removed")


if __name__ == "__main__":
    unittest.main()
