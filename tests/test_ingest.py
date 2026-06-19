#!/usr/bin/env python3
"""Tests for Stage U-D1 ingestion & normalization (``scripts/data/ingest.py``).

Combines property-based tests (via the stdlib ``pbt`` harness) with a handful of
example-based tests. The four core properties — idempotent normalization, count
preservation, id uniqueness, and JSONL round-trip — are checked over generated
inputs; the examples pin down concrete edge cases (empty/blank drops, duplicate
texts, CRLF normalization, the JSONL and per-line input readers, and the CLI).
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
import ingest  # noqa: E402


def gen_raw_texts(rng) -> list[str]:
    """A list of raw, un-normalized document texts (with edge-y unicode/ws)."""
    return pbt.lists(pbt.text(max_len=30), max_len=6)(rng)


SOURCES = ["s", "wiki", "books-v2", "code"]


class IngestPropertyTests(unittest.TestCase):
    def test_renormalizing_ingested_text_is_noop(self) -> None:
        # Property (1): normalize_text is idempotent on already-ingested text.
        def prop(raws: list[str]) -> bool:
            records = ingest.ingest_records(raws, "s")
            return all(R.normalize_text(rec.text) == rec.text for rec in records)

        pbt.for_all(gen_raw_texts, prop, label="idempotent-normalization")

    def test_count_equals_nonempty_normalized_inputs(self) -> None:
        # Property (2): output count == #inputs whose normalized form is non-empty.
        def prop(raws: list[str]) -> bool:
            expected = sum(1 for raw in raws if R.normalize_text(raw) != "")
            return len(ingest.ingest_records(raws, "s")) == expected

        pbt.for_all(gen_raw_texts, prop, label="count-preservation")

    def test_all_output_ids_unique(self) -> None:
        # Property (3): every emitted record has a distinct id, even for dup texts.
        def prop(raws: list[str]) -> bool:
            ids = [rec.id for rec in ingest.ingest_records(raws, "s")]
            return len(ids) == len(set(ids))

        pbt.for_all(gen_raw_texts, prop, label="id-uniqueness")

    def test_id_uniqueness_across_sources(self) -> None:
        def prop(raws: list[str]) -> bool:
            source = SOURCES[len(raws) % len(SOURCES)]
            ids = [rec.id for rec in ingest.ingest_records(raws, source)]
            return len(ids) == len(set(ids))

        pbt.for_all(gen_raw_texts, prop, label="id-uniqueness-multi-source")

    def test_write_then_read_roundtrips(self) -> None:
        # Property (4): write_records then read_records returns the same records.
        def prop(raws: list[str]) -> bool:
            records = ingest.ingest_records(raws, "s")
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "out.jsonl"
                R.write_records(path, records)
                loaded = R.read_records(path)
            return loaded == records

        pbt.for_all(gen_raw_texts, prop, runs=100, label="jsonl-roundtrip")

    def test_source_is_preserved(self) -> None:
        def prop(raws: list[str]) -> bool:
            source = SOURCES[len(raws) % len(SOURCES)]
            return all(
                rec.source == source for rec in ingest.ingest_records(raws, source)
            )

        pbt.for_all(gen_raw_texts, prop, label="source-preserved")


class IngestExampleTests(unittest.TestCase):
    def test_drops_empty_and_blank_documents(self) -> None:
        raws = ["hello", "", "   ", "\n\t\n", "world"]
        records = ingest.ingest_records(raws, "s")
        self.assertEqual([rec.text for rec in records], ["hello", "world"])

    def test_duplicate_texts_get_distinct_ids(self) -> None:
        records = ingest.ingest_records(["dup", "dup", "dup"], "s")
        self.assertEqual([rec.text for rec in records], ["dup", "dup", "dup"])
        self.assertEqual(len({rec.id for rec in records}), 3)

    def test_normalization_applied(self) -> None:
        # CRLF unified, trailing whitespace stripped, blank edges trimmed.
        (record,) = ingest.ingest_records(["\r\n  line1  \r\nline2\t\n\n"], "s")
        self.assertEqual(record.text, "  line1\nline2")

    def test_ids_are_stable(self) -> None:
        a = ingest.ingest_records(["a", "b"], "s")
        b = ingest.ingest_records(["a", "b"], "s")
        self.assertEqual([r.id for r in a], [r.id for r in b])

    def test_empty_input_yields_no_records(self) -> None:
        self.assertEqual(ingest.ingest_records([], "s"), [])
        self.assertEqual(ingest.ingest_records(["", "  "], "s"), [])

    def test_index_keys_id_not_position_in_output(self) -> None:
        # A dropped leading empty must not shift the ids of survivors: the id is
        # keyed on the original input index, not the output position.
        with_lead = ingest.ingest_records(["", "keep"], "s")
        self.assertEqual(len(with_lead), 1)
        # "keep" is at input index 1 here; verify the id matches that index.
        expected_id = R.make_id("s", 1, "keep")
        self.assertEqual(with_lead[0].id, expected_id)


class ReadInputTextsTests(unittest.TestCase):
    def test_reads_plain_text_one_doc_per_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "docs.txt"
            path.write_text("alpha\nbeta\n\ngamma\n", encoding="utf-8")
            texts = ingest.read_input_texts(path)
        self.assertEqual(texts, ["alpha", "beta", "", "gamma"])

    def test_reads_jsonl_text_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "docs.jsonl"
            path.write_text(
                json.dumps({"text": "one", "extra": 1})
                + "\n"
                + json.dumps({"text": "two"})
                + "\n",
                encoding="utf-8",
            )
            texts = ingest.read_input_texts(path)
        self.assertEqual(texts, ["one", "two"])

    def test_jsonl_missing_text_field_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.jsonl"
            path.write_text(json.dumps({"body": "x"}) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                ingest.read_input_texts(path)

    def test_jsonl_invalid_json_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.jsonl"
            path.write_text("{not json}\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                ingest.read_input_texts(path)


class CliTests(unittest.TestCase):
    def test_cli_summary_without_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "docs.txt"
            path.write_text("a\n\nb\n", encoding="utf-8")
            import io
            from contextlib import redirect_stdout

            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = ingest.main(["ingest.py", str(path), "--source", "s"])
            self.assertEqual(rc, 0)
            summary = json.loads(buf.getvalue())
        self.assertEqual(summary["raw"], 3)
        self.assertEqual(summary["ingested"], 2)
        self.assertEqual(summary["dropped"], 1)
        self.assertEqual(summary["source"], "s")

    def test_cli_writes_output_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "docs.txt"
            src.write_text("hello\nworld\n", encoding="utf-8")
            out = Path(tmp) / "out.jsonl"
            import io
            from contextlib import redirect_stdout

            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = ingest.main(
                    ["ingest.py", str(src), "--source", "wiki", "--output", str(out)]
                )
            self.assertEqual(rc, 0)
            loaded = R.read_records(out)
        self.assertEqual([r.text for r in loaded], ["hello", "world"])
        self.assertTrue(all(r.source == "wiki" for r in loaded))

    def test_cli_output_summary_uses_repo_relative_paths(self) -> None:
        # Committed output must never embed absolute paths. The summary path
        # printed for an in-repo output file must be repo-relative.
        out = _ROOT / "evals" / "tokenizer" / "probes.jsonl"  # any in-repo file
        import io
        from contextlib import redirect_stdout

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "docs.txt"
            src.write_text("x\n", encoding="utf-8")
            repo_out = _ROOT / "scripts" / "data" / "__pycache__" / "_ingest_tmp.jsonl"
            buf = io.StringIO()
            try:
                with redirect_stdout(buf):
                    ingest.main(
                        ["ingest.py", str(src), "--source", "s", "--output", str(repo_out)]
                    )
                summary = json.loads(buf.getvalue())
                self.assertFalse(summary["output"].startswith("/"))
                self.assertIn("scripts/data", summary["output"])
            finally:
                if repo_out.exists():
                    repo_out.unlink()
        del out


class IngestShardingTests(unittest.TestCase):
    def test_start_index_offsets_ids(self) -> None:
        records = ingest.ingest_records(["a", "b"], "s", start_index=10)
        self.assertEqual(
            [r.id for r in records],
            [R.make_id("s", 10, "a"), R.make_id("s", 11, "b")],
        )

    def test_offset_shards_have_disjoint_ids(self) -> None:
        # Re-sharding the SAME source: offsetting the second shard by the first
        # shard's document count keeps ids disjoint even for identical texts.
        shard1 = ingest.ingest_records(["alpha", "beta"], "web", start_index=0)
        shard2 = ingest.ingest_records(["alpha", "gamma"], "web", start_index=2)
        ids1 = {r.id for r in shard1}
        ids2 = {r.id for r in shard2}
        self.assertEqual(ids1 & ids2, set())

    def test_without_offset_same_source_shards_collide(self) -> None:
        # Documents the hazard the offset prevents: two shards both starting at
        # index 0 produce a colliding id for the same text at the same position.
        a = ingest.ingest_records(["alpha"], "web", start_index=0)
        b = ingest.ingest_records(["alpha"], "web", start_index=0)
        self.assertEqual(a[0].id, b[0].id)

    def test_cli_start_index(self) -> None:
        import io
        from contextlib import redirect_stdout

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "docs.txt"
            src.write_text("a\nb\n", encoding="utf-8")
            out = Path(tmp) / "out.jsonl"
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = ingest.main(
                    ["ingest.py", str(src), "--source", "s", "--start-index", "5", "--output", str(out)]
                )
            self.assertEqual(rc, 0)
            loaded = R.read_records(out)
        self.assertEqual(loaded[0].id, R.make_id("s", 5, "a"))

    def test_cli_rejects_negative_start_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "docs.txt"
            src.write_text("a\n", encoding="utf-8")
            with self.assertRaises(SystemExit):
                ingest.main(["ingest.py", str(src), "--source", "s", "--start-index", "-1"])


class RelPathTests(unittest.TestCase):
    def test_rel_in_repo_is_relative(self) -> None:
        rel = ingest._rel(_ROOT / "scripts" / "data" / "ingest.py")
        self.assertEqual(rel, "scripts/data/ingest.py")
        self.assertFalse(rel.startswith("/"))

    def test_rel_out_of_repo_falls_back_to_basename(self) -> None:
        # Paths outside the repo must not leak an absolute path into committed
        # output; _rel returns just the basename for them.
        rel = ingest._rel(Path("/var/tmp/some-outside-corpus.jsonl"))
        self.assertEqual(rel, "some-outside-corpus.jsonl")
        self.assertFalse(rel.startswith("/"))


if __name__ == "__main__":
    unittest.main()
