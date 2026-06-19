#!/usr/bin/env python3
"""Tests for the contamination check stage (unit U-D4).

Property-based tests (PBT) and example-based tests are kept in the same file but
are distinct ``unittest`` methods (they complement each other):

  * (1) identity      — a record whose text equals a benchmark is always flagged
  * (2) disjoint      — a record sharing no n-grams (disjoint alphabet) is never flagged
  * (3) monotonicity  — lowering the threshold flags a superset of records
  * (4) subsequence   — ``remove_contaminated`` output is a subsequence of its input
  * (5) score range   — ``contamination_score`` is always within [0, 1]
  * (6) consistency   — the stored flag and score never disagree (exact-match OR
                        (benchmarks present AND score >= threshold))

Several tests deliberately build records as *perturbed copies* of benchmark texts
(a benchmark plus a 1-3 char edit) so the n-gram Jaccard lands strictly between 0
and 1. That is what actually exercises the ``score >= threshold`` rule: records
that merely equal a benchmark are flagged by the exact-match rule regardless of
threshold, leaving the threshold comparison (and its ``>=`` boundary) untested.
"""

from __future__ import annotations

import contextlib
import io

# The pbt shrinker treats a generated tuple as a shrinkable structure and may
# reduce it to a shorter/empty tuple. Properties that unpack a fixed-shape case
# therefore guard the shape first and treat a malformed (shrunk) tuple as a
# vacuously-passing input, so shrinking cannot fabricate a false counterexample.
_OK = True

import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts" / "data"))
sys.path.insert(0, str(_ROOT / "tests"))

import records as R  # noqa: E402
import pbt  # noqa: E402
import contamination  # noqa: E402


def gen_records(rng):
    """Generate a list of Records with guaranteed-unique ids (index in make_id)."""
    texts = pbt.lists(pbt.text(max_len=30), max_len=6)(rng)
    return [R.Record(R.make_id("s", i, t), t, "s") for i, t in enumerate(texts)]


def gen_benchmarks(rng):
    """Generate a small list of benchmark texts."""
    return pbt.lists(pbt.text(max_len=30), max_len=5)(rng)


# Disjoint alphabets: record texts use one set of codepoints, benchmarks another,
# so they can never share a character n-gram (property 2). The two alphabets must
# be *truly* disjoint — a shared character (e.g. a space) would let an n-gram of
# spaces overlap, short-circuiting the premise. So only one alphabet carries the
# space; the record alphabet is pure letters.
_REC_ALPHA = "abcdefg"
_BENCH_ALPHA = "0123456 "


def gen_disjoint_records(rng):
    """Records drawn only from ``_REC_ALPHA``."""
    n = pbt.integers(0, 6)(rng)
    out = []
    for i in range(n):
        length = pbt.integers(0, 20)(rng)
        text = "".join(rng.choice(_REC_ALPHA) for _ in range(length))
        out.append(R.Record(R.make_id("s", i, text), text, "s"))
    return out


def gen_disjoint_benchmarks(rng):
    """Benchmark texts drawn only from ``_BENCH_ALPHA`` (non-empty each)."""
    n = pbt.integers(1, 5)(rng)
    out = []
    for _ in range(n):
        length = pbt.integers(1, 20)(rng)
        out.append("".join(rng.choice(_BENCH_ALPHA) for _ in range(length)))
    return out


# Alphabet for benchmark *base* texts that overlap a perturbed record meaningfully.
# Pure readable ASCII so the char n-grams of a base and its small edit share most
# shingles (yielding an intermediate, non-exact Jaccard).
_BASE_ALPHA = "abcdefghijklmnopqrstuvwxyz "


def _gen_base_text(rng, min_len=12, max_len=30):
    length = pbt.integers(min_len, max_len)(rng)
    return "".join(rng.choice(_BASE_ALPHA) for _ in range(length))


