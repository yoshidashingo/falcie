# Training Plan

This document outlines the staged training program required to turn fal'Cie from a public promise into a reproducible open-weight model release.

## Goals

- Validate the full pipeline at small scale before expensive runs.
- Keep every run reproducible through configs, seeds, dataset manifests, and checkpoint metadata.
- Optimize for Japanese, English, code, reasoning, and long-context performance.
- Build release candidates only after evaluation and safety gates exist.

## Staged Approach

### Stage 0: Infrastructure Smoke Tests

Purpose: prove that the repository can run end-to-end experiments.

Required outputs:

- Minimal dataset loader
- Tokenizer training smoke test
- Tiny model or external small-model evaluation harness
- Checkpoint save/load test
- Reproducible config format

### Stage 1: Tokenizer Selection

Compare tokenizer candidates on:

- Japanese compression ratio
- English compression ratio
- Code tokenization quality
- Mixed-language documents
- Long-context efficiency
- Special token design for chat, tools, and system messages

Exit criteria:

- Tokenizer artifacts are versioned.
- Evaluation notes explain the selection.
- Tokenizer license and generation process are documented.

### Stage 2: Sub-1B Experimental Models

Purpose: validate data quality, loss behavior, evaluation automation, and training stability.

Required checks:

- Training resumes after interruption.
- Loss curves are stable.
- Evaluation runs at fixed intervals.
- Data mix can be changed without code edits.
- Checkpoint metadata includes data manifest and config hashes.

### Stage 3: 1B to 7B Scaling Runs

Purpose: measure scaling behavior and prepare a credible first public release candidate.

Focus areas:

- Architecture selection
- Context length strategy
- Learning-rate schedule
- Data mixture optimization
- Instruction-tuning readiness
- Inference memory and throughput

### Stage 4: Instruction Tuning

Build instruction-following capability after a strong base model exists.

Inputs:

- Human-written instruction data where available
- High-quality synthetic instruction data with provenance
- Japanese task data
- Code repair and explanation data
- Safety and refusal examples

Methods to evaluate:

- Supervised fine-tuning
- Direct Preference Optimization
- RLAIF-style preference data
- Rejection sampling

### Stage 5: Release Candidate Training

A release candidate must be trained with frozen configs and documented inputs.

Required artifacts:

- Base model checkpoint
- Instruction-tuned checkpoint, if applicable
- Tokenizer
- Training config
- Data manifest
- Evaluation report
- Model card
- Release checklist

## Architecture Decisions To Make

The repository should explicitly decide and document:

- Dense vs MoE architecture
- Context length target
- Attention implementation
- Positional encoding strategy
- Tokenizer vocabulary size
- Training framework
- Distributed training stack
- Checkpoint format
- Quantization strategy

## Checkpoint Metadata

Every checkpoint should include:

- Model name
- Model size
- Architecture config
- Tokenizer version
- Training token count
- Dataset manifest hash
- Training config hash
- Commit SHA
- License
- Intended status: experiment, candidate, or release

## Operational Requirements

- Checkpoints must be resumable.
- Training logs must be preserved.
- Failed runs must produce actionable diagnostics.
- Evaluation must not require manual notebook execution.
- Release builds must be reproducible from documented configs.

## Immediate Implementation Tasks

1. Choose the first training framework.
2. Add `configs/training/` with a tiny smoke config.
3. Add checkpoint metadata schema.
4. Add tokenizer experiment plan.
5. Add automated evaluation hooks before scaling beyond smoke tests.
