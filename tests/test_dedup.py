#!/usr/bin/env python3
"""Property-based and example-based tests for the dedup stage (unit U-D2).

Properties exercised (PBT category in parentheses):
  * idempotence (PBT-04): dedup(dedup(x)) == dedup(x) (compared by id lists)
  * invariant   (PBT-03): output is a subsequence of input (order preserved)
  * invariant   (PBT-03): len(output) <= len(input)
  * oracle      (PBT-05): exact dedup collapses equal-text records to one
  * oracle      (PBT-05): near-dup threshold 1.0 behaves like exact dedup on
                          identical texts

Example-based tests live alongside the property tests in this file (PBT-10: the
two complement each other — examples pin concrete behaviour, PBT explores the space).
"""

from __future__ import annotations

import io
import itertools
import random
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts" / "data"))
sys.path.insert(0, str(_ROOT / "tests"))

import records as R  # noqa: E402
import pbt  # noqa: E402
import dedup  # noqa: E402

# Alphabet for near-duplicate generators: a small, fully-overlapping pool so the
# random unicode problem (disjoint shingle sets -> ~0 Jaccard) does not happen.
_NEAR_DUP_ALPHA = "abcdefghijklmnopqrstuvwxyz0123456789 "

# Moderate threshold used by the near-dup property tests. The perturbation below
# (single-char prepend/append on a 40-80 char base) keeps every pair's char-5-gram
# Jaccard in ~[0.97, 0.99] — comfortably above this threshold but strictly < 1.0.
_NEAR_DUP_THRESHOLD = 0.6
_NEAR_DUP_NGRAM = 5


def _perturbed_pair(rng: random.Random) -> tuple[str, str]:
    """A base string and a high-but-<1.0 Jaccard copy (one char prepended/appended).

    A single-character prepend/append on a long base perturbs only the n-grams that
    touch the new character, so ``char_ngrams`` Jaccard stays very high (~0.97-0.99
    for n=5) yet never reaches 1.0 (the shingle sets differ). This is exactly the
    near-duplicate-but-not-exact-duplicate structure that the near-dup DROP path
    needs and that random unicode never produces.
    """
    base_len = rng.randint(40, 80)
    base = "".join(rng.choice(_NEAR_DUP_ALPHA) for _ in range(base_len))
    extra = rng.choice(_NEAR_DUP_ALPHA)
    copy = (base + extra) if rng.random() < 0.5 else (extra + base)
    return base, copy


def gen_near_dup_records(rng: random.Random) -> list[R.Record]:
    """Record list containing at least one high-Jaccard near-duplicate pair.

    Each list has 1-3 near-dup pairs (base + perturbed copy) plus 0-3 unrelated
    filler strings, shuffled. Ids are unique via ``make_id`` with the enumeration
    index, so dedup's exact-hash pass never collapses anything for us — only the
    near-dup pass can drop a record, which is the path under test.
    """
    texts: list[str] = []
    for _ in range(rng.randint(1, 3)):
        base, copy = _perturbed_pair(rng)
        texts.append(base)
        texts.append(copy)
    for _ in range(rng.randint(0, 3)):
        length = rng.randint(40, 80)
        texts.append("".join(rng.choice(_NEAR_DUP_ALPHA) for _ in range(length)))
    rng.shuffle(texts)
    return [R.Record(R.make_id("s", i, t), t, "s") for i, t in enumerate(texts)]


def gen_records(rng) -> list[R.Record]:
    """Generate a record list with UNIQUE ids but possibly DUPLICATE texts.

    The index passed to ``make_id`` guarantees unique ids even when two records
    carry identical text, which is exactly what exercises dedup. Texts are drawn
    from a small pool so collisions (and near-collisions) actually occur.
    """
    texts = pbt.lists(pbt.text(max_len=30), max_len=6)(rng)
    return [R.Record(R.make_id("s", i, t), t, "s") for i, t in enumerate(texts)]


def _ids(records: list[R.Record]) -> list[str]:
    return [r.id for r in records]


def _is_subsequence(sub: list[R.Record], whole: list[R.Record]) -> bool:
    """True iff ``sub``'s ids appear in ``whole`` in the same relative order."""
    it = iter(whole)
    return all(any(r.id == s.id for r in it) for s in sub)


