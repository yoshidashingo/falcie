# fal'Cie Evaluations

This directory contains evaluation fixtures and harness entry points for fal'Cie.

The project should have evaluation infrastructure before expensive model training begins. Early files are intentionally lightweight and dependency-free so they can run in a clean checkout.

## Current Structure

- `tokenizer/probes.jsonl`: tokenizer comparison probes.
- `suites/smoke-scored.jsonl`: a small **scored** suite (answers + metrics) used to
  exercise the scoring harness. These are **harness fixtures, not benchmarks** —
  trivial, self-contained items whose only job is to prove the harness scores
  correctly. They are deliberately NOT drawn from any public benchmark, so they
  carry no contamination risk and must never be treated as a capability claim.

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

## Scored Evaluation Harness

The scored harness (L-004) goes beyond shape validation: it compares a predictor's
output to a known answer with real metrics (`exact_match`, `normalized_match`,
`includes`, `numeric_match`, `multiple_choice`) and aggregates accuracy overall and
by area/language, in the report shape `docs/evaluation-plan.md` requires.

```bash
python3 scripts/evals/run_eval.py --predictor gold    # reference: must score 1.0
python3 scripts/evals/run_eval.py --predictor empty   # reference: must score 0.0
python3 scripts/evals/run_eval.py evals/suites/smoke-scored.jsonl \
    --output evals/results/smoke.json
```

A **predictor** is `Callable[[task], str]`. The built-in reference predictors
(`gold`, `empty`, `echo`) let the harness be validated **without a model** — `gold`
scores 1.0 and `empty` scores 0.0, proving the scoring path is wired correctly
(both are asserted in `scripts/run_checks.py`). When a real model exists, register
its `predict(task) -> str` in place of a reference predictor; nothing else changes.

`evals/results/` outputs are not committed (see `.gitignore`); the report is
regenerated from the pinned suite + the model under test.

## Base-LM Evaluation (bits-per-byte)

For *base* (pre-instruction) checkpoints the relevant metric is bits-per-byte (BPB)
/ perplexity on held-out text, not answer accuracy. `scripts/evals/lm_eval.py`
trains a model on a train split and reports BPB overall + per language on a disjoint
held-out slice (uniform floor = 8.0 bits/byte).

```bash
python3 scripts/evals/lm_eval.py --corpus data/bakeoff/corpus.jsonl --orders 0 1 2 3 \
    --output docs/evals/lm-baseline-report.json
```

The first member is a dependency-free byte n-gram baseline
(`scripts/model/ngram_lm.py`) — a floor, not a capability claim — which reaches
~2.18 bits/byte on the held-out public-domain corpus. The committed report lives in
`docs/evals/`; the corpus and trained model are not committed (regenerable).

## Release Gate

No model checkpoint should be released until:

- Evaluation config is pinned.
- Evaluation runner executes from a clean checkout.
- Results are stored in a reviewable format.
- Model card references the exact evaluation report.
