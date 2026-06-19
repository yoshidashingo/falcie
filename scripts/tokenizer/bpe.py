#!/usr/bin/env python3
"""Dependency-free byte-level BPE tokenizer for fal'Cie.

This is a from-scratch, clean-room implementation using only the Python standard
library. It exists so the tokenizer workstream (roadmap M1 / training-plan
Stage 1) can train, compare, and select candidates before the project adopts a
dependency-managed environment.

Design choices that matter:

- **Byte-level base alphabet.** The 256 single-byte tokens (ids 0..255) are always
  present, so *every* input round-trips losslessly and there is no "unknown" token.
  This is what makes ``decode(encode(text)) == text`` hold for all text.
- **Deterministic training.** The most frequent adjacent pair is merged each step;
  ties are broken by the lexicographically smallest pair. Training the same corpus
  with the same ``vocab_size``/``special_tokens`` always yields identical merges.
- **No third-party code.** The algorithm is the textbook BPE merge loop; no vocab,
  weights, or code are copied or ported from any existing tokenizer.

Id space layout (stable given ``special_tokens``):
    0 .. 255                      -> raw bytes
    256 .. 256+S-1                -> the S special tokens, in order
    256+S .. 256+S+M-1            -> the M learned merges, in merge order

``special_tokens`` are reserved ids only; ordinary ``encode`` never emits them.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

FORMAT = "falcie-bpe"
FORMAT_VERSION = 1
BYTE_BASE = 256

Pair = tuple[int, int]


class BPEModel:
    """A trained (or loaded) byte-level BPE model.

    Construct via :meth:`train` or :meth:`load`; the bare constructor takes the
    canonical persisted fields (special tokens + ordered merges) and derives the
    lookup tables needed for ``encode``/``decode``.
    """

    def __init__(self, special_tokens: Iterable[str], merges: Iterable[Pair]) -> None:
        self.special_tokens: list[str] = list(special_tokens)
        self.merges: list[Pair] = [tuple(pair) for pair in merges]  # type: ignore[misc]
        self._build_tables()

    # -- derived tables ----------------------------------------------------

    def _build_tables(self) -> None:
        specials = self.special_tokens
        if len(set(specials)) != len(specials):
            raise ValueError("special_tokens must be unique")

        base = BYTE_BASE + len(specials)

        # id -> bytes (used by decode). Built in dependency order so every merge
        # only references ids that already have a byte expansion.
        id_to_bytes: dict[int, bytes] = {i: bytes([i]) for i in range(BYTE_BASE)}
        for offset, token in enumerate(specials):
            id_to_bytes[BYTE_BASE + offset] = token.encode("utf-8")

        merge_rank: dict[Pair, int] = {}
        pair_to_id: dict[Pair, int] = {}
        for rank, pair in enumerate(self.merges):
            a, b = pair
            if a not in id_to_bytes or b not in id_to_bytes:
                raise ValueError(f"merge {pair} references an unknown id")
            new_id = base + rank
            merge_rank[pair] = rank
            pair_to_id[pair] = new_id
            id_to_bytes[new_id] = id_to_bytes[a] + id_to_bytes[b]

        self._base = base
        self._id_to_bytes = id_to_bytes
        self._merge_rank = merge_rank
        self._pair_to_id = pair_to_id

    # -- properties --------------------------------------------------------

    @property
    def vocab_size(self) -> int:
        return BYTE_BASE + len(self.special_tokens) + len(self.merges)

    def special_id(self, token: str) -> int:
        """Return the reserved id for a special token (raises if not reserved)."""
        return BYTE_BASE + self.special_tokens.index(token)

    # -- core ops ----------------------------------------------------------

    def encode(self, text: str) -> list[int]:
        """Encode text into token ids by applying merges in increasing rank order.

        Each pass finds the lowest-rank adjacent pair present and merges *all* of
        its occurrences, then rescans. A merge's output token only ever appears in
        pairs that were learned at a higher rank, so ranks are consumed in strictly
        increasing order: this is equivalent to one-at-a-time greedy lowest-rank
        merging but runs in far fewer passes (O(distinct merges applied) rather than
        O(token count)). ``tests/test_bpe_pbt.py`` pins this equivalence against a
        naive reference encoder. Ordinary text only; special-token ids are never
        produced here.
        """
        ids: list[int] = list(text.encode("utf-8"))
        if len(ids) < 2:
            return ids

        while True:
            best_rank: int | None = None
            best_pair: Pair | None = None
            for i in range(len(ids) - 1):
                pair = (ids[i], ids[i + 1])
                rank = self._merge_rank.get(pair)
                if rank is not None and (best_rank is None or rank < best_rank):
                    best_rank = rank
                    best_pair = pair
            if best_pair is None:
                break
            ids = _merge_sequence(ids, best_pair, self._pair_to_id[best_pair])
        return ids

    def decode(self, ids: Iterable[int]) -> str:
        """Decode token ids back to text.

        Inverts :meth:`encode` for a *complete* id sequence (a full ``encode``
        output, or a concatenation of full outputs). Token ids are byte-level, so a
        truncated or otherwise arbitrary id stream may not form valid UTF-8; in that
        case a ``ValueError`` is raised (``UnicodeDecodeError`` is a ``ValueError``
        subclass), as it is for an unknown id. Callers doing streaming/partial
        decoding must recombine into complete sequences before decoding.
        """
        out = bytearray()
        for token_id in ids:
            try:
                out += self._id_to_bytes[token_id]
            except KeyError as exc:
                raise ValueError(f"unknown token id: {token_id}") from exc
        return out.decode("utf-8")

    def token_count(self, text: str) -> int:
        """``len(encode(text))`` — the ``Callable[[str], int]`` scorers expect."""
        return len(self.encode(text))

    # -- training ----------------------------------------------------------

    @classmethod
    def train(
        cls,
        corpus: Iterable[str],
        vocab_size: int,
        special_tokens: Iterable[str] = (),
    ) -> "BPEModel":
        """Learn merges from ``corpus`` until reaching ``vocab_size`` (or no pairs).

        Deterministic: most-frequent pair wins, ties broken by smallest pair.
        """
        specials = list(special_tokens)
        base = BYTE_BASE + len(specials)
        if vocab_size < base:
            raise ValueError(
                f"vocab_size {vocab_size} is below the floor {base} "
                f"(256 bytes + {len(specials)} special tokens)"
            )
        num_merges = vocab_size - base

        # Each non-empty corpus line becomes a sequence of byte ids.
        sequences: list[list[int]] = [
            list(line.encode("utf-8")) for line in corpus if line
        ]

        merges: list[Pair] = []
        next_id = base
        for _ in range(num_merges):
            counts: dict[Pair, int] = {}
            for seq in sequences:
                for i in range(len(seq) - 1):
                    pair = (seq[i], seq[i + 1])
                    counts[pair] = counts.get(pair, 0) + 1
            if not counts:
                break

            best_pair: Pair | None = None
            best_count = -1
            for pair, count in counts.items():
                if (
                    best_pair is None
                    or count > best_count
                    or (count == best_count and pair < best_pair)
                ):
                    best_count = count
                    best_pair = pair
            assert best_pair is not None

            merges.append(best_pair)
            sequences = [_merge_sequence(seq, best_pair, next_id) for seq in sequences]
            next_id += 1

        return cls(specials, merges)

    # -- persistence -------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": FORMAT,
            "version": FORMAT_VERSION,
            "special_tokens": list(self.special_tokens),
            "merges": [[a, b] for a, b in self.merges],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BPEModel":
        if data.get("format") != FORMAT:
            raise ValueError(f"not a {FORMAT} model: {data.get('format')!r}")
        if data.get("version") != FORMAT_VERSION:
            raise ValueError(f"unsupported model version: {data.get('version')!r}")
        merges = [tuple(pair) for pair in data.get("merges", [])]
        return cls(data.get("special_tokens", []), merges)

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path) -> "BPEModel":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)


def _merge_sequence(seq: list[int], pair: Pair, new_id: int) -> list[int]:
    """Replace every non-overlapping occurrence of ``pair`` in ``seq`` with ``new_id``."""
    a, b = pair
    merged: list[int] = []
    i = 0
    n = len(seq)
    while i < n:
        if i < n - 1 and seq[i] == a and seq[i + 1] == b:
            merged.append(new_id)
            i += 2
        else:
            merged.append(seq[i])
            i += 1
    return merged
