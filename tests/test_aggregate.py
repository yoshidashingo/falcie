#!/usr/bin/env python3
"""Tests for the dataset aggregation/report stage (unit U-D5).

Property-based tests (PBT category in parentheses):
  * partition (PBT-03): sum of by_source[*]["records"] == total_records
  * invariant (PBT-03): total_chars, total_bytes, total_records are all >= 0
  * additivity (PBT-04): aggregate(a + b)["total_records"] ==
                         aggregate(a)["total_records"] + aggregate(b)["total_records"]
                         (and the same for total_chars / total_bytes)
  * base case (PBT-03): empty input -> total_records 0 and mean_chars 0

Example-based tests complement the properties with concrete fixtures, the
markdown/JSON renderers, the multi-file CLI, and the repo-relative path rule.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts" / "data"))
sys.path.insert(0, str(_ROOT / "tests"))

import records as R  # noqa: E402
import pbt  # noqa: E402
import aggregate  # noqa: E402


def gen_records(rng):
    """Generate a list of records with unique ids (index disambiguates dups)."""
    texts = pbt.lists(pbt.text(max_len=30), max_len=6)(rng)
    sources = ["alpha", "beta", "gamma"]
    return [
        R.Record(R.make_id(sources[i % len(sources)], i, t), t, sources[i % len(sources)])
        for i, t in enumerate(texts)
    ]


def gen_two_record_lists(rng):
    """Generate two record lists whose ids don't collide when concatenated."""
    a = gen_records(rng)
    b_texts = pbt.lists(pbt.text(max_len=30), max_len=6)(rng)
    sources = ["alpha", "beta", "gamma"]
    b = [
        R.Record(R.make_id("b", i, t), t, sources[i % len(sources)])
        for i, t in enumerate(b_texts)
    ]
    return (a, b)


class TestAggregateProperties(unittest.TestCase):
    def test_by_source_records_sum_to_total(self):
        # PBT-03: the per-source partition of record counts is exhaustive.
        def prop(records):
            report = aggregate.aggregate(records)
            per_source = sum(v["records"] for v in report["by_source"].values())
            return per_source == report["total_records"]

        pbt.for_all(gen_records, prop, label="by_source partitions total_records")

    def test_by_source_chars_and_bytes_sum_to_total(self):
        # PBT-03: chars and bytes partition the same way as records.
        def prop(records):
            report = aggregate.aggregate(records)
            chars = sum(v["chars"] for v in report["by_source"].values())
            byts = sum(v["bytes"] for v in report["by_source"].values())
            return chars == report["total_chars"] and byts == report["total_bytes"]

        pbt.for_all(gen_records, prop, label="by_source partitions chars/bytes")

    def test_totals_non_negative(self):
        # PBT-03: counts are never negative.
        def prop(records):
            report = aggregate.aggregate(records)
            return (
                report["total_records"] >= 0
                and report["total_chars"] >= 0
                and report["total_bytes"] >= 0
                and report["mean_chars"] >= 0
            )

        pbt.for_all(gen_records, prop, label="totals non-negative")

    def test_additivity_records(self):
        # PBT-04: total_records is additive over list concatenation.
        def prop(pair):
            a, b = pair
            combined = aggregate.aggregate(a + b)["total_records"]
            split = (
                aggregate.aggregate(a)["total_records"]
                + aggregate.aggregate(b)["total_records"]
            )
            return combined == split

        pbt.for_all(gen_two_record_lists, prop, label="additivity total_records")

    def test_additivity_chars_and_bytes(self):
        # PBT-04: total_chars and total_bytes are additive too.
        def prop(pair):
            a, b = pair
            combined = aggregate.aggregate(a + b)
            agg_a = aggregate.aggregate(a)
            agg_b = aggregate.aggregate(b)
            return (
                combined["total_chars"] == agg_a["total_chars"] + agg_b["total_chars"]
                and combined["total_bytes"]
                == agg_a["total_bytes"] + agg_b["total_bytes"]
            )

        pbt.for_all(gen_two_record_lists, prop, label="additivity chars/bytes")

    def test_total_chars_matches_sum_of_text_lengths(self):
        # Oracle: total_chars equals the naive sum over the input.
        def prop(records):
            report = aggregate.aggregate(records)
            expected = sum(len(rec.text) for rec in records)
            return report["total_chars"] == expected

        pbt.for_all(gen_records, prop, label="total_chars oracle")

    def test_mean_chars_consistent(self):
        # Invariant: mean_chars * total_records reconstructs total_chars.
        def prop(records):
            report = aggregate.aggregate(records)
            if report["total_records"] == 0:
                return report["mean_chars"] == 0
            reconstructed = report["mean_chars"] * report["total_records"]
            return abs(reconstructed - report["total_chars"]) < 1e-6

        pbt.for_all(gen_records, prop, label="mean_chars consistent")


