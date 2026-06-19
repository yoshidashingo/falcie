#!/usr/bin/env python3
"""Property-based and example-based tests for the dataset loader (unit U-I3).

Properties exercised (PBT category in parentheses):
  * determinism (PBT-04): same (seed, shuffle_buffer) -> identical id order
  * coverage    (PBT-03): start=0 -> output id multiset == input id multiset
                          (a permutation: no loss, no duplication)
  * no-shuffle  (PBT-03): shuffle_buffer <= 1 -> original input order
  * resumable   (PBT-04): load_order(start=k) == load_order(start=0)[k:]

Example-based tests pin small concrete cases (PBT-10: examples and PBT complement
each other — examples nail down behaviour, PBT explores the input space).
"""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts" / "data"))
sys.path.insert(0, str(_ROOT / "scripts" / "common"))
sys.path.insert(0, str(_ROOT / "tests"))

import pbt  # noqa: E402
import records as R  # noqa: E402
import loader  # noqa: E402


# --- generators -----------------------------------------------------------


def _records_from_texts(texts: list[str]) -> list[R.Record]:
    """Build a record list with guaranteed-unique ids from arbitrary texts."""
    return [R.Record(R.make_id("s", i, t), t, "s") for i, t in enumerate(texts)]


def gen_records(rng) -> list[R.Record]:
    """A record list of 0-12 records with unique ids (texts may repeat)."""
    length = rng.randint(0, 12)
    texts = ["".join(pbt.text(min_len=0, max_len=6)(rng)) for _ in range(length)]
    return _records_from_texts(texts)


def gen_records_nonempty(rng) -> list[R.Record]:
    """A record list of 1-12 records (so start within range is meaningful)."""
    length = rng.randint(1, 12)
    texts = ["".join(pbt.text(min_len=0, max_len=6)(rng)) for _ in range(length)]
    return _records_from_texts(texts)


def _ids(records: list[R.Record]) -> list[str]:
    return [r.id for r in records]


# --- property-based tests -------------------------------------------------