def _perturb(rng, base):
    """Apply a small edit to ``base`` so the result is a near (non-exact) copy.

    Three modes — append 1-3 novel chars, substitute one interior char, or drop
    the last char — each preserving high n-gram overlap with ``base`` while making
    the texts unequal. The appended/substituted characters are drawn from a set
    disjoint from ``_BASE_ALPHA`` so the edit cannot accidentally reproduce ``base``.
    """
    mode = pbt.integers(0, 2)(rng)
    if mode == 0:
        k = pbt.integers(1, 3)(rng)
        return base + "".join(rng.choice("XYZ") for _ in range(k))
    if mode == 1:
        if not base:
            return base + "X"
        i = pbt.integers(0, len(base) - 1)(rng)
        repl = "Q" if base[i] != "Q" else "W"
        return base[:i] + repl + base[i + 1 :]
    return base[:-1] if base else base + "X"


def gen_perturbed_case(rng):
    """A (records, benchmarks) case where records are *perturbed* benchmark copies.

    Each benchmark gets one record that is a small edit of it, so the record's
    n-gram Jaccard vs that benchmark is high but strictly below 1.0 — exactly the
    regime that exercises the ``score >= threshold`` rule (not the exact-match
    rule). A couple of plain records are mixed in as non-contaminated noise.
    """
    n_bench = pbt.integers(1, 3)(rng)
    benchmarks = [_gen_base_text(rng) for _ in range(n_bench)]
    records = []
    for j, base in enumerate(benchmarks):
        rec_text = _perturb(rng, base)
        records.append(R.Record(R.make_id("r", j, rec_text), rec_text, "r"))
    # A little extra noise drawn from the same readable alphabet (usually low score).
    for k in range(pbt.integers(0, 2)(rng)):
        noise = _gen_base_text(rng, 0, 10)
        records.append(R.Record(R.make_id("n", k, noise + f"#{k}"), noise + f"#{k}", "n"))
    return records, benchmarks


