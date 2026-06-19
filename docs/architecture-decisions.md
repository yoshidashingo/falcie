# Architecture Decisions

This file tracks major technical decisions that must be made before fal'Cie can train and release serious checkpoints.

The goal is not to decide everything upfront. The goal is to make each decision explicit, evidence-backed, and revisable.

## Decision Status

Use these labels:

- Proposed: plausible direction, not yet validated.
- Testing: actively being evaluated.
- Accepted: selected for the next implementation stage.
- Rejected: considered and not selected.
- Superseded: replaced by a newer decision.

## ADR-001: Training Framework

Status: Proposed

Candidates:

- PyTorch with native distributed training
- Hugging Face Transformers plus Accelerate
- Megatron-LM style stack
- DeepSpeed-based stack
- JAX-based stack

Decision criteria:

- Reproducibility
- Multi-node scalability
- Checkpoint compatibility
- Community familiarity
- Long-context support
- Ease of evaluation integration

Current direction:

Start with a simple PyTorch/Hugging Face-compatible path for smoke tests, then revisit for larger-scale training.

## ADR-002: Model Family

Status: Proposed

Candidates:

- Dense decoder-only Transformer
- Mixture-of-Experts decoder-only Transformer
- Hybrid approaches for long context or retrieval

Decision criteria:

- Training stability
- Inference deployability
- Scaling efficiency
- Open implementation maturity
- Japanese and code performance

Current direction:

Begin with dense decoder-only experimental models to reduce pipeline complexity. Revisit MoE when data, evaluation, and training infrastructure are stable.

## ADR-003: Tokenizer Strategy

Status: Proposed

Requirements:

- Strong Japanese compression
- Strong English compression
- Code-friendly segmentation
- Stable special tokens for chat, tools, and system messages
- Reproducible training process

Current direction:

Run tokenizer bakeoffs before any non-smoke model training.

Progress (M1, 2026-06-19): a dependency-free, clean-room byte-level BPE tokenizer
(`scripts/tokenizer/bpe.py`) plus a training CLI (`scripts/tokenizer/train_bpe.py`)
and a selection harness (`scripts/tokenizer/select_tokenizer.py`) now exist and
emit a reproducible selection report (`docs/tokenizers/selection-report.md`). A
byte-level base alphabet (256 byte tokens) was chosen so encoding is lossless —
no unknown tokens, and `decode(encode(x)) == x` for all text — verified by
property-based tests (`tests/test_bpe_pbt.py`). This is the bakeoff scaffolding;
the final vocabulary size and training corpus remain Proposed pending a held-out
training corpus and the full criteria in `tokenizer-evaluation.md`.

## ADR-004: Context Length Strategy

Status: Proposed

Decision criteria:

- Training cost
- Long-context benchmark performance
- Inference memory
- Attention implementation
- Compatibility with deployment libraries

Current direction:

Start with moderate context for experimental models, then scale context only after long-context evals and infrastructure are ready.

## ADR-005: Checkpoint Format

Status: Proposed

Requirements:

- Safe tensor format where possible
- Hugging Face compatibility for distribution
- Checksums for all release artifacts
- Metadata linking checkpoint to data manifest and training config

Current direction:

Use safetensors-compatible release artifacts whenever possible.

## ADR-006: Testing Strategy and Property-Based Testing

Status: Accepted (for the dependency-free phase)

Context:

The repository is standard-library-only by policy, and the AI-DLC
property-based-testing extension is enabled (full). PBT-09 would normally mandate
Hypothesis, which is a third-party dependency and therefore disallowed in the
current phase.

Decision:

- Use the stdlib `unittest` runner; tests live under `tests/` and run via
  `python3 -m unittest discover -s tests` (wrapped by `scripts/run_checks.py`).
- Provide a small dependency-free PBT harness (`tests/pbt.py`) supplying seedable
  domain generators, automatic shrinking, and reproducible seeds — the
  capabilities PBT-07/PBT-08 require — in place of Hypothesis.
- Revisit and migrate to Hypothesis when the project adopts a dependency-managed
  environment (e.g., alongside the training framework in ADR-001).

Consequences:

- Property-based and example-based tests coexist (PBT-10): see
  `tests/test_bpe_pbt.py` and `tests/test_bpe_examples.py`.
- The harness is intentionally minimal but sufficient for round-trip, invariant,
  idempotence, and oracle properties of the current dependency-free units.
