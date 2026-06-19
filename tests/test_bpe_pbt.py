#!/usr/bin/env python3
"""Property-based tests for the byte-level BPE tokenizer (unit U-T1).

Properties exercised (PBT category in parentheses):
  * round-trip (PBT-02): decode(encode(x)) == x for all text x
  * invariant  (PBT-03): every emitted id is in [0, vocab_size); byte-level
                          encoding never produces more tokens than UTF-8 bytes
  * oracle/determinism (PBT-05): training the same corpus twice yields equal merges
  * round-trip (PBT-02): a saved-then-loaded model encodes identically

Example-based tests live in ``test_bpe_examples.py`` (PBT-10: the two are kept
in separate files and complement each other).
"""

from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts" / "tokenizer"))
sys.path.insert(0, str(_ROOT / "tests"))

import bpe  # noqa: E402
import pbt  # noqa: E402

# A fixed, reasonably varied training corpus and a model shared across tests.
CORPUS = [
    "fal'Cieは、オープンウェイト言語モデルを目指します。",
    "fal'Cie aims to become a frontier-grade open-weight language model.",
    "def load(path: Path) -> dict: return json.loads(path.read_text())",
    "評価 harness は README と model card を同じ commit SHA に紐づけます。",
    "export function format(name: string): string { return name.trim(); }",
    "## Release Gate\n- evaluation report\n- model card\n- checksums",
    "the quick brown fox jumps over the lazy dog 0123456789",
]
SPECIALS = ["<bos>", "<eos>", "<pad>"]
VOCAB_SIZE = bpe.BYTE_BASE + len(SPECIALS) + 300
MODEL = bpe.BPEModel.train(CORPUS, vocab_size=VOCAB_SIZE, special_tokens=SPECIALS)
SPECIAL_IDS = {MODEL.special_id(tok) for tok in MODEL.special_tokens}


def _reference_encode(model: bpe.BPEModel, text: str) -> list[int]:
    """Naive, obviously-correct reference: merge exactly one (leftmost) lowest-rank
    pair per pass. This is the original one-at-a-time semantics; the optimized
    ``encode`` must agree with it for every input (guards the perf rewrite)."""
    ids = list(text.encode("utf-8"))
    while len(ids) >= 2:
        best_rank = None
        best_pos = None
        for i in range(len(ids) - 1):
            rank = model._merge_rank.get((ids[i], ids[i + 1]))
            if rank is not None and (best_rank is None or rank < best_rank):
                best_rank = rank
                best_pos = i
        if best_pos is None:
            break
        pair = (ids[best_pos], ids[best_pos + 1])
        ids[best_pos : best_pos + 2] = [model._pair_to_id[pair]]
    return ids


def _text_with_specials(rng) -> str:
    """Generator: ordinary text that sometimes embeds a special-token literal,
    to check encode never emits a reserved id for text that merely *looks* special."""
    base = pbt.text(max_len=40)(rng)
    if SPECIALS and rng.random() < 0.5:
        token = rng.choice(SPECIALS)
        pos = rng.randint(0, len(base))
        return base[:pos] + token + base[pos:]
    return base


class TestBPEProperties(unittest.TestCase):
    def test_roundtrip(self) -> None:
        pbt.for_all(
            pbt.text(max_len=80),
            lambda s: MODEL.decode(MODEL.encode(s)) == s,
            label="decode(encode(x)) == x",
        )

    def test_ids_within_vocab(self) -> None:
        pbt.for_all(
            pbt.text(max_len=80),
            lambda s: all(0 <= i < MODEL.vocab_size for i in MODEL.encode(s)),
            label="encoded ids in [0, vocab_size)",
        )

    def test_never_expands_beyond_byte_length(self) -> None:
        pbt.for_all(
            pbt.text(max_len=80),
            lambda s: len(MODEL.encode(s)) <= len(s.encode("utf-8")),
            label="token_count <= byte_length",
        )

    def test_training_is_deterministic(self) -> None:
        # Oracle: the model under test is its own reference — same inputs, same merges.
        corpus_gen = pbt.lists(pbt.text(max_len=24), min_len=1, max_len=6)
        vocab = bpe.BYTE_BASE + 24

        def deterministic(corpus: list[str]) -> bool:
            a = bpe.BPEModel.train(corpus, vocab_size=vocab)
            b = bpe.BPEModel.train(corpus, vocab_size=vocab)
            return a.merges == b.merges

        pbt.for_all(corpus_gen, deterministic, runs=60, label="train twice => equal merges")

    def test_save_load_preserves_encoding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "model.json"
            MODEL.save(path)
            loaded = bpe.BPEModel.load(path)
            pbt.for_all(
                pbt.text(max_len=80),
                lambda s: loaded.encode(s) == MODEL.encode(s),
                label="load(save(m)).encode == m.encode",
            )

    def test_encode_matches_naive_reference(self) -> None:
        # Safety net for the optimized (merge-all-per-rank) encode: it must agree
        # with the naive one-at-a-time reference for every input and every model.
        pbt.for_all(
            pbt.text(max_len=80),
            lambda s: MODEL.encode(s) == _reference_encode(MODEL, s),
            label="encode == naive reference (fixed model)",
        )

        def matches_on_random_model(corpus: list[str]) -> bool:
            model = bpe.BPEModel.train(corpus, vocab_size=bpe.BYTE_BASE + 40)
            sample = "".join(corpus)[:60]
            return model.encode(sample) == _reference_encode(model, sample)

        pbt.for_all(
            pbt.lists(pbt.text(max_len=24), min_len=1, max_len=6),
            matches_on_random_model,
            runs=60,
            label="encode == naive reference (random models)",
        )

    def test_encode_never_emits_special_ids(self) -> None:
        # Core safety invariant for downstream training: ordinary encode (even of
        # text containing special-token literals) must never emit a reserved id.
        pbt.for_all(
            _text_with_specials,
            lambda s: SPECIAL_IDS.isdisjoint(MODEL.encode(s)),
            label="encode emits no special ids",
        )
        # ...and such text still round-trips.
        pbt.for_all(
            _text_with_specials,
            lambda s: MODEL.decode(MODEL.encode(s)) == s,
            label="special-bearing text round-trips",
        )

    def test_encode_scales_on_large_in_domain_input(self) -> None:
        # Perf regression guard: the old O(n^2) encode took ~26s on 32KB; this
        # ~108KB in-domain input (which exercises deep merging) must finish fast.
        big = "the quick brown fox jumps over the lazy dog 0123456789\n" * 2000
        start = time.perf_counter()
        ids = MODEL.encode(big)
        elapsed = time.perf_counter() - start
        self.assertEqual(MODEL.decode(ids), big)
        self.assertLess(
            elapsed, 10.0, f"encode too slow ({elapsed:.2f}s) — possible O(n^2) regression"
        )


if __name__ == "__main__":
    unittest.main()