class TestDedupProperties(unittest.TestCase):
    def test_idempotence(self) -> None:
        # dedup is a fixed point after one pass: a second pass changes nothing.
        pbt.for_all(
            gen_records,
            lambda recs: _ids(dedup.dedup(dedup.dedup(recs))) == _ids(dedup.dedup(recs)),
            label="dedup(dedup(x)) == dedup(x)",
        )

    def test_idempotence_with_near_dup(self) -> None:
        pbt.for_all(
            gen_records,
            lambda recs: _ids(dedup.dedup(dedup.dedup(recs, 0.6), 0.6))
            == _ids(dedup.dedup(recs, 0.6)),
            label="near-dup dedup is idempotent",
        )

    def test_output_is_subsequence(self) -> None:
        pbt.for_all(
            gen_records,
            lambda recs: _is_subsequence(dedup.dedup(recs), recs),
            label="output is a subsequence of input (exact)",
        )

    def test_output_is_subsequence_near_dup(self) -> None:
        pbt.for_all(
            gen_records,
            lambda recs: _is_subsequence(dedup.dedup(recs, 0.7), recs),
            label="output is a subsequence of input (near-dup)",
        )

    def test_output_no_longer_than_input(self) -> None:
        pbt.for_all(
            gen_records,
            lambda recs: len(dedup.dedup(recs)) <= len(recs),
            label="len(output) <= len(input) (exact)",
        )

    def test_output_no_longer_than_input_near_dup(self) -> None:
        pbt.for_all(
            gen_records,
            lambda recs: len(dedup.dedup(recs, 0.5)) <= len(recs),
            label="len(output) <= len(input) (near-dup)",
        )

    def test_exact_collapses_equal_texts(self) -> None:
        # Oracle: the number of kept records equals the number of distinct texts.
        def matches_distinct_count(recs: list[R.Record]) -> bool:
            kept = dedup.dedup(recs)
            distinct_texts = len({r.text for r in recs})
            return len(kept) == distinct_texts

        pbt.for_all(
            gen_records,
            matches_distinct_count,
            label="exact dedup keeps one per distinct text",
        )

    def test_no_duplicate_hashes_in_output(self) -> None:
        # The surviving records all have distinct content hashes.
        def distinct_hashes(recs: list[R.Record]) -> bool:
            kept = dedup.dedup(recs)
            hashes = [R.content_hash(r.text) for r in kept]
            return len(hashes) == len(set(hashes))

        pbt.for_all(gen_records, distinct_hashes, label="kept records have distinct hashes")

    def test_threshold_one_matches_exact_on_identical_texts(self) -> None:
        # With threshold 1.0, two records with *identical* text must collapse to
        # one. Distinct texts always have Jaccard < 1.0 here, so the kept count
        # equals the number of distinct texts — same oracle as exact dedup.
        def matches_distinct_count(recs: list[R.Record]) -> bool:
            kept = dedup.dedup(recs, near_dup_threshold=1.0)
            distinct_texts = len({r.text for r in recs})
            return len(kept) == distinct_texts

        pbt.for_all(
            gen_records,
            matches_distinct_count,
            label="threshold=1.0 collapses identical texts like exact",
        )

    def test_near_dup_pair_drops_at_least_one(self) -> None:
        # Every generated list contains a high-Jaccard near-dup pair, so with a
        # moderate threshold at least one record MUST be dropped. This kills the
        # mutant that disables the near-dup ``if any(...)`` drop (which would keep
        # every record, since the exact-hash pass never fires for these unique-id,
        # distinct-text records).
        def drops_something(recs: list[R.Record]) -> bool:
            kept = dedup.dedup(
                recs, near_dup_threshold=_NEAR_DUP_THRESHOLD, ngram=_NEAR_DUP_NGRAM
            )
            return len(kept) < len(recs)

        pbt.for_all(
            gen_near_dup_records,
            drops_something,
            label="near-dup pair forces at least one drop",
        )

    def test_kept_set_has_no_residual_near_dups(self) -> None:
        # After near-dup dedup, no two surviving records may have pairwise Jaccard
        # >= threshold. This pins the drop semantics: a mutant that flips ``>=`` to
        # ``>`` (or weakens the comparison) would leave a residual pair whose Jaccard
        # equals/exceeds the threshold in the kept set.
        def no_residual(recs: list[R.Record]) -> bool:
            kept = dedup.dedup(
                recs, near_dup_threshold=_NEAR_DUP_THRESHOLD, ngram=_NEAR_DUP_NGRAM
            )
            for x, y in itertools.combinations(kept, 2):
                similarity = R.jaccard(
                    R.char_ngrams(x.text, _NEAR_DUP_NGRAM),
                    R.char_ngrams(y.text, _NEAR_DUP_NGRAM),
                )
                if similarity >= _NEAR_DUP_THRESHOLD:
                    return False
            return True

        pbt.for_all(
            gen_near_dup_records,
            no_residual,
            label="kept set has no pairwise Jaccard >= threshold",
        )


