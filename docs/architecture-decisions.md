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
