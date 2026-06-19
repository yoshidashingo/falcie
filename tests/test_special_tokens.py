#!/usr/bin/env python3
"""Tests for the special-token chat scheme (unit U-T4).

Properties exercised (PBT category in parentheses):
  * invariant (PBT-03): every string in SPECIAL_TOKENS is unique, reserved in a
    model built with them, and ordinary encode of plain text never emits a
    reserved id;
  * structural invariant (PBT-03): format_chat output starts with <bos> and, in
    message order, contains each message's role token followed by its content;
  * config consistency (PBT-04): SPECIAL_TOKENS has no duplicates and exactly
    matches the categories declared in configs/tokenizer/evaluation.yaml.

Example-based tests pin a concrete 2-message chat (format_chat / encode_chat
round-trip). PBT and example tests live together here per assignment but are kept
as separate methods.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts" / "tokenizer"))
sys.path.insert(0, str(_ROOT / "scripts" / "common"))
sys.path.insert(0, str(_ROOT / "tests"))

import bpe  # noqa: E402
import pbt  # noqa: E402
import special_tokens as ST  # noqa: E402

# A small, varied corpus so the BPE model learns some merges (incl. over markers).
CORPUS = [
    "fal'Cieは、オープンウェイト言語モデルを目指します。",
    "hello world, this is a small chat corpus for testing.",
    "def greet(name: str) -> str: return f'hi {name}'",
    "<system>you are helpful<eos><user>hi<eos>",
    "the quick brown fox 0123456789",
]
VOCAB_SIZE = bpe.BYTE_BASE + len(ST.SPECIAL_TOKENS) + 200
MODEL = ST.build_tokenizer(CORPUS, VOCAB_SIZE)
RESERVED_IDS = {MODEL.special_id(tok) for tok in ST.SPECIAL_TOKENS}


def _read_config_categories() -> list[str]:
    """Load special_token_categories from evaluation.yaml.

    The config is JSON-compatible YAML (see summarize_probes / the repo contract),
    so json.loads parses it directly — no third-party YAML dependency.
    """
    data = json.loads(ST.CONFIG_PATH.read_text(encoding="utf-8"))
    return list(data["special_token_categories"])


def _gen_message(rng) -> dict[str, str]:
    role = rng.choice(("system", "user", "assistant"))
    content = pbt.text(max_len=30)(rng)
    return {"role": role, "content": content}


def _gen_chat(rng) -> list[dict[str, str]]:
    return pbt.lists(_gen_message, min_len=1, max_len=4)(rng)


def _text_maybe_with_marker(rng) -> str:
    """Plain text that sometimes embeds a special-token literal — encode of it
    must still never emit a reserved id."""
    base = pbt.text(max_len=40)(rng)
    if rng.random() < 0.5:
        token = rng.choice(ST.SPECIAL_TOKENS)
        pos = rng.randint(0, len(base))
        return base[:pos] + token + base[pos:]
    return base


class TestSpecialTokenProperties(unittest.TestCase):
    # --- Property 1: uniqueness + reservation + no leakage into plain text ----

    def test_special_tokens_unique_and_reserved(self) -> None:
        self.assertEqual(len(ST.SPECIAL_TOKENS), len(set(ST.SPECIAL_TOKENS)))
        # Every special token has a working reserved id, and ids are distinct.
        ids = [MODEL.special_id(tok) for tok in ST.SPECIAL_TOKENS]
        self.assertEqual(len(ids), len(set(ids)))
        for tok in ST.SPECIAL_TOKENS:
            self.assertIn(tok, MODEL.special_tokens)

    def test_plain_encode_never_emits_reserved_ids(self) -> None:
        pbt.for_all(
            _text_maybe_with_marker,
            lambda s: RESERVED_IDS.isdisjoint(MODEL.encode(s)),
            label="ordinary encode emits no reserved special ids",
        )

    # --- Property 2: format_chat structure ------------------------------------

    def test_format_chat_starts_with_bos(self) -> None:
        pbt.for_all(
            _gen_chat,
            lambda msgs: ST.format_chat(msgs).startswith(ST.BOS),
            label="format_chat starts with <bos>",
        )

    def test_format_chat_contains_roles_and_content_in_order(self) -> None:
        def in_order(msgs: list[dict[str, str]]) -> bool:
            rendered = ST.format_chat(msgs)
            # Walk a cursor forward: for each message its role token then its
            # content must appear after the previous match — i.e. in message order.
            cursor = 0
            for msg in msgs:
                role_tok = ST.ROLE_TO_TOKEN[msg["role"]]
                role_at = rendered.find(role_tok, cursor)
                if role_at < 0:
                    return False
                content_at = rendered.find(msg["content"], role_at + len(role_tok))
                if content_at < 0:
                    return False
                cursor = content_at + len(msg["content"])
            return True

        pbt.for_all(
            _gen_chat,
            in_order,
            label="format_chat has role+content per message in order",
        )

    def test_encode_chat_roundtrips_to_format_chat(self) -> None:
        # Documented behaviour: markers are literal bytes, so decode recovers the
        # exact formatted string.
        pbt.for_all(
            _gen_chat,
            lambda msgs: MODEL.decode(ST.encode_chat(MODEL, msgs)) == ST.format_chat(msgs),
            label="decode(encode_chat) == format_chat",
        )

    # --- A deliberately wrong property must return False, not raise -----------

    def test_negative_control(self) -> None:
        # Sanity check on the harness contract: a false property is caught.
        with self.assertRaises(pbt.Counterexample):
            pbt.for_all(
                _gen_chat,
                lambda msgs: not ST.format_chat(msgs).startswith(ST.BOS),
                label="(negative control) format_chat does NOT start with bos",
            )

    # --- Property 3: SPECIAL_TOKENS matches the config categories -------------

    def test_special_tokens_match_config(self) -> None:
        categories = _read_config_categories()
        # No duplicate categories or tokens.
        self.assertEqual(len(categories), len(set(categories)))
        self.assertEqual(len(ST.SPECIAL_TOKENS), len(set(ST.SPECIAL_TOKENS)))
        # CATEGORY_TO_TOKEN keys are exactly the declared categories, same order.
        self.assertEqual(list(ST.CATEGORY_TO_TOKEN.keys()), categories)
        # SPECIAL_TOKENS is the ordered values of that mapping.
        self.assertEqual(ST.SPECIAL_TOKENS, [ST.CATEGORY_TO_TOKEN[c] for c in categories])


class TestSpecialTokenExamples(unittest.TestCase):
    def test_concrete_two_message_chat_format(self) -> None:
        messages = [
            {"role": "system", "content": "You are fal'Cie."},
            {"role": "user", "content": "Hello!"},
        ]
        expected = "<bos><system>You are fal'Cie.<eos><user>Hello!<eos>"
        self.assertEqual(ST.format_chat(messages), expected)

    def test_concrete_two_message_chat_encode_roundtrip(self) -> None:
        messages = [
            {"role": "system", "content": "You are fal'Cie."},
            {"role": "user", "content": "Hello!"},
        ]
        ids = ST.encode_chat(MODEL, messages)
        self.assertEqual(ids, MODEL.encode(ST.format_chat(messages)))
        self.assertEqual(MODEL.decode(ids), ST.format_chat(messages))

    def test_canonical_token_strings(self) -> None:
        self.assertEqual(
            ST.SPECIAL_TOKENS,
            [
                "<bos>",
                "<eos>",
                "<pad>",
                "<system>",
                "<user>",
                "<assistant>",
                "<tool_call>",
                "<tool_result>",
            ],
        )

    def test_build_tokenizer_reserves_all_markers(self) -> None:
        model = ST.build_tokenizer(["a tiny corpus"], bpe.BYTE_BASE + len(ST.SPECIAL_TOKENS))
        for tok in ST.SPECIAL_TOKENS:
            self.assertEqual(model.special_id(tok), model.special_tokens.index(tok) + bpe.BYTE_BASE)

    def test_unknown_role_raises(self) -> None:
        with self.assertRaises(KeyError):
            ST.format_chat([{"role": "tool", "content": "x"}])


if __name__ == "__main__":
    unittest.main()