class ContaminationProperties(unittest.TestCase):
    def test_identity_flagged(self) -> None:
        """(1) A record whose text equals a benchmark text is always flagged.

        The generated ``records`` list is used directly: each generated record is
        re-emitted as a benchmark, so the property asserts over real generated data
        (not just a hand-built record) — a code path the prior version ignored.
        """

        def prop(case) -> bool:
            if not isinstance(case, tuple) or len(case) != 2:
                return _OK
            records, benchmarks = case
            if not records:
                return _OK
            # Every generated record's own text is treated as a benchmark, so each
            # must exact-match and be flagged regardless of threshold.
            bench_texts = list(benchmarks) + [rec.text for rec in records]
            flagged = contamination.flag_contaminated(records, bench_texts)
            return all(rec.meta["contaminated"] is True for rec in flagged)

        def gen(rng):
            return (gen_records(rng), gen_benchmarks(rng))

        pbt.for_all(gen, prop, label="identity")

    def test_disjoint_never_flagged(self) -> None:
        """(2) A record sharing no n-grams with any benchmark is never flagged."""

        def prop(case) -> bool:
            if not isinstance(case, tuple) or len(case) != 2:
                return _OK
            records, benchmarks = case
            # Premise: every benchmark is non-empty and the record/benchmark
            # alphabets are disjoint. An empty string exact-matches another empty
            # string (a legitimate contamination), so empties void the premise. If
            # shrinking introduced an empty text or a shared character the premise
            # no longer holds and the property is vacuously true.
            if not benchmarks or any(b == "" for b in benchmarks):
                return _OK
            if any(r.text == "" for r in records):
                return _OK
            rec_chars = set("".join(r.text for r in records))
            bench_chars = set("".join(benchmarks))
            if rec_chars & bench_chars:
                return _OK
            flagged = contamination.flag_contaminated(records, benchmarks)
            return all(rec.meta["contaminated"] is False for rec in flagged)

        def gen(rng):
            return (gen_disjoint_records(rng), gen_disjoint_benchmarks(rng))

        pbt.for_all(gen, prop, label="disjoint")

    def test_threshold_monotonicity(self) -> None:
        """(3) Lowering the threshold flags a superset: flagged(low) >= flagged(high).

        Records are *perturbed* copies of the benchmarks, so their score is strictly
        between 0 and 1 and the ``score >= threshold`` rule (not exact-match) decides
        membership. That makes the threshold actually load-bearing: with random low
        and high thresholds, the low set must always contain the high set.
        """

        def prop(case) -> bool:
            if not isinstance(case, tuple) or len(case) != 4:
                return _OK
            records, benchmarks, t_low, t_high = case
            lo, hi = (t_low, t_high) if t_low <= t_high else (t_high, t_low)
            low_flag = {
                rec.id
                for rec in contamination.flag_contaminated(records, benchmarks, lo)
                if rec.meta["contaminated"]
            }
            high_flag = {
                rec.id
                for rec in contamination.flag_contaminated(records, benchmarks, hi)
                if rec.meta["contaminated"]
            }
            return high_flag <= low_flag

        def gen(rng):
            records, benchmarks = gen_perturbed_case(rng)
            t_low = pbt.integers(0, 100)(rng) / 100.0
            t_high = pbt.integers(0, 100)(rng) / 100.0
            return (records, benchmarks, t_low, t_high)

        pbt.for_all(gen, prop, label="monotonicity")

    def test_threshold_monotonicity_strictly_larger(self) -> None:
        """(3, strict) A constructed case where lowering the threshold flags a
        STRICTLY larger set — proving the threshold rule (not exact-match) drives
        membership. Kills the mutant that ignores ``threshold`` entirely.
        """
        # A perturbed copy of the benchmark: appended chars push the score below 1.0
        # but well above a low threshold. At threshold 0.99 it is NOT flagged; at
        # threshold 0.10 it IS. So the low-threshold flag set is strictly larger.
        bench = "the quick brown fox jumps over the lazy dog"
        rec = R.Record(R.make_id("s", 0, bench + "XYZ"), bench + "XYZ", "s")
        low = contamination.flag_contaminated([rec], [bench], 0.10)
        high = contamination.flag_contaminated([rec], [bench], 0.99)
        self.assertTrue(low[0].meta["contaminated"])
        self.assertFalse(high[0].meta["contaminated"])
        # And it is genuinely the threshold rule, not exact-match.
        score = low[0].meta["contamination_score"]
        self.assertLess(score, 1.0)
        self.assertGreater(score, 0.10)

    def test_remove_is_subsequence(self) -> None:
        """(4) remove_contaminated output is a subsequence of the input."""

        def prop(case) -> bool:
            if not isinstance(case, tuple) or len(case) != 2:
                return _OK
            records, benchmarks = case
            kept = contamination.remove_contaminated(records, benchmarks)
            kept_ids = [rec.id for rec in kept]
            input_ids = [rec.id for rec in records]
            # Subsequence check: kept_ids appears in order within input_ids.
            it = iter(input_ids)
            return all(any(k == x for x in it) for k in kept_ids)

        def gen(rng):
            records = gen_records(rng)
            benchmarks = gen_benchmarks(rng)
            # Mix in benchmark-derived records to ensure some get removed.
            if benchmarks:
                records = list(records) + [
                    R.Record(R.make_id("b", i, b), b, "b")
                    for i, b in enumerate(benchmarks)
                ]
            return (records, benchmarks)

        pbt.for_all(gen, prop, label="subsequence")

    def test_score_in_unit_interval(self) -> None:
        """(5) contamination_score is always in [0, 1].

        Half of the generated cases are *perturbed* benchmark copies, so the score
        actually takes non-trivial values in (0, 1) — not just 0.0 as it did when the
        generator drew unrelated random unicode that never overlapped a benchmark.
        """

        def prop(case) -> bool:
            if not isinstance(case, tuple) or len(case) != 2:
                return _OK
            records, benchmarks = case
            flagged = contamination.flag_contaminated(records, benchmarks)
            return all(
                0.0 <= rec.meta["contamination_score"] <= 1.0 for rec in flagged
            )

        def gen(rng):
            if pbt.integers(0, 1)(rng):
                return gen_perturbed_case(rng)
            return (gen_records(rng), gen_benchmarks(rng))

        pbt.for_all(gen, prop, label="score-range")

    def test_score_range_actually_intermediate(self) -> None:
        """(5, teeth) The score generator must really reach values strictly inside
        (0, 1) — otherwise [0, 1] is only ever tested at 0.0. This asserts that a
        perturbed-copy case produces at least one intermediate score across runs.
        """
        seen_intermediate = False
        rng_seed = 0

        def gen(rng):
            return gen_perturbed_case(rng)

        def prop(case) -> bool:
            nonlocal seen_intermediate
            records, benchmarks = case
            flagged = contamination.flag_contaminated(records, benchmarks)
            for rec in flagged:
                s = rec.meta["contamination_score"]
                if 0.0 < s < 1.0:
                    seen_intermediate = True
                if not (0.0 <= s <= 1.0):
                    return False
            return True

        pbt.for_all(gen, prop, runs=200, seed=rng_seed, label="score-intermediate")
        self.assertTrue(
            seen_intermediate,
            "perturbed generator never produced an intermediate (0,1) score",
        )

    def test_lower_ngram_also_holds_score_range(self) -> None:
        """(5, robustness) Score range holds across a range of n-gram sizes."""

        def prop(case) -> bool:
            if not isinstance(case, tuple) or len(case) != 3:
                return _OK
            records, benchmarks, n = case
            if not isinstance(n, int) or n < 1:
                return _OK
            flagged = contamination.flag_contaminated(records, benchmarks, 0.8, n)
            return all(
                0.0 <= rec.meta["contamination_score"] <= 1.0 for rec in flagged
            )

        def gen(rng):
            n = pbt.integers(1, 6)(rng)
            return (gen_records(rng), gen_benchmarks(rng), n)

        pbt.for_all(gen, prop, label="score-range-ngram")


