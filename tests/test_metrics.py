#!/usr/bin/env python3
"""Tests for the evaluation metrics (fal'Cie L-004, unit U-E1)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts" / "evals"))

import metrics as M  # noqa: E402


class TestExactMatch(unittest.TestCase):
    def test_equal_and_trimmed(self) -> None:
        self.assertTrue(M.exact_match("DONE", "DONE"))
        self.assertTrue(M.exact_match("  DONE  ", "DONE"))

    def test_case_sensitive(self) -> None:
        self.assertFalse(M.exact_match("done", "DONE"))


class TestNormalizedMatch(unittest.TestCase):
    def test_case_and_punct_insensitive(self) -> None:
        self.assertTrue(M.normalized_match("Paris.", "paris"))
        self.assertTrue(M.normalized_match("東京。", "東京"))

    def test_fullwidth_folding(self) -> None:
        self.assertTrue(M.normalized_match("１２３", "123"))

    def test_distinct(self) -> None:
        self.assertFalse(M.normalized_match("London", "Paris"))


class TestIncludes(unittest.TestCase):
    def test_substring(self) -> None:
        self.assertTrue(M.includes("here is def add(a, b): ...", "def add"))

    def test_missing(self) -> None:
        self.assertFalse(M.includes("nope", "def add"))

    def test_empty_target_is_false(self) -> None:
        self.assertFalse(M.includes("anything", ""))


class TestNumericMatch(unittest.TestCase):
    def test_plain_and_trailing_prose(self) -> None:
        self.assertTrue(M.numeric_match("144", "144"))
        self.assertTrue(M.numeric_match("The answer is 144.", "144"))

    def test_commas_and_floatish(self) -> None:
        self.assertTrue(M.numeric_match("1,000", "1000"))
        self.assertTrue(M.numeric_match("12.0", "12"))

    def test_uses_last_number(self) -> None:
        self.assertTrue(M.numeric_match("from 3 to 7 we get 10", "10"))

    def test_no_number(self) -> None:
        self.assertFalse(M.numeric_match("no digits here", "144"))
        self.assertFalse(M.numeric_match("144", "no target number"))


class TestMultipleChoice(unittest.TestCase):
    def test_bare_letter(self) -> None:
        self.assertTrue(M.multiple_choice("C", "C"))

    def test_answer_cue(self) -> None:
        self.assertTrue(M.multiple_choice("The answer is B.", "B"))

    def test_paren_form(self) -> None:
        self.assertTrue(M.multiple_choice("I pick (D) here", "D"))

    def test_casefold(self) -> None:
        self.assertTrue(M.multiple_choice("a", "A"))

    def test_wrong_and_empty(self) -> None:
        self.assertFalse(M.multiple_choice("The answer is A", "C"))
        self.assertFalse(M.multiple_choice("", "C"))

    def test_prose_not_scored_as_answer(self) -> None:
        # Precision-first: a sentence that merely starts with a letter must NOT be
        # read as choosing that option (no first-letter fallback).
        self.assertFalse(M.multiple_choice("A quick brown fox", "A"))
        self.assertFalse(M.multiple_choice("I think it could be any of them", "I"))


class TestScoreDispatch(unittest.TestCase):
    def test_dispatch(self) -> None:
        self.assertTrue(M.score("numeric_match", "144", "144"))
        self.assertFalse(M.score("exact_match", "x", "y"))

    def test_unknown_metric_raises(self) -> None:
        with self.assertRaises(KeyError):
            M.score("nope", "a", "a")

    def test_registry_complete(self) -> None:
        self.assertEqual(
            set(M.METRICS),
            {"exact_match", "normalized_match", "includes", "numeric_match", "multiple_choice"},
        )


if __name__ == "__main__":
    unittest.main()