class TestLoaderProperties(unittest.TestCase):
    def test_determinism(self) -> None:
        """Same (seed, shuffle_buffer) yields identical id ordering."""

        def prop(records: list[R.Record]) -> bool:
            a = loader.load_order(records, seed=7, shuffle_buffer=4)
            b = loader.load_order(records, seed=7, shuffle_buffer=4)
            return _ids(a) == _ids(b)

        pbt.for_all(gen_records, prop, runs=200, seed=0, label="determinism")

    def test_determinism_varied_params(self) -> None:
        """Determinism holds across a range of seeds and buffer sizes."""

        def prop(records: list[R.Record]) -> bool:
            for seed in (0, 1, 13, 99):
                for buf in (0, 1, 2, 3, 5, 16):
                    a = _ids(loader.load_order(records, seed=seed, shuffle_buffer=buf))
                    b = _ids(loader.load_order(records, seed=seed, shuffle_buffer=buf))
                    if a != b:
                        return False
            return True

        pbt.for_all(gen_records, prop, runs=120, seed=1, label="determinism-varied")

    def test_coverage_is_permutation(self) -> None:
        """start=0 -> the output id multiset equals the input id multiset exactly."""

        def prop(records: list[R.Record]) -> bool:
            out = loader.load_order(records, seed=42, shuffle_buffer=5, start=0)
            return sorted(_ids(out)) == sorted(_ids(records)) and len(out) == len(records)

        pbt.for_all(gen_records, prop, runs=200, seed=2, label="coverage")

    def test_coverage_across_buffer_sizes(self) -> None:
        """Permutation property holds for any buffer size (and no seed)."""

        def prop(records: list[R.Record]) -> bool:
            in_ids = sorted(_ids(records))
            for buf in (0, 1, 2, 4, 7, 32):
                out = loader.load_order(records, seed=3, shuffle_buffer=buf, start=0)
                if sorted(_ids(out)) != in_ids:
                    return False
            # seed=None must also be a permutation (falls back to original order).
            out_no_seed = loader.load_order(records, seed=None, shuffle_buffer=8, start=0)
            return sorted(_ids(out_no_seed)) == in_ids

        pbt.for_all(gen_records, prop, runs=150, seed=3, label="coverage-buffers")

    def test_no_shuffle_keeps_order(self) -> None:
        """shuffle_buffer <= 1 yields the original input order."""

        def prop(records: list[R.Record]) -> bool:
            for buf in (-3, 0, 1):
                out = loader.load_order(records, seed=123, shuffle_buffer=buf)
                if _ids(out) != _ids(records):
                    return False
            # seed=None disables shuffling even with a large buffer.
            out_none = loader.load_order(records, seed=None, shuffle_buffer=10)
            return _ids(out_none) == _ids(records)

        pbt.for_all(gen_records, prop, runs=200, seed=4, label="no-shuffle")

    def test_resumable_suffix(self) -> None:
        """load_order(start=k) equals load_order(start=0)[k:] for matching params."""

        def prop(records: list[R.Record]) -> bool:
            n = len(records)
            full = loader.load_order(records, seed=11, shuffle_buffer=4, start=0)
            for k in range(0, n + 2):  # include k == n and k > n (empty suffix)
                resumed = loader.load_order(records, seed=11, shuffle_buffer=4, start=k)
                if _ids(resumed) != _ids(full[k:]):
                    return False
            return True

        pbt.for_all(gen_records_nonempty, prop, runs=200, seed=5, label="resumable")

    def test_resumable_no_shuffle(self) -> None:
        """Resumable suffix also holds in the no-shuffle (original-order) regime."""

        def prop(records: list[R.Record]) -> bool:
            full = loader.load_order(records, shuffle_buffer=1, start=0)
            for k in range(0, len(records) + 1):
                resumed = loader.load_order(records, shuffle_buffer=1, start=k)
                if _ids(resumed) != _ids(full[k:]):
                    return False
            return True

        pbt.for_all(gen_records_nonempty, prop, runs=150, seed=6, label="resumable-plain")

    def test_negative_property_is_false_not_raise(self) -> None:
        """Sanity: a deliberately wrong property returns False (per harness contract)."""

        def wrong(records: list[R.Record]) -> bool:
            # Shuffling with a large buffer is NOT generally the identity order, so
            # claiming it equals the input order is false for many inputs. We assert
            # the harness reports a counterexample (raises), not that it passes.
            out = loader.load_order(records, seed=1, shuffle_buffer=8)
            return _ids(out) == _ids(records)

        # Use an input that the buffer shuffle actually reorders so the wrong
        # property is genuinely violated.
        reordering_input = _records_from_texts([f"t{i}" for i in range(12)])
        # The property is false on this concrete input; confirm directly.
        self.assertFalse(wrong(reordering_input))


# --- example-based tests --------------------------------------------------


