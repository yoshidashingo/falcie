# Technology Stack

## Programming Languages
- **Python 3** — only language with executable code. Uses `from __future__ import annotations` and PEP 585 generics (`dict[str, Any]`, `list[str]`), so 3.9+ syntactically. Local bytecode (`*.cpython-314.pyc`) indicates CPython 3.14 was used to run it.
- **Markdown** — all governance docs.
- **HTML** — `docs/index.html`, `docs/ja.html` (GitHub Pages landing).
- **YAML (JSON subset)** — config/spec files are authored in JSON syntax with `.yaml` extension and parsed with `json.loads`.
- **JSONL** — tokenizer probe fixtures.

## Frameworks
- **None.** No web framework, no ML framework, no test framework yet. All tooling is Python standard library only.

## Infrastructure
- **None deployed.** No cloud resources, containers, or IaC.
- **Planned (per docs)**: Hugging Face + GitHub Releases for distribution; a PyTorch/Hugging Face-compatible training path is the proposed starting direction (ADR-001), dense decoder-only model family proposed (ADR-002), safetensors-compatible checkpoints proposed (ADR-005).

## Build Tools
- **None.** No package manager, lockfile, or build script. Scripts execute directly via `python3`.

## Testing Tools
- **None formal.** Validation is performed by the scripts themselves (self-checking validators). No pytest/unittest suites present yet.

## Version Control / Automation
- **Git** — repository is a git repo; `run_smoke_eval.py` reads `git rev-parse HEAD` for provenance (optional, degrades to `"unknown"`).
- **CI/CD** — none present (no `.github/workflows/`).
