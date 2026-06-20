#!/usr/bin/env python3
"""Dependency-free scoring metrics for the fal'Cie evaluation harness (unit U-E1).

Each metric is a pure ``Callable[[str, str, dict], bool]`` — ``(prediction,
target, task) -> passed`` — so a model output can be scored against a known
answer without any third-party library. The ``task`` dict is passed for metrics
that need extra fields (e.g. multiple-choice ``choices``); most ignore it.

These deliberately model *answer-checking*, not generation quality: that is the
part an automated harness can do reproducibly. Human review (evaluation-plan.md
layer 3) covers what these cannot.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from typing import Any

# Full-width digits etc. are folded so "１２" and "12" compare equal.
_PUNCT = re.compile(r"[\s!\"#$%&'()*+,\-./:;<=>?@\[\\\]^_`{|}~。、，．！？「」『』（）：；]+")
_NUMBER = re.compile(r"[-+]?\d[\d,]*\.?\d*")


def normalize(text: str) -> str:
    """Case-fold, NFKC-fold (full-width -> ASCII), strip surrounding punctuation
    and collapse internal whitespace/punctuation to single spaces."""
    folded = unicodedata.normalize("NFKC", text).casefold().strip()
    return _PUNCT.sub(" ", folded).strip()


def exact_match(prediction: str, target: str, task: dict[str, Any] | None = None) -> bool:
    """Whitespace-trimmed exact string equality."""
    return prediction.strip() == target.strip()


def normalized_match(prediction: str, target: str, task: dict[str, Any] | None = None) -> bool:
    """Equality after NFKC + case-fold + punctuation/whitespace normalization."""
    return normalize(prediction) == normalize(target)


def includes(prediction: str, target: str, task: dict[str, Any] | None = None) -> bool:
    """True when the normalized target appears anywhere in the normalized prediction.

    Substring semantics, so ``"def add"`` matches inside ``"def added"``. Suitable
    for "the answer must contain X" checks; for stricter code matching prefer a
    word-boundary check at the call site.
    """
    n_target = normalize(target)
    return bool(n_target) and n_target in normalize(prediction)


def numeric_match(prediction: str, target: str, task: dict[str, Any] | None = None) -> bool:
    """Compare the LAST number in the prediction to the target number.

    Tolerant of commas and trailing prose ("The answer is 144."). Uses a tiny
    relative+absolute tolerance so 144 and 144.0 match. Returns False if either
    side has no parseable number. Note: commas are treated as thousands
    separators, so a comma-separated list like "1, 2, 3" collapses to one number
    (3) — these tasks expect a single numeric answer, not a list.
    """
    pt = _last_number(prediction)
    tt = _last_number(target)
    if pt is None or tt is None:
        return False
    return abs(pt - tt) <= 1e-9 + 1e-9 * abs(tt)


def multiple_choice(prediction: str, target: str, task: dict[str, Any] | None = None) -> bool:
    """Check the chosen option letter against ``target`` (the correct letter, e.g. "C").

    Precision-first extraction — a clear answer is required, so prose like
    "A quick brown fox" is NOT scored as choosing A. Accepts only:
      1. a prediction that is a single letter ("C"),
      2. an explicit cue ("answer is C" / "answer: C"), or
      3. a parenthesized letter ("(C)").
    An ambiguous free-form answer with no clear marker scores False rather than
    guessing from the first letter found. The task's ``choices`` are validated at
    load time (``harness.load_suite``), so ``target`` is always a listed option.
    """
    want = target.strip().casefold()
    pred = prediction.strip()
    if len(pred) == 1:
        return pred.casefold() == want
    cue = re.search(r"answer\s*(?:is|:)?\s*\(?([A-Ja-j])\)?\b", prediction, re.I)
    if cue:
        return cue.group(1).casefold() == want
    paren = re.search(r"\(([A-Ja-j])\)", prediction)
    if paren:
        return paren.group(1).casefold() == want
    return False


def _last_number(text: str) -> float | None:
    matches = _NUMBER.findall(unicodedata.normalize("NFKC", text))
    if not matches:
        return None
    try:
        return float(matches[-1].replace(",", ""))
    except ValueError:
        return None


METRICS: dict[str, Callable[[str, str, dict[str, Any] | None], bool]] = {
    "exact_match": exact_match,
    "normalized_match": normalized_match,
    "includes": includes,
    "numeric_match": numeric_match,
    "multiple_choice": multiple_choice,
}


def score(metric: str, prediction: str, target: str, task: dict[str, Any] | None = None) -> bool:
    """Dispatch to a registered metric by name. Raises KeyError on unknown metric."""
    if metric not in METRICS:
        raise KeyError(f"unknown metric: {metric!r} (known: {', '.join(sorted(METRICS))})")
    return METRICS[metric](prediction, target, task)
