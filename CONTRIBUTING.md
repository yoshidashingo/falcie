# Contributing to fal'Cie

fal'Cie is an early open-weight language model project. Contributions should make the project more reproducible, measurable, and releasable.

## Current Priorities

The highest-value contributions are:

- Evaluation harness design
- Dataset manifest and license review process
- Data filtering and deduplication scripts
- Tokenizer experiments for Japanese, English, and code
- Training configuration templates
- Model-card and release documentation
- Safety and benchmark-contamination checks

## Ground Rules

- Do not commit raw datasets, model weights, credentials, or private data.
- Do not add data sources with unclear license terms.
- Do not make capability claims without evaluation evidence.
- Keep changes small and reviewable.
- Prefer reproducible scripts and configs over manual notebooks.
- Document assumptions and limitations.

## Development Workflow

1. Open an issue or draft a short proposal for substantial changes.
2. Keep implementation changes scoped to one workstream.
3. Add or update docs when behavior or policy changes.
4. Run relevant checks before requesting review.
5. Include evidence in pull requests: commands, outputs, screenshots, or benchmark summaries.

## Documentation Contributions

Documentation should be concrete and operational.

Good documentation:

- Names the file, script, config, or process being described.
- Explains inputs and outputs.
- States what is verified and what is not.
- Avoids unsupported performance claims.
- Links to source policies, licenses, or evaluation results.

## Data Contributions

For any proposed dataset, include:

- Dataset name
- Source URL
- License or terms
- Intended use
- Approximate size
- Language/domain coverage
- Known risks
- Suggested filters

Datasets without clear redistribution or training rights should be rejected or quarantined.

## Evaluation Contributions

Evaluation additions should include:

- Benchmark source
- License status
- Task definition
- Metric
- Prompt format
- Expected output format
- Contamination check strategy
- Smoke-test path

## Code Style

The implementation stack is not finalized yet. Until it is, prefer:

- Plain Python for scripts
- Config-driven behavior
- Deterministic outputs where possible
- Small modules with clear inputs and outputs
- No hidden service dependencies

## Release Discipline

A checkpoint is not release-ready until `docs/release-checklist.md` is complete. Release PRs should link to:

- Model card
- Evaluation report
- Data manifest
- Training config
- Safety notes
- Checksums

## Communication

Be precise. If a result is preliminary, label it preliminary. If a dataset or benchmark is uncertain, say so directly.
