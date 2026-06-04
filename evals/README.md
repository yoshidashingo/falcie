# fal'Cie Evaluations

This directory contains evaluation fixtures and harness entry points for fal'Cie.

The project should have evaluation infrastructure before expensive model training begins. Early files are intentionally lightweight and dependency-free so they can run in a clean checkout.

## Current Structure

- `tokenizer/probes.jsonl`: tokenizer comparison probes.

Planned structure:

- `configs/evals/`: evaluation suite definitions.
- `scripts/evals/`: evaluation runners and validators.
- `evals/results/`: generated result summaries. Do not commit large outputs.

## Evaluation Principles

- Capability claims must map to versioned evaluation results.
- Public benchmark configurations must be reproducible.
- Private regression data should not be committed if it would leak the test set.
- Benchmark contamination checks must run before release.
- Evaluation output should include model identifier, config identifier, commit SHA, and known limitations.

## Smoke Evaluation

The initial smoke runner validates evaluation configuration shape and emits a small JSON report. It does not evaluate a language model yet.

Run:

```bash
python3 scripts/evals/run_smoke_eval.py configs/evals/smoke.yaml
```

This gives the repository an executable evaluation entry point before a model implementation exists.

## Release Gate

No model checkpoint should be released until:

- Evaluation config is pinned.
- Evaluation runner executes from a clean checkout.
- Results are stored in a reviewable format.
- Model card references the exact evaluation report.