class ContaminationExamples(unittest.TestCase):
    BENCHMARKS = [
        "the quick brown fox jumps over the lazy dog",
        "fal'Cie aims to become an open-weight language model",
    ]

    def _records(self, texts: list[str]) -> list[R.Record]:
        return [R.Record(R.make_id("s", i, t), t, "s") for i, t in enumerate(texts)]

    def test_exact_match_flagged(self) -> None:
        recs = self._records([self.BENCHMARKS[0]])
        flagged = contamination.flag_contaminated(recs, self.BENCHMARKS)
        self.assertTrue(flagged[0].meta["contaminated"])
        self.assertEqual(flagged[0].meta["contamination_score"], 1.0)

    def test_exact_match_after_normalization(self) -> None:
        # Trailing whitespace and blank lines are stripped by normalize_text, so
        # this still counts as an exact match even with a high threshold.
        recs = self._records([self.BENCHMARKS[0] + "   \n\n"])
        flagged = contamination.flag_contaminated(recs, self.BENCHMARKS, threshold=0.99)
        self.assertTrue(flagged[0].meta["contaminated"])

    def test_clean_record_not_flagged(self) -> None:
        recs = self._records(["0123456789 numbers only and unrelated content"])
        flagged = contamination.flag_contaminated(recs, self.BENCHMARKS)
        self.assertFalse(flagged[0].meta["contaminated"])
        self.assertLess(flagged[0].meta["contamination_score"], 0.8)

    def test_near_duplicate_flagged_by_jaccard(self) -> None:
        # One-word change from a benchmark: high n-gram overlap -> flagged.
        recs = self._records(["the quick brown fox jumps over the lazy cat"])
        flagged = contamination.flag_contaminated(recs, self.BENCHMARKS, threshold=0.7)
        self.assertTrue(flagged[0].meta["contaminated"])

    def test_score_equal_to_threshold_is_flagged(self) -> None:
        """(1c) Boundary: score == threshold flags the record. Kills ``>=`` -> ``>``.

        ``abcdefghij`` has six 5-grams; ``abcdefghijk`` adds exactly one, so their
        Jaccard is 6/7 == 0.8571 (rounded). It is NOT an exact match, so the only
        thing that can flag it is the threshold rule. Setting the threshold to that
        exact rounded value must flag it (``score >= threshold``); a ``>`` mutant
        would not.
        """
        bench = ["abcdefghij"]
        recs = self._records(["abcdefghijk"])
        flagged = contamination.flag_contaminated(recs, bench, threshold=0.8571)
        self.assertEqual(flagged[0].meta["contamination_score"], 0.8571)
        self.assertTrue(flagged[0].meta["contaminated"])
        # One tick above the score: not flagged (confirms the boundary is exact).
        above = contamination.flag_contaminated(recs, bench, threshold=0.8572)
        self.assertFalse(above[0].meta["contaminated"])

    def test_score_between_thresholds_flips(self) -> None:
        """(1b) A record whose score sits between two thresholds flips contaminated.

        The same 0.8571 perturbed copy is flagged below the score and not flagged
        above it — so ``contaminated`` is a function of ``threshold``, not hardcoded.
        """
        bench = ["abcdefghij"]
        recs = self._records(["abcdefghijk"])
        below = contamination.flag_contaminated(recs, bench, threshold=0.80)
        above = contamination.flag_contaminated(recs, bench, threshold=0.90)
        self.assertTrue(below[0].meta["contaminated"])
        self.assertFalse(above[0].meta["contaminated"])

    def test_flag_and_score_never_disagree(self) -> None:
        """(5) Consistency: for every record, the stored flag equals the rule
        ``exact_match OR (benchmarks AND score >= threshold)``. The persisted score
        and the boolean flag can never disagree.
        """
        bench = self.BENCHMARKS
        normalized_bench = {R.normalize_text(b) for b in bench}
        texts = [
            self.BENCHMARKS[0],  # exact match
            self.BENCHMARKS[0] + "XYZ",  # near (sub-1.0) score
            "abcdefghijk",  # unrelated to these benchmarks -> low score
            "0123456789 entirely different digits content here",
        ]
        recs = self._records(texts)
        for threshold in (0.0, 0.5, 0.8, 0.99, 1.0):
            flagged = contamination.flag_contaminated(recs, bench, threshold=threshold)
            for rec in flagged:
                exact = R.normalize_text(rec.text) in normalized_bench
                score = rec.meta["contamination_score"]
                expected = exact or (bool(bench) and score >= threshold)
                self.assertEqual(
                    rec.meta["contaminated"],
                    expected,
                    msg=f"flag/score disagree at threshold={threshold} for {rec.text!r}",
                )

    def test_consistency_with_empty_benchmarks(self) -> None:
        """(5) Consistency degenerate arm: with no benchmarks the rule reduces to
        ``exact_match`` (always False) -> nothing is contaminated, score is 0.0.
        """
        recs = self._records(["anything", "0123456789", ""[:0] or "x"])
        for threshold in (0.0, 0.5, 1.0):
            flagged = contamination.flag_contaminated(recs, [], threshold=threshold)
            for rec in flagged:
                self.assertFalse(rec.meta["contaminated"])
                self.assertEqual(rec.meta["contamination_score"], 0.0)

    def test_empty_benchmarks_remove_keeps_everything(self) -> None:
        """(6) Empty benchmark list: even with --remove, the corpus survives intact.

        Guards against a regression where ``threshold == 0.0`` plus no benchmarks
        could wipe the corpus. With no benchmarks nothing is contaminated, so
        ``remove_contaminated`` returns the whole input unchanged.
        """
        texts = ["first record", "second record", "third 0123456789 record"]
        recs = self._records(texts)
        for threshold in (0.0, 0.8, 1.0):
            kept = contamination.remove_contaminated(recs, [], threshold=threshold)
            self.assertEqual([r.id for r in kept], [r.id for r in recs])
            self.assertTrue(all(not r.meta["contaminated"] for r in kept))

    def test_remove_drops_contaminated(self) -> None:
        recs = self._records(
            [self.BENCHMARKS[0], "completely different unrelated 0123456789 text here"]
        )
        kept = contamination.remove_contaminated(recs, self.BENCHMARKS)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].text, "completely different unrelated 0123456789 text here")

    def test_empty_records(self) -> None:
        self.assertEqual(contamination.flag_contaminated([], self.BENCHMARKS), [])
        self.assertEqual(contamination.remove_contaminated([], self.BENCHMARKS), [])

    def test_no_benchmarks_flags_nothing(self) -> None:
        recs = self._records(["any text at all"])
        flagged = contamination.flag_contaminated(recs, [])
        self.assertFalse(flagged[0].meta["contaminated"])
        self.assertEqual(flagged[0].meta["contamination_score"], 0.0)

    def test_load_benchmarks_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bench.jsonl"
            path.write_text(
                '{"id": "a", "text": "hello world"}\n{"text": "second one"}\n\n',
                encoding="utf-8",
            )
            texts = contamination.load_benchmarks(path)
            self.assertEqual(texts, ["hello world", "second one"])

    def test_load_benchmarks_txt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bench.txt"
            path.write_text("first line\n\nsecond line\n", encoding="utf-8")
            texts = contamination.load_benchmarks(path)
            self.assertEqual(texts, ["first line", "second line"])

    def test_default_benchmarks_load(self) -> None:
        # The default probe fixture is a real .jsonl with a text field.
        texts = contamination.load_benchmarks(contamination.DEFAULT_BENCHMARKS)
        self.assertTrue(texts)
        self.assertTrue(all(isinstance(t, str) and t for t in texts))

    def test_cli_flag_and_remove(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            inp = tmp_path / "in.jsonl"
            R.write_records(
                inp,
                self._records(
                    [self.BENCHMARKS[0], "unrelated 0123456789 only digits text"]
                ),
            )
            out = tmp_path / "out.jsonl"
            # Wrap main() so its progress line does not leak into the test runner's
            # stdout (keeps -v output clean and isolates the CLI's side effects).
            with contextlib.redirect_stdout(io.StringIO()):
                rc = contamination.main(
                    [
                        "contamination.py",
                        str(inp),
                        "--benchmarks",
                        str(self._write_bench(tmp_path)),
                        "--output",
                        str(out),
                    ]
                )
            self.assertEqual(rc, 0)
            written = R.read_records(out)
            self.assertEqual(len(written), 2)  # flag mode keeps all records
            contaminated = [r for r in written if r.meta["contaminated"]]
            self.assertEqual(len(contaminated), 1)

            # Now with --remove the contaminated record is dropped.
            out2 = tmp_path / "out2.jsonl"
            with contextlib.redirect_stdout(io.StringIO()):
                rc = contamination.main(
                    [
                        "contamination.py",
                        str(inp),
                        "--benchmarks",
                        str(self._write_bench(tmp_path)),
                        "--remove",
                        "--output",
                        str(out2),
                    ]
                )
            self.assertEqual(rc, 0)
            written2 = R.read_records(out2)
            self.assertEqual(len(written2), 1)
            self.assertFalse(written2[0].meta["contaminated"])

    def _write_bench(self, tmp_path: Path) -> Path:
        path = tmp_path / "bench.txt"
        path.write_text("\n".join(self.BENCHMARKS) + "\n", encoding="utf-8")
        return path


if __name__ == "__main__":
    unittest.main()
