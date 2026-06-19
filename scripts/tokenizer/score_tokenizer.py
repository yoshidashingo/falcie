#!/usr/bin/env python3
"""Score tokenizer compression on the fal'Cie probe fixture.

This is a dependency-free *baseline* scorer. It measures tokens-per-character
and tokens-per-byte for reference tokenizers (byte, char, whitespace) so that
future subword tokenizer candidates have a stable comparison floor.

The byte tokenizer is the canonical reference: it never compresses, so its
token count is the upper bound that every real candidate must beat. The char
and whitespace tokenizers bracket the space from the other side.

No external tokenizer library is required. A real candidate can be added later
by registering a ``Callable[[str], int]`` in ``TOKENIZERS`` (or by wrapping a
library's encoder), after which the same compression report applies to it.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROBES = ROOT / "evals" / "tokenizer" / "probes.jsonl"
REQUIRED_FIELDS = {"id", "language", "domain", "text"}


def load_probes(path: Path) -> list[dict[str, Any]]:
    """Load and validate the probe JSONL fixture.

    Mirrors the validation in ``summarize_probes.py`` so the scorer fails the
    same way on a malformed fixture instead of silently scoring garbage.
    """
    probes: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            probe = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc

        missing = REQUIRED_FIELDS - probe.keys()
        if missing:
            raise ValueError(f"{path}:{line_no}: missing fields: {sorted(missing)}")
        for field in REQUIRED_FIELDS:
            if not isinstance(probe[field], str) or not probe[field]:
                raise ValueError(f"{path}:{line_no}: {field} must be a non-empty string")
        if probe["id"] in seen_ids:
            raise ValueError(f"{path}:{line_no}: duplicate id: {probe['id']}")
        seen_ids.add(probe["id"])
        probes.append(probe)

    if not probes:
        raise ValueError(f"{path}: no probes found")
    return probes


# --- reference tokenizers -------------------------------------------------


def tokenize_byte(text: str) -> int:
    """UTF-8 byte count. The no-compression upper bound."""
    return len(text.encode("utf-8"))


def tokenize_char(text: str) -> int:
    """Unicode codepoint count. One token per character."""
    return len(text)


def tokenize_whitespace(text: str) -> int:
    """Whitespace-delimited word count. A very coarse lower bound."""
    return len(text.split())


TOKENIZERS: dict[str, Callable[[str], int]] = {
    "byte": tokenize_byte,
    "char": tokenize_char,
    "whitespace": tokenize_whitespace,
}


def _ratio(numer: int, denom: int) -> float:
    return round(numer / denom, 4) if denom else 0.0


def _summarize_bucket(bucket: dict[str, dict[str, int]]) -> dict[str, dict[str, Any]]:
    return {
        key: {
            **totals,
            "tokens_per_char": _ratio(totals["tokens"], totals["chars"]),
            "tokens_per_byte": _ratio(totals["tokens"], totals["bytes"]),
        }
        for key, totals in sorted(bucket.items())
    }


def score(
    probes: list[dict[str, Any]],
    tokenizer_name: str,
    tokenizer: Callable[[str], int],
) -> dict[str, Any]:
    per_probe: list[dict[str, Any]] = []
    by_language: dict[str, dict[str, int]] = defaultdict(
        lambda: {"tokens": 0, "chars": 0, "bytes": 0}
    )
    by_domain: dict[str, dict[str, int]] = defaultdict(
        lambda: {"tokens": 0, "chars": 0, "bytes": 0}
    )
    overall = {"tokens": 0, "chars": 0, "bytes": 0}

    for probe in probes:
        text = probe["text"]
        counts = {
            "tokens": tokenizer(text),
            "chars": len(text),
            "bytes": len(text.encode("utf-8")),
        }
        per_probe.append(
            {
                "id": probe["id"],
                "language": probe["language"],
                "domain": probe["domain"],
                **counts,
                "tokens_per_char": _ratio(counts["tokens"], counts["chars"]),
                "tokens_per_byte": _ratio(counts["tokens"], counts["bytes"]),
            }
        )
        for bucket, key in ((by_language, probe["language"]), (by_domain, probe["domain"])):
            for field in overall:
                bucket[key][field] += counts[field]
        for field in overall:
            overall[field] += counts[field]

    return {
        "tokenizer": tokenizer_name,
        "probe_count": len(probes),
        "overall": {
            **overall,
            "tokens_per_char": _ratio(overall["tokens"], overall["chars"]),
            "tokens_per_byte": _ratio(overall["tokens"], overall["bytes"]),
        },
        "by_language": _summarize_bucket(by_language),
        "by_domain": _summarize_bucket(by_domain),
        "per_probe": per_probe,
    }


def _rel(path: Path) -> str:
    """Repo-relative string — committed reports must not embed absolute paths
    (repo Git rule). Falls back to the basename for paths outside the repo."""
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return resolved.name


def render_markdown(reports: list[dict[str, Any]], probe_path: Path) -> str:
    lines: list[str] = []
    lines.append("# Tokenizer Compression Report")
    lines.append("")
    lines.append(f"- probe_file: `{_rel(probe_path)}`")
    lines.append(f"- probes: {reports[0]['probe_count']}")
    lines.append(f"- tokenizers: {', '.join(r['tokenizer'] for r in reports)}")
    lines.append("")

    lines.append("## Overall")
    lines.append("")
    lines.append("| tokenizer | tokens | chars | bytes | tokens/char | tokens/byte |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for report in reports:
        o = report["overall"]
        lines.append(
            f"| {report['tokenizer']} | {o['tokens']} | {o['chars']} | {o['bytes']} "
            f"| {o['tokens_per_char']} | {o['tokens_per_byte']} |"
        )
    lines.append("")

    for report in reports:
        for dimension, label in (("by_language", "language"), ("by_domain", "domain")):
            lines.append(f"## {report['tokenizer']} — by {label}")
            lines.append("")
            lines.append(
                f"| {label} | tokens | chars | bytes | tokens/char | tokens/byte |"
            )
            lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
            for key, vals in report[dimension].items():
                lines.append(
                    f"| {key} | {vals['tokens']} | {vals['chars']} | {vals['bytes']} "
                    f"| {vals['tokens_per_char']} | {vals['tokens_per_byte']} |"
                )
            lines.append("")

    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("probes", nargs="?", default=str(DEFAULT_PROBES))
    parser.add_argument(
        "--tokenizer",
        action="append",
        choices=sorted(TOKENIZERS),
        help="Tokenizer(s) to score. Repeatable. Defaults to all baselines.",
    )
    parser.add_argument("--format", choices=["json", "md"], default="json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv[1:])

    probe_path = Path(args.probes)
    probes = load_probes(probe_path)

    names = args.tokenizer or sorted(TOKENIZERS)
    reports = [score(probes, name, TOKENIZERS[name]) for name in names]

    if args.format == "md":
        output = render_markdown(reports, probe_path)
    else:
        payload = {
            "probe_file": _rel(probe_path),
            "reports": reports,
        }
        output = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
