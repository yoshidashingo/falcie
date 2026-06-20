# Evaluation Plan

fal'Cie will not claim frontier capability without repeatable evaluation evidence. This document defines what must be measured before any model release.

## Goals

- Measure broad capability, not only benchmark memorization.
- Track Japanese, English, code, math, long-context, and instruction-following performance separately.
- Detect regressions between base, instruction-tuned, and aligned checkpoints.
- Make release claims reproducible wherever benchmark licenses allow.

## Evaluation Layers

### 1. Public Benchmarks

Use public benchmarks for comparability with existing models.

Initial target areas:

- General knowledge and reasoning
- Mathematical reasoning
- Code generation and debugging
- Multilingual understanding
- Japanese language tasks
- Long-context retrieval and synthesis
- Instruction following

Candidate benchmark families:

- MMLU-style academic reasoning
- GPQA-style hard reasoning
- GSM8K/MATH-style math
- HumanEval/MBPP-style code
- Japanese benchmark suites such as JGLUE-style tasks where licensing permits
- MT-Bench/AlpacaEval-style instruction following
- Needle-in-a-haystack and long-context retrieval tests

Exact benchmark choices must be pinned in `evals/` before release.

### 2. Private Regression Set

A private regression set is required to reduce benchmark overfitting.

It should include:

- Japanese business writing and summarization tasks
- Long Japanese and English document QA
- Code repair tasks not present in public datasets
- Multi-turn instruction-following tests
- Safety and refusal edge cases
- Hallucination traps with unknown or false premises

Only aggregate results should be published if the dataset must remain private.

### 3. Human Review

Automated scores are insufficient for release decisions.

Review should cover:

- Helpfulness
- Factuality
- Japanese fluency and register control
- Code correctness beyond unit tests
- Refusal quality
- Overconfidence and hallucination behavior
- Comparative preference against prior fal'Cie checkpoints

## Release Gates

A checkpoint can become a public release candidate only when:

- Evaluation harness runs from a clean checkout.
- Public benchmark results are versioned and reproducible.
- Private regression set shows no critical regression against the previous candidate.
- Safety evaluation has no unresolved release blockers.
- Model card includes limitations and intended use.
- Contamination checks have been run for public benchmarks.

## Reporting Format

Each evaluated checkpoint should publish:

- Model identifier
- Base or instruction-tuned status
- Training token count
- Context length
- Evaluation harness version
- Benchmark versions
- Score table
- Known failures
- Comparison against prior fal'Cie checkpoint

## Anti-Contamination Rules

- Keep benchmark datasets out of training data unless explicitly allowed for supervised training and disclosed.
- Run near-duplicate search against public benchmark prompts. Wired: the eval texts
  are aggregated into `evals/benchmark-index.jsonl`
  (`scripts/data/build_benchmark_index.py`) and the training corpus is decontaminated
  against it with `scripts/data/contamination.py` (exact + char-n-gram Jaccard).
- Track benchmark leakage findings in release notes.
- Avoid tuning directly to leaderboard quirks.

## Initial Implementation Tasks

1. ~~Create `evals/README.md` with benchmark inventory.~~ Done.
2. ~~Add a machine-readable evaluation config format.~~ Done (`configs/evals/smoke.yaml`
   shape config; `evals/suites/*.jsonl` scored-task format).
3. ~~Add a script that runs a tiny smoke evaluation on a mock or small local
   model.~~ Done (`run_smoke_eval.py` shape, `run_mock_eval.py` mock scoring path).
4. ~~Add a result schema for score reports.~~ Done (L-004): `scripts/evals/harness.py`
   produces a versioned report (harness version, model id, commit, accuracy overall +
   by area/language, known failures) scored by real metrics (`scripts/evals/metrics.py`).
5. Require evaluation output before any release tag — enforceable now: the harness
   self-checks in `scripts/run_checks.py` (gold predictor must score 1.0, empty 0.0),
   so a release gate can require a scored report from `run_eval.py` once a model exists.

## Scored Harness (L-004)

`scripts/evals/run_eval.py` runs a predictor over a scored suite
(`evals/suites/smoke-scored.jsonl`) and emits the report above. A predictor is
`Callable[[task], str]`; reference predictors (`gold`/`empty`/`echo`) validate the
harness without a model. Suites under `evals/suites/` are harness fixtures, not
benchmarks (no contamination risk). When a real model lands, plug its `predict`
into the harness — the scoring, aggregation, and report shape are already in place.

## Base-LM Evaluation — bits-per-byte (L-005)

Base (pre-instruction) checkpoints are judged by **bits-per-byte (BPB)** and
perplexity on held-out text — the answer-checking harness above is for instruction
models. `scripts/evals/lm_eval.py` trains a model on a train split and reports BPB
overall and per language on a disjoint held-out slice; a uniform model scores
log2(256) = 8.0 bits/byte, the floor any learned model must beat.

The first evaluable series member is a **dependency-free byte n-gram baseline**
(`scripts/model/ngram_lm.py`) — a floor, not a capability claim. On the held-out
public-domain corpus it reaches ~2.18 bits/byte at order 3 (perplexity ~4.5),
closing the data -> tokenizer -> model -> eval loop end to end. See
[`evals/lm-baseline-report.md`](evals/lm-baseline-report.md). A real model (M2+)
plugs into the same BPB metric; the raw corpus and trained model are not committed
(regenerable via `scripts/data/fetch_corpus.py` + `scripts/evals/lm_eval.py`).

## Long-Context Evaluation — needle-in-a-haystack (L-008)

Context extension must be validated, not assumed (ADR-004 gates it on
needle-in-a-haystack). `scripts/evals/niah.py` synthesizes NIAH tasks — a unique
needle fact embedded in filler at a chosen depth, with a retrieval question — and
scores a predictor across a **length x depth grid**, producing a retrieval matrix.
Reference predictors validate the eval without a model: `gold` retrieves every
needle (1.0), `empty` none (0.0), and a `window:<N>` prefix stand-in shows real
length x depth structure (short/shallow found, long/deep missed). A real model (M2+)
plugs in as the predictor when context extension is tested.
