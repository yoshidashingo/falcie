#!/usr/bin/env python3
"""A tiny, dependency-free property-based testing harness for fal'Cie.

The repository is standard-library-only by policy, which rules out Hypothesis
(the PBT framework the AI-DLC property-based-testing extension would otherwise
mandate). This module is the recorded substitute for that PBT-09 deviation: it
provides the three things the extension actually requires —

  * **custom, domain-appropriate generators** (PBT-07): see :func:`text`,
    :func:`lists`, :func:`integers`, :func:`sampled_from`, :func:`one_of`;
  * **automatic shrinking** of a failing case to a small reproducer (PBT-08);
  * **seed-based reproducibility** (PBT-08): every run is seeded, and the seed
    plus the shrunk counterexample are reported on failure.

It is intentionally small. It is not a Hypothesis replacement; it is enough to
express round-trip, invariant, idempotence, and oracle properties for the
dependency-free units in this repo and to fail loudly, reproducibly, and with a
minimal counterexample when a property does not hold.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from typing import Any

Gen = Callable[[random.Random], Any]
Prop = Callable[[Any], bool]

# A pool of "interesting" characters: ASCII, accented Latin, Japanese kana/kanji,
# an emoji (astral plane), and whitespace/control bytes. Generators draw from
# this pool plus occasional random valid codepoints so tests hit realistic,
# multi-byte, edge-y inputs rather than only ASCII.
_INTERESTING_CHARS: tuple[str, ...] = tuple(
    "abcXYZ0129 "  # ascii letters/digits/space
    "',.\"_-/\\#:{}[]()"  # punctuation that shows up in code/config
    "\n\t\r"  # whitespace
    "\x00\x01"  # control bytes
    "àéüñç"  # accented latin
    "あいうカナ漢字本語"  # japanese
    "🍣𠮷"  # emoji + astral-plane CJK
)

# Lone surrogates (U+D800..U+DFFF) cannot be UTF-8 encoded; exclude them so the
# generator only produces valid str values (PBT-07: domain-appropriate inputs).
_SURROGATE_LO = 0xD800
_SURROGATE_HI = 0xDFFF
_MAX_CODEPOINT = 0x10FFFF


class Counterexample(AssertionError):
    """Raised when a property fails. Message carries seed + minimal example."""


def _evaluate(prop: Prop, value: Any) -> tuple[bool, BaseException | None]:
    """Return ``(holds, error)``.

    A *truthy* return means the property holds. A raise means it does not — but the
    exception is captured (not swallowed) so a bug *inside* the property (a typo, a
    wrong attribute) surfaces in the failure message instead of masquerading as a
    product counterexample. A genuine crash in the code under test still counts as a
    counterexample, now with its exception type reported.
    """
    try:
        return bool(prop(value)), None
    except Exception as exc:  # noqa: BLE001 - any error is a counterexample for PBT
        return False, exc


def _holds(prop: Prop, value: Any) -> bool:
    """True iff the property holds for ``value`` (used during shrinking)."""
    return _evaluate(prop, value)[0]


def for_all(
    generator: Gen,
    prop: Prop,
    *,
    runs: int = 200,
    seed: int = 0,
    shrinks: int = 1000,
    label: str | None = None,
) -> None:
    """Assert ``prop`` holds for ``runs`` generated inputs; shrink on failure.

    Deterministic given ``seed``. On the first counterexample the input is shrunk
    to a minimal failing case and a :class:`Counterexample` is raised whose message
    includes the seed and the shrunk value so the failure can be replayed exactly.
    """
    rng = random.Random(seed)
    for _ in range(runs):
        value = generator(rng)
        holds, _ = _evaluate(prop, value)
        if not holds:
            minimal = _shrink(value, prop, budget=shrinks)
            _, error = _evaluate(prop, minimal)
            cause = (
                "property returned a falsy value"
                if error is None
                else f"property raised {type(error).__name__}: {error}"
            )
            name = f"{label}: " if label else ""
            raise Counterexample(
                f"{name}{cause} (seed={seed}); minimal counterexample: {minimal!r}"
            )


# --- generators -----------------------------------------------------------


def _random_char(rng: random.Random) -> str:
    if rng.random() < 0.8:
        return rng.choice(_INTERESTING_CHARS)
    while True:
        cp = rng.randint(0x20, _MAX_CODEPOINT)
        if not (_SURROGATE_LO <= cp <= _SURROGATE_HI):
            return chr(cp)


def text(min_len: int = 0, max_len: int = 40) -> Gen:
    """Generator of varied, valid (UTF-8-encodable) unicode strings."""

    def gen(rng: random.Random) -> str:
        length = rng.randint(min_len, max_len)
        return "".join(_random_char(rng) for _ in range(length))

    return gen


def integers(lo: int, hi: int) -> Gen:
    """Generator of ints in ``[lo, hi]``."""

    def gen(rng: random.Random) -> int:
        return rng.randint(lo, hi)

    return gen


def sampled_from(values: Sequence[Any]) -> Gen:
    """Generator that picks one element from ``values``."""
    pool = list(values)

    def gen(rng: random.Random) -> Any:
        return rng.choice(pool)

    return gen


def lists(element: Gen, min_len: int = 0, max_len: int = 8) -> Gen:
    """Generator of lists whose elements come from ``element``."""

    def gen(rng: random.Random) -> list[Any]:
        length = rng.randint(min_len, max_len)
        return [element(rng) for _ in range(length)]

    return gen


def one_of(*generators: Gen) -> Gen:
    """Generator that delegates to a randomly chosen sub-generator."""
    if not generators:
        raise ValueError("one_of requires at least one generator")

    def gen(rng: random.Random) -> Any:
        return rng.choice(generators)(rng)

    return gen


# --- shrinking ------------------------------------------------------------


def _shrink_candidates(value: Any) -> list[Any]:
    """Yield structurally-smaller variants of ``value`` (one shrink step)."""
    candidates: list[Any] = []

    if isinstance(value, str):
        if value == "":
            return []
        # Drop a contiguous half, then drop single characters, then simplify chars.
        half = len(value) // 2
        if half:
            candidates.append(value[:half])
            candidates.append(value[half:])
        for i in range(len(value)):
            candidates.append(value[:i] + value[i + 1 :])
        for i, ch in enumerate(value):
            if ch != "a":
                candidates.append(value[:i] + "a" + value[i + 1 :])
        return candidates

    if isinstance(value, (list, tuple)):
        seq = list(value)
        if not seq:
            return []
        half = len(seq) // 2
        if half:
            candidates.append(_rewrap(value, seq[:half]))
            candidates.append(_rewrap(value, seq[half:]))
        for i in range(len(seq)):
            candidates.append(_rewrap(value, seq[:i] + seq[i + 1 :]))
        for i, elem in enumerate(seq):
            for smaller in _shrink_candidates(elem):
                candidates.append(_rewrap(value, seq[:i] + [smaller] + seq[i + 1 :]))
        return candidates

    if isinstance(value, int):
        if value == 0:
            return []
        candidates.append(0)
        candidates.append(value // 2)
        if value > 0:
            candidates.append(value - 1)
        else:
            candidates.append(value + 1)
        return candidates

    return candidates


def _rewrap(original: Any, items: list[Any]) -> Any:
    return tuple(items) if isinstance(original, tuple) else items


def _shrink(value: Any, prop: Prop, *, budget: int) -> Any:
    """Greedily reduce ``value`` to a smaller still-failing input."""
    current = value
    while budget > 0:
        progressed = False
        for candidate in _shrink_candidates(current):
            budget -= 1
            if budget <= 0:
                break
            if not _holds(prop, candidate):
                current = candidate
                progressed = True
                break
        if not progressed:
            break
    return current
