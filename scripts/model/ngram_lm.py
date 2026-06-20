#!/usr/bin/env python3
"""Dependency-free byte-level n-gram language model (fal'Cie L-005, unit U-M1).

A deliberately trivial *baseline* model — a floor, not a capability claim — whose
only jobs are (1) to close the data -> tokenizer -> model -> eval loop end to end
and (2) to give the base-LM metric (bits-per-byte / perplexity) a real model to
score. A real neural model (M2+) replaces it behind the same interface.

The model interpolates byte n-gram estimates of orders 0..N with a uniform floor,
renormalized so that for any context the probabilities over the 256 byte values
sum to 1 and are strictly positive. That makes bits-per-byte finite and the model
a proper distribution. Deterministic: identical training text -> identical model.

`order` is the maximum context length (bytes of history). Higher order fits the
training text better; on held-out text it helps until contexts get too sparse.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable

BYTE_VALUES = 256


class NgramLM:
    def __init__(self, order: int, base: float = 4.0, floor_weight: float = 0.1) -> None:
        if order < 0:
            raise ValueError("order must be >= 0")
        if floor_weight <= 0:
            # The uniform floor is what keeps every byte > 0 (and BPB finite);
            # a zero floor would reintroduce zero-probability bytes.
            raise ValueError("floor_weight must be > 0")
        self.order = order
        self.floor_weight = floor_weight
        # weights[k] favours higher orders geometrically; renormalization (Z) makes
        # absent orders back off automatically.
        self.weights = [base ** k for k in range(order + 1)]
        # counts[k]: context-tuple(length k) -> {byte: count}; totals[k]: context -> sum.
        self.counts: list[dict[tuple[int, ...], dict[int, int]]] = [defaultdict(dict) for _ in range(order + 1)]
        self.totals: list[dict[tuple[int, ...], int]] = [defaultdict(int) for _ in range(order + 1)]

    @classmethod
    def train(cls, texts: Iterable[str], order: int, **kw) -> "NgramLM":
        model = cls(order, **kw)
        for text in texts:
            data = text.encode("utf-8")
            n = len(data)
            for i in range(n):
                nxt = data[i]
                for k in range(order + 1):
                    if k > i:
                        break
                    ctx = tuple(data[i - k:i])
                    bucket = model.counts[k][ctx]
                    bucket[nxt] = bucket.get(nxt, 0) + 1
                    model.totals[k][ctx] += 1
        return model

    def prob(self, context: tuple[int, ...] | bytes, byte: int) -> float:
        """Normalized P(byte | context) in (0, 1]. Only the orders whose context was
        seen in training contribute; a uniform floor keeps every byte > 0."""
        num = self.floor_weight / BYTE_VALUES
        z = self.floor_weight
        ctx_seq = tuple(context)
        clen = len(ctx_seq)
        for k in range(self.order + 1):
            if k > clen:
                break
            ctx = ctx_seq[clen - k:] if k else ()
            bucket = self.counts[k].get(ctx)
            if bucket:
                num += self.weights[k] * bucket.get(byte, 0) / self.totals[k][ctx]
                z += self.weights[k]
        return num / z

    def distribution(self, context: tuple[int, ...] | bytes) -> list[float]:
        """Full normalized distribution over the 256 bytes (sums to 1.0)."""
        return [self.prob(context, b) for b in range(BYTE_VALUES)]

    def bits_per_byte(self, text: str) -> float:
        """Average -log2 P(next byte | context) over ``text`` (UTF-8 bytes).

        This is the standard base-LM metric: lower is better; a uniform model
        scores log2(256) = 8.0 bits/byte, which any learned model must beat.
        Returns 0.0 for empty text.
        """
        data = text.encode("utf-8")
        if not data:
            return 0.0
        total_bits = 0.0
        for i in range(len(data)):
            ctx = data[max(0, i - self.order):i]
            p = self.prob(ctx, data[i])
            total_bits += -math.log2(p)
        return total_bits / len(data)

    def perplexity(self, text: str) -> float:
        """Per-byte perplexity = 2 ** bits_per_byte."""
        return 2.0 ** self.bits_per_byte(text)


UNIFORM_BPB = math.log2(BYTE_VALUES)  # 8.0 — the floor a learned model must beat
