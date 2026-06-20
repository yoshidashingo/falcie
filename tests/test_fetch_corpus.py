#!/usr/bin/env python3
"""Tests for the corpus cleaning logic (fal'Cie L-003, unit U-D7).

Covers the dependency-free text cleaners in ``scripts/data/fetch_corpus.py`` —
Aozora markup/header/footer stripping, Project Gutenberg wrapper stripping, and
paragraph splitting — with inline fixtures (no network, no downloads).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts" / "data"))

import fetch_corpus as fc  # noqa: E402


AOZORA_SAMPLE = (
    "吾輩は猫である\n"
    "夏目漱石\n"
    "\n"
    "-------------------------------------------------------\n"
    "【テキスト中に現れる記号について】\n"
    "《》：ルビ\n"
    "｜：ルビの付く文字列の始まりを特定する記号\n"
    "-------------------------------------------------------\n"
    "\n"
    "吾輩《わがはい》は猫である。\n"
    "名前はまだ［＃「ない」に傍点］ない。\n"
    "ど｜こで生れたかとんと見当がつかぬ。\n"
    "\n"
    "底本：「吾輩は猫である」岩波書店\n"
    "入力：誰か\n"
)


class TestCleanAozora(unittest.TestCase):
    def setUp(self) -> None:
        self.cleaned = fc.clean_aozora(AOZORA_SAMPLE.encode("shift_jis"))

    def test_strips_ruby(self) -> None:
        self.assertNotIn("《", self.cleaned)
        self.assertNotIn("わがはい", self.cleaned)
        self.assertIn("吾輩は猫である。", self.cleaned)

    def test_strips_annotation(self) -> None:
        self.assertNotIn("［＃", self.cleaned)
        self.assertIn("名前はまだない。", self.cleaned)

    def test_strips_ruby_base_marker(self) -> None:
        self.assertNotIn("｜", self.cleaned)
        self.assertIn("どこで生れたか", self.cleaned)

    def test_strips_header_block(self) -> None:
        self.assertNotIn("テキスト中に現れる記号", self.cleaned)
        self.assertNotIn("ルビの付く文字列", self.cleaned)

    def test_strips_footer(self) -> None:
        self.assertNotIn("底本", self.cleaned)
        self.assertNotIn("入力", self.cleaned)


class TestCleanGutenberg(unittest.TestCase):
    def test_strips_wrapper(self) -> None:
        raw = (
            "The Project Gutenberg eBook of Something\n"
            "boilerplate license header here\n"
            "*** START OF THE PROJECT GUTENBERG EBOOK SOMETHING ***\n"
            "\n"
            "Real body sentence one.\n"
            "\n"
            "Real body sentence two.\n"
            "*** END OF THE PROJECT GUTENBERG EBOOK SOMETHING ***\n"
            "trailing license footer\n"
        ).encode("utf-8")
        cleaned = fc.clean_gutenberg(raw)
        self.assertIn("Real body sentence one.", cleaned)
        self.assertIn("Real body sentence two.", cleaned)
        self.assertNotIn("boilerplate license header", cleaned)
        self.assertNotIn("trailing license footer", cleaned)
        self.assertNotIn("PROJECT GUTENBERG", cleaned)


class TestParagraphs(unittest.TestCase):
    def test_fine_splits_on_single_newline(self) -> None:
        # Aozora-style single-newline body -> one paragraph per line.
        text = "一行目の文章です。\n二行目の文章です。\n三行目の文章です。"
        paras = fc.paragraphs(text, fine=True)
        self.assertEqual(len(paras), 3)

    def test_coarse_keeps_single_newline_together(self) -> None:
        # Default mode splits only on blank lines.
        text = "line one wrapped\nstill same paragraph\n\nsecond paragraph here"
        paras = fc.paragraphs(text, fine=False)
        self.assertEqual(len(paras), 2)

    def test_drops_trivial_fragments(self) -> None:
        text = "a\n\nthis is a real paragraph"
        self.assertEqual(fc.paragraphs(text, fine=False), ["this is a real paragraph"])


if __name__ == "__main__":
    unittest.main()
