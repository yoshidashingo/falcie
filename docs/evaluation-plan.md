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
- Run near-duplicate search against public benchmark prompts.
- Track benchmark leakage findings in release notes.
- Avoid tuning directly to leaderboard quirks.

## Initial Implementation Tasks

1. Create `evals/README.md` with benchmark inventory.
2. Add a machine-readable evaluation config format.
3. Add a script that runs a tiny smoke evaluation on a mock or small local model.
4. Add a result schema for score reports.
5. Require evaluation output before any release tag.
