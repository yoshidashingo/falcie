#!/usr/bin/env python3
"""Build the canonical eval-benchmark index for decontamination (fal'Cie L-007).

`data-policy.md` and `evaluation-plan.md` require the training corpus to be
decontaminated against the evaluation set before any training run — a model that
saw a benchmark item during pretraining produces meaningless scores. The
contamination stage (`scripts/data/contamination.py`) needs a single benchmark
file to check against; this builds that canonical "do-not-train-on-these" set by
gathering every eval text that must stay out of training:

  * the tokenizer probe texts (`evals/tokenizer/probes.jsonl`), and
  * the scored-suite **prompts and answers** (`evals/suites/smoke-scored.jsonl`).

Output (`evals/benchmark-index.jsonl`) is one ``{"id","text","source","field"}`` per
line, deduped by normalized text, deterministically ordered. Then decontaminate with:

    python3 scripts/data/contamination.py <corpus>.jsonl \
        --benchmarks evals/benchmark-index.jsonl --remove --output clean.jsonl

Use ``--check`` in CI to verify the committed index is still in sync with the suites.
Dependency-free (standard library only).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import records as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PROBES = ROOT / "evals" / "tokenizer" / "probes.jsonl"
SCORED_SUITE = ROOT / "evals" / "suites" / "smoke-scored.jsonl"
DEFAULT_OUTPUT = ROOT / "evals" / "benchmark-index.jsonl"

# Answers shorter than the contamination char-n-gram window (5) can only ever
# *exact-match* a training doc that is literally the answer string — a generic,
# signal-free token (e.g. "7", "C", "東京"). Including them risks removing such
# degenerate docs for no benefit, so floor answer rows at the n-gram length.
# Prompts are always included (they are the real contamination signal).
ANSWER_MIN_LEN = 5


def _rel(path: Path) -> str:
    """Repo-relative string, falling back to the raw path if outside ROOT."""
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
    return rows


def build_index() -> list[dict]:
    """Gather eval texts to protect, dedup by normalized text, order deterministically."""
    candidates: list[tuple[str, str, str]] = []  # (id, text, source/field)
    for rec in _read_jsonl(PROBES):
        candidates.append((f"probes:{rec['id']}", rec["text"], "probes/text"))
    for task in _read_jsonl(SCORED_SUITE):
        candidates.append((f"smoke-scored:{task['id']}:prompt", task["prompt"], "smoke-scored/prompt"))
        answer = str(task["answer"])
        if len(R.normalize_text(answer)) >= ANSWER_MIN_LEN:
            candidates.append((f"smoke-scored:{task['id']}:answer", answer, "smoke-scored/answer"))

    seen_norm: set[str] = set()
    index: list[dict] = []
    for item_id, text, field in candidates:
        norm = R.normalize_text(text)
        if not norm or norm in seen_norm:
            continue
        seen_norm.add(norm)
        index.append({"id": item_id, "text": text, "source": field})
    # Deterministic order independent of input ordering.
    index.sort(key=lambda r: r["id"])
    return index


def _serialize(index: list[dict]) -> str:
    return "\n".join(json.dumps(r, ensure_ascii=False) for r in index) + ("\n" if index else "")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    ap.add_argument("--check", action="store_true",
                    help="Verify the committed index matches a fresh build; exit 1 if stale.")
    args = ap.parse_args(argv[1:])

    index = build_index()
    if not index:
        print("error: benchmark index is empty (no eval suites found?)", file=sys.stderr)
        return 1
    serialized = _serialize(index)

    if args.check:
        if not args.output.exists():
            print(f"error: {_rel(args.output)} is missing; run without --check to build it",
                  file=sys.stderr)
            return 1
        current = args.output.read_text(encoding="utf-8")
        if current != serialized:
            print(f"error: {_rel(args.output)} is out of sync with the eval suites; "
                  f"rebuild with: python3 scripts/data/build_benchmark_index.py", file=sys.stderr)
            return 1
        print(f"benchmark index in sync: {len(index)} items")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(serialized, encoding="utf-8")
    print(f"wrote {_rel(args.output)} — {len(index)} benchmark items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
