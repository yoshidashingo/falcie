#!/usr/bin/env python3
"""Train a byte-level BPE tokenizer from a corpus (fal'Cie unit U-T2).

Dependency-free. Reads a corpus, trains a :class:`bpe.BPEModel`, optionally saves
it, and prints a short summary (vocab size, merge count, compression on the corpus).

Corpus input:
  * ``.jsonl`` file  -> the ``text`` field of each record is one corpus line
                        (matches ``evals/tokenizer/probes.jsonl``).
  * any other file   -> each line is one corpus line.
  * default          -> the probe fixture, so the command runs in a clean checkout.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpe  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS = ROOT / "evals" / "tokenizer" / "probes.jsonl"
DEFAULT_SPECIAL_TOKENS = [
    "<bos>",
    "<eos>",
    "<pad>",
    "<system>",
    "<user>",
    "<assistant>",
    "<tool_call>",
    "<tool_result>",
]


def read_corpus(path: Path) -> list[str]:
    """Read corpus lines from a .jsonl (``text`` field) or plain text file."""
    raw = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        lines: list[str] = []
        for line_no, line in enumerate(raw.splitlines(), 1):
            if not line.strip():
                continue
            record = json.loads(line)
            text = record.get("text")
            if not isinstance(text, str) or not text:
                raise ValueError(f"{path}:{line_no}: record has no non-empty 'text'")
            lines.append(text)
        return lines
    return [line for line in raw.splitlines() if line]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", nargs="?", default=str(DEFAULT_CORPUS))
    parser.add_argument("--vocab-size", type=int, default=1024)
    parser.add_argument(
        "--special-token",
        action="append",
        dest="special_tokens",
        help="Reserved special token. Repeatable. Defaults to the chat/tool set.",
    )
    parser.add_argument("--output", type=Path, help="Where to save the model JSON.")
    args = parser.parse_args(argv[1:])

    corpus_path = Path(args.corpus)
    corpus = read_corpus(corpus_path)
    specials = args.special_tokens if args.special_tokens is not None else DEFAULT_SPECIAL_TOKENS

    model = bpe.BPEModel.train(corpus, vocab_size=args.vocab_size, special_tokens=specials)

    corpus_bytes = sum(len(line.encode("utf-8")) for line in corpus)
    corpus_tokens = sum(model.token_count(line) for line in corpus)
    ratio = round(corpus_tokens / corpus_bytes, 4) if corpus_bytes else 0.0

    summary = {
        "corpus": str(corpus_path.relative_to(ROOT)) if corpus_path.is_relative_to(ROOT) else str(corpus_path),
        "corpus_lines": len(corpus),
        "vocab_size": model.vocab_size,
        "special_tokens": model.special_tokens,
        "learned_merges": len(model.merges),
        "corpus_bytes": corpus_bytes,
        "corpus_tokens": corpus_tokens,
        "tokens_per_byte": ratio,
    }

    if args.output:
        model.save(args.output)
        summary["saved_to"] = str(args.output)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