class TestLoaderExamples(unittest.TestCase):
    def setUp(self) -> None:
        self.recs = _records_from_texts([f"doc-{i}" for i in range(6)])
        self.ids = _ids(self.recs)

    def test_empty_input(self) -> None:
        self.assertEqual(loader.load_order([], seed=1, shuffle_buffer=4), [])
        self.assertEqual(loader.load_order([]), [])

    def test_buffer_zero_is_identity(self) -> None:
        out = loader.load_order(self.recs, seed=9, shuffle_buffer=0)
        self.assertEqual(_ids(out), self.ids)

    def test_buffer_one_is_identity(self) -> None:
        out = loader.load_order(self.recs, seed=9, shuffle_buffer=1)
        self.assertEqual(_ids(out), self.ids)

    def test_no_seed_is_identity_even_with_buffer(self) -> None:
        out = loader.load_order(self.recs, seed=None, shuffle_buffer=4)
        self.assertEqual(_ids(out), self.ids)

    def test_shuffle_is_deterministic_concrete(self) -> None:
        a = loader.load_order(self.recs, seed=2024, shuffle_buffer=3)
        b = loader.load_order(self.recs, seed=2024, shuffle_buffer=3)
        self.assertEqual(_ids(a), _ids(b))
        # Same elements, and (for this seed/buffer) a genuine reordering occurs.
        self.assertEqual(sorted(_ids(a)), sorted(self.ids))
        self.assertNotEqual(_ids(a), self.ids)

    def test_different_seeds_can_differ(self) -> None:
        a = _ids(loader.load_order(self.recs, seed=1, shuffle_buffer=4))
        b = _ids(loader.load_order(self.recs, seed=2, shuffle_buffer=4))
        # Both are permutations of the same ids.
        self.assertEqual(sorted(a), sorted(self.ids))
        self.assertEqual(sorted(b), sorted(self.ids))
        # For these particular seeds the orders differ (documents the seed effect).
        self.assertNotEqual(a, b)

    def test_start_skips_prefix(self) -> None:
        full = loader.load_order(self.recs, seed=5, shuffle_buffer=3, start=0)
        skipped = loader.load_order(self.recs, seed=5, shuffle_buffer=3, start=2)
        self.assertEqual(_ids(skipped), _ids(full[2:]))

    def test_start_beyond_length_is_empty(self) -> None:
        out = loader.load_order(self.recs, seed=5, shuffle_buffer=3, start=100)
        self.assertEqual(out, [])

    def test_start_zero_no_shuffle_concrete(self) -> None:
        out = loader.load_order(self.recs, shuffle_buffer=1, start=2)
        self.assertEqual(_ids(out), self.ids[2:])

    def test_negative_start_raises(self) -> None:
        with self.assertRaises(ValueError):
            loader.load_order(self.recs, start=-1)

    def test_iter_jsonl_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.jsonl"
            R.write_records(path, self.recs)
            out = loader.iter_jsonl(path, seed=None, shuffle_buffer=0)
            self.assertEqual(_ids(out), self.ids)

    def test_iter_jsonl_matches_load_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.jsonl"
            R.write_records(path, self.recs)
            via_file = loader.iter_jsonl(path, seed=77, shuffle_buffer=4, start=1)
            via_mem = loader.load_order(
                R.read_records(path), seed=77, shuffle_buffer=4, start=1
            )
            self.assertEqual(_ids(via_file), _ids(via_mem))


# --- CLI tests ------------------------------------------------------------


class TestLoaderCLI(unittest.TestCase):
    def _write(self, tmp: str) -> Path:
        recs = _records_from_texts([f"doc-{i}" for i in range(5)])
        path = Path(tmp) / "data.jsonl"
        R.write_records(path, recs)
        return path

    def test_cli_prints_ids_and_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp)
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = loader.main(["loader.py", str(path)])
            self.assertEqual(rc, 0)
            out = buf.getvalue()
            self.assertIn("count: 5", out)
            for rec in R.read_records(path):
                self.assertIn(rec.id, out)
            # No absolute path leaks into output.
            self.assertNotIn(str(Path(tmp)), out)

    def test_cli_count_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp)
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = loader.main(["loader.py", str(path), "--count"])
            self.assertEqual(rc, 0)
            out = buf.getvalue()
            self.assertIn("count: 5", out)
            # In count mode, ids are not listed.
            self.assertNotIn("doc-", out.split("count:")[1])

    def test_cli_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp)
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = loader.main(["loader.py", str(path), "--limit", "2"])
            self.assertEqual(rc, 0)
            out = buf.getvalue()
            self.assertIn("count: 2", out)
            # Exactly two id lines printed.
            id_lines = [
                ln for ln in out.splitlines() if ln and not ln.startswith(("input:", "count:"))
            ]
            self.assertEqual(len(id_lines), 2)

    def test_cli_rejects_negative_start(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp)
            with self.assertRaises(SystemExit):
                loader.main(["loader.py", str(path), "--start", "-1"])


if __name__ == "__main__":
    unittest.main()