class TestAggregateExamples(unittest.TestCase):
    def test_empty_input(self):
        report = aggregate.aggregate([])
        self.assertEqual(report["total_records"], 0)
        self.assertEqual(report["total_chars"], 0)
        self.assertEqual(report["total_bytes"], 0)
        self.assertEqual(report["mean_chars"], 0.0)
        self.assertEqual(report["by_source"], {})

    def test_known_counts(self):
        records = [
            R.Record(R.make_id("web", 0, "abc"), "abc", "web"),
            R.Record(R.make_id("web", 1, "héllo"), "héllo", "web"),
            R.Record(R.make_id("code", 0, "漢字"), "漢字", "code"),
        ]
        report = aggregate.aggregate(records)
        self.assertEqual(report["total_records"], 3)
        # 3 + 5 + 2 = 10 chars
        self.assertEqual(report["total_chars"], 10)
        # "abc"=3, "héllo"=6 (é is 2 bytes), "漢字"=6 (3 each) -> 15 bytes
        self.assertEqual(report["total_bytes"], 15)
        self.assertAlmostEqual(report["mean_chars"], 10 / 3)
        self.assertEqual(report["by_source"]["web"]["records"], 2)
        self.assertEqual(report["by_source"]["web"]["chars"], 8)
        self.assertEqual(report["by_source"]["web"]["bytes"], 9)
        self.assertEqual(report["by_source"]["code"]["records"], 1)
        self.assertEqual(report["by_source"]["code"]["bytes"], 6)

    def test_by_source_sorted(self):
        records = [
            R.Record(R.make_id("zeta", 0, "x"), "x", "zeta"),
            R.Record(R.make_id("alpha", 0, "y"), "y", "alpha"),
            R.Record(R.make_id("mu", 0, "z"), "z", "mu"),
        ]
        report = aggregate.aggregate(records)
        self.assertEqual(list(report["by_source"].keys()), ["alpha", "mu", "zeta"])

    def test_render_markdown(self):
        records = [R.Record(R.make_id("web", 0, "hello"), "hello", "web")]
        report = aggregate.aggregate(records)
        md = aggregate.render_markdown(report)
        self.assertIn("# Dataset Aggregation Report", md)
        self.assertIn("total_records: 1", md)
        self.assertIn("| web | 1 | 5 | 5 |", md)
        self.assertTrue(md.endswith("\n"))

    def test_render_json_roundtrip(self):
        records = [
            R.Record(R.make_id("web", 0, "hello"), "hello", "web"),
            R.Record(R.make_id("code", 0, "def f(): pass"), "def f(): pass", "code"),
        ]
        report = aggregate.aggregate(records)
        text = aggregate.render_json(report)
        parsed = json.loads(text)
        self.assertEqual(parsed["total_records"], 2)
        self.assertEqual(parsed["by_source"]["web"]["chars"], 5)

    def test_aggregate_paths_multi_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            a_path = tmp_path / "a.jsonl"
            b_path = tmp_path / "b.jsonl"
            R.write_records(
                a_path,
                [
                    R.Record(R.make_id("web", 0, "abc"), "abc", "web"),
                    R.Record(R.make_id("web", 1, "de"), "de", "web"),
                ],
            )
            R.write_records(
                b_path,
                [R.Record(R.make_id("code", 0, "x"), "x", "code")],
            )
            report = aggregate.aggregate_paths([a_path, b_path])
            self.assertEqual(report["total_records"], 3)
            self.assertEqual(report["total_chars"], 6)
            self.assertEqual(report["by_source"]["web"]["records"], 2)
            self.assertEqual(report["by_source"]["code"]["records"], 1)

    def test_aggregate_paths_duplicate_id_across_files_raises(self):
        # aggregate_paths enforces id uniqueness ACROSS inputs (matching the
        # within-file rule of read_records); a shared id must raise ValueError,
        # never silently double-count. We write the SAME record (same source,
        # index, text -> same make_id) into both shards to force the collision.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            a_path = tmp_path / "a.jsonl"
            b_path = tmp_path / "b.jsonl"
            shared = R.Record(R.make_id("web", 0, "abc"), "abc", "web")
            # Each file alone is internally valid; the clash only spans files.
            R.write_records(
                a_path,
                [
                    shared,
                    R.Record(R.make_id("web", 1, "de"), "de", "web"),
                ],
            )
            R.write_records(
                b_path,
                [
                    shared,
                    R.Record(R.make_id("code", 0, "x"), "x", "code"),
                ],
            )
            # Sanity: the id really is identical across the two shards.
            self.assertEqual(
                R.read_records(a_path)[0].id, R.read_records(b_path)[0].id
            )
            with self.assertRaises(ValueError):
                aggregate.aggregate_paths([a_path, b_path])

    def test_aggregate_paths_disjoint_ids_sum_record_counts(self):
        # Positive companion: when ids are disjoint across shards, aggregation
        # succeeds and total_records is exactly the sum of each file's count.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            a_path = tmp_path / "a.jsonl"
            b_path = tmp_path / "b.jsonl"
            a_records = [
                R.Record(R.make_id("web", 0, "abc"), "abc", "web"),
                R.Record(R.make_id("web", 1, "de"), "de", "web"),
                R.Record(R.make_id("web", 2, "fgh"), "fgh", "web"),
            ]
            b_records = [
                R.Record(R.make_id("code", 0, "x"), "x", "code"),
                R.Record(R.make_id("code", 1, "yy"), "yy", "code"),
            ]
            R.write_records(a_path, a_records)
            R.write_records(b_path, b_records)
            report = aggregate.aggregate_paths([a_path, b_path])
            self.assertEqual(
                report["total_records"], len(a_records) + len(b_records)
            )
            self.assertEqual(report["total_records"], 5)
            self.assertEqual(report["by_source"]["web"]["records"], 3)
            self.assertEqual(report["by_source"]["code"]["records"], 2)

    def test_cli_json_output_relative_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            in_path = tmp_path / "in.jsonl"
            out_path = tmp_path / "out.json"
            R.write_records(
                in_path,
                [R.Record(R.make_id("web", 0, "hello"), "hello", "web")],
            )
            rc = aggregate.main(
                [
                    "aggregate.py",
                    str(in_path),
                    "--format",
                    "json",
                    "--output",
                    str(out_path),
                ]
            )
            self.assertEqual(rc, 0)
            payload = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["total_records"], 1)
            # The committed report must never embed an absolute path. The temp
            # file is outside ROOT, so _rel falls back to the basename.
            for entry in payload["inputs"]:
                self.assertFalse(Path(entry).is_absolute())
            self.assertIn("in.jsonl", payload["inputs"])

    def test_cli_md_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            in_path = tmp_path / "in.jsonl"
            out_path = tmp_path / "out.md"
            R.write_records(
                in_path,
                [R.Record(R.make_id("web", 0, "hello"), "hello", "web")],
            )
            rc = aggregate.main(
                ["aggregate.py", str(in_path), "--format", "md", "--output", str(out_path)]
            )
            self.assertEqual(rc, 0)
            md = out_path.read_text(encoding="utf-8")
            self.assertIn("# Dataset Aggregation Report", md)
            self.assertIn("| web | 1 | 5 | 5 |", md)


if __name__ == "__main__":
    unittest.main()