class TestDedupNearDupBoundary(unittest.TestCase):
    """Exact-boundary examples that kill ``>=`` -> ``>`` on the near-dup comparison."""

    def _recs(self, texts: list[str]) -> list[R.Record]:
        return [R.Record(R.make_id("s", i, t), t, "s") for i, t in enumerate(texts)]

    def test_jaccard_exactly_at_threshold_drops_second(self) -> None:
        # With ngram=1, char_ngrams is the set of distinct characters. "abcd" -> the
        # set {a,b,c,d}; "abce" -> {a,b,c,e}. Intersection {a,b,c} has size 3, union
        # {a,b,c,d,e} has size 5, so Jaccard == 3/5 == 0.6 EXACTLY. At threshold 0.6
        # the second record is dropped because 0.6 >= 0.6; a mutant using ``>`` would
        # keep it (0.6 > 0.6 is False), so this example fails under that mutant.
        a, b = "abcd", "abce"
        self.assertEqual(
            R.jaccard(R.char_ngrams(a, 1), R.char_ngrams(b, 1)),
            0.6,
            msg="precondition: the two texts must have Jaccard exactly 0.6 at n=1",
        )
        recs = self._recs([a, b])
        kept = dedup.dedup(recs, near_dup_threshold=0.6, ngram=1)
        self.assertEqual([r.text for r in kept], [a])
        self.assertEqual(kept[0].id, recs[0].id)

    def test_jaccard_just_below_threshold_keeps_second(self) -> None:
        # Companion to the boundary case: when Jaccard is strictly below threshold the
        # second record survives. "abcd"/"abce" Jaccard is 0.6; a threshold just above
        # it (0.61) must NOT drop. This pins the inequality direction so the boundary
        # test above cannot be satisfied by an always-drop mutant.
        a, b = "abcd", "abce"
        recs = self._recs([a, b])
        kept = dedup.dedup(recs, near_dup_threshold=0.61, ngram=1)
        self.assertEqual([r.text for r in kept], [a, b])


