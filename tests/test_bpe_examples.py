#!/usr/bin/env python3
"""Example-based tests for the byte-level BPE tokenizer (unit U-T1).

These pin specific, known behaviours (PBT-10: example-based tests complement the
property-based tests in ``test_bpe_pbt.py`` and document concrete expectations).
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts" / "tokenizer"))

import bpe  # noqa: E402


class TestBPEExamples(unittest.TestCase):
    def test_empty_string(self) -> None:
        model = bpe.BPEModel.train(["abc"], vocab_size=bpe.BYTE_BASE + 1)
        self.assertEqual(model.encode(""), [])
        self.assertEqual(model.decode([]), "")

    def test_single_byte_char_has_no_merge(self) -> None:
        model = bpe.BPEModel.train(["ab"], vocab_size=bpe.BYTE_BASE)  # no merges
        self.assertEqual(model.merges, [])
        self.assertEqual(model.encode("a"), [ord("a")])

    def test_known_first_merge(self) -> None:
        # "aaaa" -> most frequent adjacent pair is ('a','a'); one merge collapses pairs.
        model = bpe.BPEModel.train(["aaaa"], vocab_size=bpe.BYTE_BASE + 1)
        self.assertEqual(model.merges, [(ord("a"), ord("a"))])
        new_id = bpe.BYTE_BASE  # first merge id, no specials
        self.assertEqual(model.encode("aaaa"), [new_id, new_id])
        self.assertEqual(model.decode([new_id, new_id]), "aaaa")

    def test_special_tokens_reserved_but_not_emitted(self) -> None:
        specials = ["<bos>", "<eos>"]
        model = bpe.BPEModel.train(["hello"], vocab_size=bpe.BYTE_BASE + len(specials), special_tokens=specials)
        self.assertEqual(model.special_id("<bos>"), bpe.BYTE_BASE)
        self.assertEqual(model.special_id("<eos>"), bpe.BYTE_BASE + 1)
        # Encoding text that literally contains "<eos>" must not yield the reserved id.
        self.assertNotIn(model.special_id("<eos>"), model.encode("<eos> at end"))
        self.assertEqual(model.decode(model.encode("<eos> at end")), "<eos> at end")

    def test_vocab_size_below_floor_raises(self) -> None:
        with self.assertRaises(ValueError):
            bpe.BPEModel.train(["abc"], vocab_size=bpe.BYTE_BASE - 1)
        with self.assertRaises(ValueError):
            # floor includes special tokens
            bpe.BPEModel.train(["abc"], vocab_size=bpe.BYTE_BASE, special_tokens=["<bos>"])

    def test_save_load_round_trip(self) -> None:
        model = bpe.BPEModel.train(["banana bandana"], vocab_size=bpe.BYTE_BASE + 10, special_tokens=["<pad>"])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.json"
            model.save(path)
            loaded = bpe.BPEModel.load(path)
        self.assertEqual(loaded.merges, model.merges)
        self.assertEqual(loaded.special_tokens, model.special_tokens)
        self.assertEqual(loaded.vocab_size, model.vocab_size)

    def test_from_dict_rejects_foreign_format(self) -> None:
        with self.assertRaises(ValueError):
            bpe.BPEModel.from_dict({"format": "not-falcie", "version": 1, "merges": []})

    def test_decode_rejects_unknown_id(self) -> None:
        model = bpe.BPEModel.train(["abc"], vocab_size=bpe.BYTE_BASE)
        with self.assertRaises(ValueError):
            model.decode([10**9])

    def test_duplicate_special_tokens_rejected(self) -> None:
        with self.assertRaises(ValueError):
            bpe.BPEModel(["<x>", "<x>"], [])

    def test_compresses_in_domain_text(self) -> None:
        # The "never expands" property holds at equality on out-of-domain text; this
        # pins that the merge path *actually compresses* text the model was trained
        # on (token count strictly below the UTF-8 byte length).
        corpus = [
            "the quick brown fox jumps over the lazy dog",
            "fal'Cie open-weight language model",
            "日本語と English の混在テキスト",
        ]
        model = bpe.BPEModel.train(corpus, vocab_size=bpe.BYTE_BASE + 80)
        for line in corpus:
            byte_len = len(line.encode("utf-8"))
            self.assertLess(
                model.token_count(line),
                byte_len,
                f"expected compression on in-domain line: {line!r}",
            )


if __name__ == "__main__":
    unittest.main()
