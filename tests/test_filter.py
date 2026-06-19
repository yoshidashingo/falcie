#!/usr/bin/env python3
"""Tests for the quality-filtering stage (unit U-D3).

Property-based tests (PBT category in parentheses) and example-based tests are
kept side by side here; they complement each other (PBT-10).

Properties exercised:
  * subsequence (PBT-03): the kept records are an order-preserving subsequence of
    the input — never reordered, mutated, or invented.
  * idempotence (PBT-04): filter_records(filter_records(x)) == filter_records(x).
  * soundness/oracle (PBT-05): every kept record passes ``passes_filters`` under
    the same config.
  * invariant (PBT-03): a text shorter than ``min_chars`` is always dropped.
  * invariant (PBT-03): a text whose repeat-line ratio exceeds
    ``max_repeat_line_ratio`` is always dropped, and one that does not exceed it
    (all else permissive) is always kept.
  * invariant (PBT-03): an empty/permissive config drops nothing.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts" / "data"))
sys.path.insert(0, str(_ROOT / "tests"))

import records as R  # noqa: E402
import pbt  # noqa: E402
import filter as F  # noqa: E402


def gen_records(rng) -> list[R.Record]:
    """Generator of small record lists with UNIQUE ids (index disambiguates dups).

    Text is non-empty: the Record contract (``Record.from_dict``) rejects empty
    text, so real records flowing through the pipeline always have ``len >= 1``.
    """
    texts = pbt.lists(pbt.text(min_len=1, max_len=30), max_len=6)(rng)
    return [R.Record(R.make_id("s", i, t), t, "s") for i, t in enumerate(texts)]


def gen_config(rng) -> dict:
    """Generator of varied (sometimes active, sometimes disabled) filter configs."""
    cfg: dict = {}
    if rng.random() < 0.7:
        cfg["min_chars"] = pbt.integers(0, 10)(rng)
    if rng.random() < 0.5:
        cfg["max_chars"] = pbt.integers(0, 25)(rng)
    if rng.random() < 0.5:
        cfg["max_symbol_ratio"] = round(rng.random(), 3)
    if rng.random() < 0.5:
        cfg["max_whitespace_ratio"] = round(rng.random(), 3)
    if rng.random() < 0.5:
        cfg["max_repeat_line_ratio"] = round(rng.random(), 3)
    return cfg


def gen_records_and_config(rng) -> tuple[list[R.Record], dict]:
    return gen_records(rng), gen_config(rng)


# A small pool of distinct, newline-free, non-empty line tokens. Drawing lines
# from a *small* pool and joining with "\n" deliberately forces many exact
# duplicate lines, so the repeat-line ratio varies across the full [0, 1) range
# (vs. the default text generator, which makes essentially-always-distinct
# single-line text and leaves the repeat-line check path dead).
_LINE_POOL: tuple[str, ...] = ("alpha", "beta", "gamma", "delta", "x", "yy")


def _repeat_line_ratio(lines: list[str]) -> float:
    """Independent oracle for the repeat-line ratio (mirrors filter._repeat_line_ratio).

    Fraction of lines that exactly duplicate an EARLIER line; the first
    occurrence of each distinct line is not counted. ``lines`` is the result of
    splitting the text on "\\n" and so is always non-empty.
    """
    seen: set[str] = set()
    repeats = 0
    for line in lines:
        if line in seen:
            repeats += 1
        else:
            seen.add(line)
    return repeats / len(lines)


def gen_multiline(rng) -> tuple[str, float]:
    """Generator of MULTI-LINE text with a deliberately-varied repeat-line ratio.

    Returns ``(text, ratio)`` where ``text`` is several pool lines joined with
    "\\n" and ``ratio`` is its exact repeat-line ratio computed by the oracle
    above. The lines are non-empty so the whole text has ``len >= 1`` (it never
    trips the default ``min_chars`` of 1), letting a property isolate the
    repeat-line check.
    """
    n = pbt.integers(2, 8)(rng)
    lines = [pbt.sampled_from(_LINE_POOL)(rng) for _ in range(n)]
    text = "\n".join(lines)
    # Split mirrors how passes_filters re-derives lines from the joined text.
    return text, _repeat_line_ratio(text.split("\n"))


def _is_subsequence(sub: list[R.Record], whole: list[R.Record]) -> bool:
    """True if ``sub`` appears in ``whole`` in order (by identity of records)."""
    it = iter(whole)
    return all(any(s is w for w in it) for s in sub)


class TestFilterProperties(unittest.TestCase):
    def test_output_is_subsequence(self) -> None:
        # (1) The kept records are an order-preserving subsequence of the input.
        def prop(case: tuple[list[R.Record], dict]) -> bool:
            recs, cfg = case
            kept = F.filter_records(recs, cfg)
            return _is_subsequence(kept, recs)

        pbt.for_all(gen_records_and_config, prop, label="output subsequence of input")

    def test_idempotence(self) -> None:
        # (2) Filtering an already-filtered list keeps exactly the same records.
        def prop(case: tuple[list[R.Record], dict]) -> bool:
            recs, cfg = case
            once = F.filter_records(recs, cfg)
            twice = F.filter_records(once, cfg)
            return once == twice

        pbt.for_all(gen_records_and_config, prop, label="filter is idempotent")

    def test_kept_records_pass_filters(self) -> None:
        # (3) Every kept record passes passes_filters under the same config.
        def prop(case: tuple[list[R.Record], dict]) -> bool:
            recs, cfg = case
            kept = F.filter_records(recs, cfg)
            return all(F.passes_filters(r.text, cfg) for r in kept)

        pbt.for_all(gen_records_and_config, prop, label="kept records pass filters")

    def test_short_text_always_dropped(self) -> None:
        # (4) A text strictly shorter than min_chars is always dropped.
        def gen(rng):
            min_chars = pbt.integers(1, 12)(rng)
            text = pbt.text(min_len=0, max_len=max(0, min_chars - 1))(rng)
            return min_chars, text

        def prop(case: tuple[int, str]) -> bool:
            min_chars, text = case
            # text is generated strictly shorter than min_chars.
            return not F.passes_filters(text, {"min_chars": min_chars})

        pbt.for_all(gen, prop, label="text shorter than min_chars is dropped")

    def test_high_repeat_line_ratio_always_dropped(self) -> None:
        # (6a) A text whose repeat-line ratio strictly EXCEEDS the configured
        # max_repeat_line_ratio is always dropped (all other checks permissive).
        # Mirrors the short-text invariant: build the structure deliberately, set
        # only the relevant threshold, assert the drop.
        def gen(rng):
            text, ratio = gen_multiline(rng)
            # Choose a threshold strictly below the actual ratio so the drop must
            # fire. When ratio is 0 (all lines distinct) no such threshold exists,
            # so back off to a guaranteed-duplicate text (ratio = 1/2 > 0).
            if ratio <= 0.0:
                text, ratio = "dup\ndup", 0.5
            # A threshold a hair below the rational ratio: still in [0, ratio).
            threshold = max(0.0, ratio - 1e-9)
            return text, ratio, threshold

        def prop(case: tuple[str, float, float]) -> bool:
            # The shrinker may hand back a structurally-reduced tuple; treat any
            # mis-shaped value as vacuously holding so the reported counterexample
            # stays a real generated case rather than a shrink artifact.
            if not (isinstance(case, tuple) and len(case) == 3):
                return True
            text, ratio, threshold = case
            # Precondition the generator promises: ratio strictly exceeds threshold.
            if not (ratio > threshold):
                return True  # vacuously: nothing to assert for this draw
            return not F.passes_filters(text, {"max_repeat_line_ratio": threshold})

        pbt.for_all(gen, prop, label="repeat-line ratio above threshold is dropped")

    def test_repeat_line_ratio_within_threshold_kept(self) -> None:
        # (6b) A multi-line text whose repeat-line ratio does NOT exceed the
        # threshold is kept when every other check is permissive.
        def gen(rng):
            text, ratio = gen_multiline(rng)
            # A threshold at-or-above the ratio: ratio does not exceed it, so the
            # repeat-line check must not drop. (ratio itself is a valid threshold,
            # exercising the exact-equality boundary half the time.)
            threshold = ratio if rng.random() < 0.5 else min(1.0, ratio + 1e-9)
            return text, ratio, threshold

        def prop(case: tuple[str, float, float]) -> bool:
            # Tolerate shrink artifacts (see the sibling property) so the reported
            # counterexample is a genuine generated case.
            if not (isinstance(case, tuple) and len(case) == 3):
                return True
            text, ratio, threshold = case
            cfg = {
                "min_chars": 0,
                "max_chars": None,
                "max_symbol_ratio": None,
                "max_whitespace_ratio": None,
                "max_repeat_line_ratio": threshold,
            }
            return F.passes_filters(text, cfg)

        pbt.for_all(gen, prop, label="repeat-line ratio within threshold is kept")

    def test_permissive_config_drops_nothing(self) -> None:
        # (5) With an empty/permissive config, nothing is dropped.
        def prop(recs: list[R.Record]) -> bool:
            empty = F.filter_records(recs, {})
            permissive = F.filter_records(
                recs,
                {
                    "min_chars": 0,
                    "max_chars": None,
                    "max_symbol_ratio": None,
                    "max_whitespace_ratio": None,
                    "max_repeat_line_ratio": None,
                },
            )
            return empty == recs and permissive == recs

        pbt.for_all(gen_records, prop, label="permissive config drops nothing")


class TestFilterExamples(unittest.TestCase):
    def _recs(self, texts: list[str]) -> list[R.Record]:
        return [R.Record(R.make_id("s", i, t), t, "s") for i, t in enumerate(texts)]

    def test_min_chars_default_drops_empty(self) -> None:
        # Default min_chars is 1, so the empty string is dropped but a 1-char text kept.
        self.assertFalse(F.passes_filters("", {}))
        self.assertTrue(F.passes_filters("x", {}))

    def test_min_and_max_chars(self) -> None:
        self.assertFalse(F.passes_filters("ab", {"min_chars": 3}))
        self.assertTrue(F.passes_filters("abc", {"min_chars": 3}))
        self.assertTrue(F.passes_filters("abc", {"max_chars": 3}))
        self.assertFalse(F.passes_filters("abcd", {"max_chars": 3}))

    def test_symbol_ratio(self) -> None:
        # "a!!!" -> 3/4 = 0.75 symbol fraction.
        self.assertFalse(F.passes_filters("a!!!", {"max_symbol_ratio": 0.5}))
        self.assertTrue(F.passes_filters("abcd", {"max_symbol_ratio": 0.5}))
        # Exactly at the threshold is allowed (strictly-greater rejects).
        self.assertTrue(F.passes_filters("ab!!", {"max_symbol_ratio": 0.5}))

    def test_whitespace_ratio(self) -> None:
        # "a   " -> 3/4 = 0.75 whitespace.
        self.assertFalse(F.passes_filters("a   ", {"max_whitespace_ratio": 0.5}))
        self.assertTrue(F.passes_filters("abcd", {"max_whitespace_ratio": 0.5}))

    def test_repeat_line_ratio(self) -> None:
        # 3 identical lines -> 2 repeats over 3 lines = 0.666...
        text = "dup\ndup\ndup"
        self.assertFalse(F.passes_filters(text, {"max_repeat_line_ratio": 0.5}))
        # All distinct lines -> 0 repeats.
        self.assertTrue(F.passes_filters("a\nb\nc", {"max_repeat_line_ratio": 0.5}))
        # A single line is never a repeat.
        self.assertTrue(F.passes_filters("only", {"max_repeat_line_ratio": 0.0}))

    def test_repeat_line_ratio_exact_threshold_kept(self) -> None:
        # Boundary: ratio EXACTLY equal to the threshold is KEPT (drop is strictly
        # '>', so '>' -> '>=' must change this assertion). "a\na\nb\nc" -> 1 repeat
        # over 4 lines = exactly 0.25.
        text = "a\na\nb\nc"
        self.assertTrue(F.passes_filters(text, {"max_repeat_line_ratio": 0.25}))
        # A hair below 0.25 (now strictly exceeded) flips it to dropped.
        self.assertFalse(F.passes_filters(text, {"max_repeat_line_ratio": 0.24}))
        # Half-and-half: "dup\ndup" -> 1 repeat over 2 lines = exactly 0.5, kept
        # at threshold 0.5 but dropped just below.
        self.assertTrue(F.passes_filters("dup\ndup", {"max_repeat_line_ratio": 0.5}))
        self.assertFalse(F.passes_filters("dup\ndup", {"max_repeat_line_ratio": 0.49}))

    def test_filter_records_keeps_passing_only(self) -> None:
        # Text "x" (len 1) is below min_chars=2 and dropped; longer texts kept.
        recs = self._recs(["x", "ok", "fine", "y"])
        kept = F.filter_records(recs, {"min_chars": 2})
        self.assertEqual([r.text for r in kept], ["ok", "fine"])
        # Subsequence and idempotence on a concrete case.
        self.assertEqual(F.filter_records(kept, {"min_chars": 2}), kept)

    def test_load_config_merges_over_defaults(self) -> None:
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cfg.yaml"
            path.write_text(json.dumps({"min_chars": 5}), encoding="utf-8")
            cfg = F.load_config(path)
            self.assertEqual(cfg["min_chars"], 5)
            # Untouched keys fall back to the permissive defaults.
            self.assertIsNone(cfg["max_chars"])
            self.assertIsNone(cfg["max_symbol_ratio"])

    def test_load_config_rejects_non_object(self) -> None:
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.yaml"
            path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
            with self.assertRaises(ValueError):
                F.load_config(path)

    def test_cli_reports_counts_and_writes_output(self) -> None:
        import io
        import json
        import tempfile
        from contextlib import redirect_stdout

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            inp = tmp_path / "in.jsonl"
            R.write_records(inp, self._recs(["x", "keep", "y"]))
            cfg = tmp_path / "cfg.yaml"
            cfg.write_text(json.dumps({"min_chars": 2}), encoding="utf-8")
            out = tmp_path / "out.jsonl"

            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = F.main(["filter.py", str(inp), "--config", str(cfg), "--output", str(out)])
            self.assertEqual(rc, 0)
            self.assertIn("kept 1 removed 2", buf.getvalue())

            written = R.read_records(out)
            self.assertEqual([r.text for r in written], ["keep"])


if __name__ == "__main__":
    unittest.main()