class TestDedupCLI(unittest.TestCase):
    """Exercise ``dedup.main`` argument validation, JSONL output, and path printing."""

    def test_threshold_out_of_range_exits(self) -> None:
        # argparse ``parser.error`` raises SystemExit(2) for an out-of-[0,1] threshold.
        with self.assertRaises(SystemExit) as ctx:
            dedup.main(["dedup", "nonexistent.jsonl", "--near-dup-threshold", "1.5"])
        self.assertEqual(ctx.exception.code, 2)

    def test_ngram_zero_exits(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            dedup.main(["dedup", "nonexistent.jsonl", "--ngram", "0"])
        self.assertEqual(ctx.exception.code, 2)

    def test_valid_run_writes_jsonl_and_prints_relative_path(self) -> None:
        # Use a temp dir INSIDE the repo so ``_rel`` returns a true repo-relative path
        # (a temp dir outside the repo would fall back to the basename and not test the
        # relative_to branch). Confirms: exact dedup ran (two "alpha" collapse to one),
        # JSONL was written and reloads cleanly, and the printed output path is a
        # repo-relative (non-absolute) string equal to ``relative_to(ROOT)``.
        with tempfile.TemporaryDirectory(dir=str(_ROOT)) as tmp:
            tmp_dir = Path(tmp)
            input_path = tmp_dir / "in.jsonl"
            output_path = tmp_dir / "out.jsonl"
            R.write_records(
                input_path,
                [
                    R.Record("id1", "alpha", "s"),
                    R.Record("id2", "alpha", "s"),
                    R.Record("id3", "beta", "s"),
                ],
            )

            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = dedup.main(["dedup", str(input_path), "--output", str(output_path)])
            stdout = buffer.getvalue()

            self.assertEqual(code, 0)
            self.assertTrue(output_path.exists())

            kept = R.read_records(output_path)
            self.assertEqual([(r.id, r.text) for r in kept], [("id1", "alpha"), ("id3", "beta")])

            output_lines = [
                line for line in stdout.splitlines() if line.startswith("output:")
            ]
            self.assertEqual(len(output_lines), 1)
            printed = output_lines[0].split("output:", 1)[1].strip()
            self.assertFalse(Path(printed).is_absolute())
            self.assertEqual(printed, str(output_path.resolve().relative_to(dedup.ROOT)))
            # Summary counts are correct: two of three records kept, one removed.
            self.assertIn("kept: 2", stdout)
            self.assertIn("removed: 1", stdout)


class TestDedupExamples(unittest.TestCase):
    def _recs(self, texts: list[str]) -> list[R.Record]:
        return [R.Record(R.make_id("s", i, t), t, "s") for i, t in enumerate(texts)]

    def test_identical_texts_collapse_to_first(self) -> None:
        recs = self._recs(["alpha", "alpha", "beta", "alpha"])
        kept = dedup.dedup(recs)
        # Only the first "alpha" and the first "beta" survive, in input order.
        self.assertEqual([r.text for r in kept], ["alpha", "beta"])
        self.assertEqual(kept[0].id, recs[0].id)
        self.assertEqual(kept[1].id, recs[2].id)

    def test_empty_input(self) -> None:
        self.assertEqual(dedup.dedup([]), [])

    def test_all_unique_passthrough(self) -> None:
        recs = self._recs(["a", "b", "c", "d"])
        kept = dedup.dedup(recs)
        self.assertEqual(_ids(kept), _ids(recs))

    def test_order_preserved(self) -> None:
        recs = self._recs(["x", "y", "x", "z", "y"])
        kept = dedup.dedup(recs)
        self.assertEqual([r.text for r in kept], ["x", "y", "z"])

    def test_near_dup_drops_similar(self) -> None:
        # Two long, near-identical strings: high Jaccard so the second is dropped.
        a = "the quick brown fox jumps over the lazy dog"
        b = "the quick brown fox jumps over the lazy dOg"
        recs = self._recs([a, b, "completely different content here entirely"])
        kept = dedup.dedup(recs, near_dup_threshold=0.7, ngram=5)
        self.assertEqual(len(kept), 2)
        self.assertEqual(kept[0].text, a)  # first of the near-dup pair kept
        self.assertEqual(kept[1].text, recs[2].text)

    def test_near_dup_keeps_dissimilar(self) -> None:
        recs = self._recs(["aaaaaaaaaa", "zzzzzzzzzz", "mmmmmmmmmm"])
        kept = dedup.dedup(recs, near_dup_threshold=0.5, ngram=3)
        self.assertEqual(len(kept), 3)

    def test_near_dup_threshold_none_is_exact_only(self) -> None:
        # Near-identical but not byte-identical texts survive when threshold is None.
        a = "the quick brown fox jumps over the lazy dog"
        b = "the quick brown fox jumps over the lazy dOg"
        recs = self._recs([a, b])
        kept = dedup.dedup(recs, near_dup_threshold=None)
        self.assertEqual(len(kept), 2)

    def test_threshold_one_keeps_near_but_not_identical(self) -> None:
        # Threshold 1.0 only collapses truly identical texts; near-dups survive.
        a = "the quick brown fox jumps over the lazy dog"
        b = "the quick brown fox jumps over the lazy dOg"
        recs = self._recs([a, b, a])
        kept = dedup.dedup(recs, near_dup_threshold=1.0)
        self.assertEqual([r.text for r in kept], [a, b])

    def test_exact_runs_even_when_near_dup_enabled(self) -> None:
        # Identical texts are caught by the exact pass before shingling.
        recs = self._recs(["same", "same", "same"])
        kept = dedup.dedup(recs, near_dup_threshold=0.9)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].id, recs[0].id)


if __name__ == "__main__":
    unittest.main()
