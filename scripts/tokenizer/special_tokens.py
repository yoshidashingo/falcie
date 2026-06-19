#!/usr/bin/env python3
"""Canonical special-token scheme for fal'Cie chat formatting (unit U-T4).

The training/evaluation config (``configs/tokenizer/evaluation.yaml``) declares a
``special_token_categories`` list — the *roles* the tokenizer must reserve so the
chat/tool surface has stable, non-text markers. This module turns those abstract
categories into concrete token *strings* and provides the glue to (a) build a BPE
model with those strings reserved as special ids and (b) render a list of chat
messages into a single prompt string.

Category -> token string mapping (kept in declaration order):

    bos             -> <bos>
    eos             -> <eos>
    pad             -> <pad>
    system_role     -> <system>
    user_role       -> <user>
    assistant_role  -> <assistant>
    tool_call       -> <tool_call>
    tool_result     -> <tool_result>

How the markers are encoded — read this before relying on the ids
----------------------------------------------------------------
``build_tokenizer`` reserves every string in :data:`SPECIAL_TOKENS` via
``BPEModel.train(..., special_tokens=SPECIAL_TOKENS)``. That gives each marker a
*reserved id* (``model.special_id(tok)``) which ordinary ``encode`` will never
emit (see ``bpe.py``'s contract: ``special_tokens`` are reserved ids only).

``format_chat`` builds a plain ``str`` that embeds the marker strings literally
(e.g. ``"<bos><system>hi<eos>..."``). ``encode_chat`` is exactly
``model.encode(format_chat(messages))``. Because ordinary ``encode`` does **not**
inject special ids, the markers in that string are encoded as their *literal
UTF-8 bytes* (and any learned merges over them), **not** as the reserved special
ids. This is the documented, intentional behaviour for this smoke scheme: the
round-trip ``decode(encode_chat(...)) == format_chat(...)`` holds, and the
reserved ids stay free for a future encoder that injects them deliberately. The
reservation still matters: it guarantees those ids exist and are stable, and that
plain text never collides with them.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "tokenizer"))

import bpe  # noqa: E402

CONFIG_PATH = ROOT / "configs" / "tokenizer" / "evaluation.yaml"

# category (as declared in evaluation.yaml "special_token_categories") -> token string.
# Insertion order is the canonical order; SPECIAL_TOKENS is derived from it.
CATEGORY_TO_TOKEN: dict[str, str] = {
    "bos": "<bos>",
    "eos": "<eos>",
    "pad": "<pad>",
    "system_role": "<system>",
    "user_role": "<user>",
    "assistant_role": "<assistant>",
    "tool_call": "<tool_call>",
    "tool_result": "<tool_result>",
}

# Ordered list of the token STRINGS (the canonical special-token vocabulary).
SPECIAL_TOKENS: list[str] = list(CATEGORY_TO_TOKEN.values())

# Convenience handles for the markers chat formatting needs.
BOS = CATEGORY_TO_TOKEN["bos"]
EOS = CATEGORY_TO_TOKEN["eos"]

# role -> role marker, for the three chat roles format_chat understands.
ROLE_TO_TOKEN: dict[str, str] = {
    "system": CATEGORY_TO_TOKEN["system_role"],
    "user": CATEGORY_TO_TOKEN["user_role"],
    "assistant": CATEGORY_TO_TOKEN["assistant_role"],
}


def build_tokenizer(corpus: Sequence[str], vocab_size: int) -> bpe.BPEModel:
    """Train a :class:`bpe.BPEModel` with :data:`SPECIAL_TOKENS` reserved.

    Thin wrapper over ``BPEModel.train`` so every caller reserves the *same*
    canonical markers in the *same* order; ``vocab_size`` must leave room for the
    256 byte tokens plus the special tokens (``train`` enforces this floor).
    """
    return bpe.BPEModel.train(corpus, vocab_size=vocab_size, special_tokens=SPECIAL_TOKENS)


def format_chat(messages: Sequence[Mapping[str, str]]) -> str:
    """Render chat ``messages`` into a single prompt string.

    Each message is ``{'role': 'system'|'user'|'assistant', 'content': str}`` and
    is rendered as ``<role><content><eos>`` (role marker, then the raw content,
    then the end-of-sequence marker). The whole prompt is prefixed with the
    beginning-of-sequence marker, so the output is::

        <bos><role1>content1<eos><role2>content2<eos>...

    Raises ``KeyError`` for an unknown role or a message missing ``role``/
    ``content`` — chat inputs must be well-formed.
    """
    parts: list[str] = [BOS]
    for message in messages:
        role_token = ROLE_TO_TOKEN[message["role"]]
        content = message["content"]
        parts.append(f"{role_token}{content}{EOS}")
    return "".join(parts)


def encode_chat(model: bpe.BPEModel, messages: Sequence[Mapping[str, str]]) -> list[int]:
    """Encode a chat: ``model.encode(format_chat(messages))``.

    Note (see module docstring): ordinary ``encode`` does *not* inject the
    reserved special ids; the markers are encoded as their literal bytes. The
    round-trip ``model.decode(encode_chat(model, messages)) == format_chat(...)``
    therefore holds for any model trained over a byte-level base alphabet.
    """
    return model.encode(format_chat(messages))


def _rel(path: Path) -> str:
    """Repo-relative string for ``path`` (basename fallback if outside the repo)."""
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return resolved.name


def main(argv: list[str]) -> int:
    """Print the canonical special-token scheme (config-relative, deterministic)."""
    print(f"config: {_rel(CONFIG_PATH)}")
    print(f"special_tokens: {len(SPECIAL_TOKENS)}")
    for category, token in CATEGORY_TO_TOKEN.items():
        print(f"  {category}: {token}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
