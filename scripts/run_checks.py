#!/usr/bin/env python3
"""Run every fal'Cie verification gate with one command (unit U-I6).

This is the Loop-Engineering gate for the repo: it runs the dependency-free
validators, the tokenizer pipeline, and the test suite, then prints a pass/fail
summary and exits non-zero if anything failed. Intended for local use and CI.

    python3 scripts/run_checks.py

Each check is a subprocess so a crash in one does not abort the rest.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


# (label, argv) — argv is run from the repo root.
CHECKS: list[tuple[str, list[str]]] = [
    ("validate_manifest", [PY, "scripts/data/validate_manifest.py"]),
    ("smoke_eval", [PY, "scripts/evals/run_smoke_eval.py"]),
    ("summarize_probes", [PY, "scripts/tokenizer/summarize_probes.py"]),
    ("score_tokenizer", [PY, "scripts/tokenizer/score_tokenizer.py"]),
    ("select_tokenizer", [PY, "scripts/tokenizer/select_tokenizer.py", "--no-write"]),
    ("unit_tests", [PY, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]),
]


def run_check(label: str, argv: list[str]) -> bool:
    print(f"==> {label}")
    result = subprocess.run(argv, cwd=ROOT)
    ok = result.returncode == 0
    print(f"    {'PASS' if ok else 'FAIL'} ({label}, exit={result.returncode})")
    return ok


def main() -> int:
    results = [(label, run_check(label, argv)) for label, argv in CHECKS]
    print("\n--- summary ---")
    failed = [label for label, ok in results if not ok]
    for label, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")
    if failed:
        print(f"\n{len(failed)} check(s) failed: {', '.join(failed)}")
        return 1
    print(f"\nall {len(results)} checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
