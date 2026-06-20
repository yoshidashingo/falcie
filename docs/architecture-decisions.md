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

Research evidence (L-002, 2026-06-20): reference recipes use custom PyTorch (Llama 3
— 4D parallelism TP+CP+PP+FSDP) or JAX/Pathways (Gemma). The most reproducible
*open* training stack is AI2's `OLMo-core` (PyTorch, Apache-2.0), which ships data,
code, logs, and intermediate checkpoints. This supports a PyTorch-first direction
with OLMo-core as the primary reference to study. See
`docs/research/open-weight-recipes.md` (Training recipe & stability). Recommendation:
keep Status Proposed; move to Testing once the M2 training framework is chosen.

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

Research evidence (L-002, 2026-06-20): the dense-first choice is well supported —
Meta chose dense for Llama 3 explicitly "to maximize training stability," and OLMo 2
and Gemma 2/3 are dense. MoE is the frontier-efficiency path: DeepSeek-V3 activates
37B of 671B params (MLA + DeepSeekMoE + auxiliary-loss-free balancing) and Qwen3-MoE
uses 128 experts / 8 active. JP caveat: Qwen3 dropped shared experts to push
specialization; a JP+EN model should keep >=1 shared expert if it adopts MoE. See
`docs/research/open-weight-recipes.md` (Model family). Recommendation: this evidence
justifies promoting the dense-first direction to Testing for M2 (owner handoff).

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

Research evidence (L-002, 2026-06-20): reference vocab sizes have converged upward —
Llama 3 and DeepSeek-V3 at 128k, Qwen3 ~151.7k, Gemma 2/3 at 256k/262k, OLMo 2 at
~100k. Byte-level BPE (Qwen3, Llama 3, DeepSeek) is the mainstream lossless base,
matching fal'Cie's existing choice. Critically, Gemma 3 grew its vocabulary
specifically to improve Japanese/CJK encoding "at the expense of a slight increase
of token counts for English and code." This makes vocab size the key open decision
for a JP-first model. See `docs/research/open-weight-recipes.md` (Tokenizer).
Recommendation: run a vocab-size bakeoff at 64k / 128k / 256k measuring Japanese
fertility vs embedding-parameter cost on a JP-heavy held-out corpus before fixing
the size.

Bakeoff evidence (L-003, 2026-06-20): the harness now exists
(`scripts/tokenizer/vocab_bakeoff.py`) and an in-phase small-scale bakeoff was run
on a held-out public-domain corpus (Aozora JP + Gutenberg EN + CPython code; raw
corpus not committed per `data-policy.md` — see
`configs/data/bakeoff-corpus.manifest.json`). Report:
`docs/tokenizers/vocab-bakeoff-report.md`. Japanese tokens/char measured on a
held-out, multi-work eval slice vs that slice's own byte baseline (3.0), all
non-collapsing:

| vocab | ja tokens/char | vs byte | embed @ d_model=2048 |
| ---: | ---: | ---: | ---: |
| 512 | 1.3611 | -54.6% | 1.05M |
| 1024 | 1.0598 | -64.7% | 2.10M |
| 2048 | 0.8653 | -71.2% | 4.19M |
| 4096 | 0.7165 | -76.1% | 8.39M |
| 8192 | 0.6152 | -79.5% | 16.78M |

Finding: even a tiny subword vocab crushes the byte baseline on Japanese (already
-55% at 512). The fertility gain shows **diminishing returns** (per-doubling
relative improvement 22% -> 18% -> 17% -> 14%) while embedding cost **doubles every
step**. Within this small range no cost knee is reached — each doubling still cut
Japanese tokens/char by >= 14%, so the best-fertility pick is simply the largest
tested vocab; the knee is *expected* at larger vocab, which is exactly why the
reference models settle at 128k-256k rather than scaling indefinitely, and why the
JP/CJK benefit (Gemma 3) justifies the larger end. Absolute sizes here are tiny
(pure-Python + a ~0.7 MB corpus); only the trend and methodology generalize. The
full 64k/128k/256k run — where the production size and its actual knee are fixed —
is deferred to M2 (real corpus + a faster, dependency-managed trainer).
Recommendation: this justifies promoting ADR-003 from Proposed to **Testing** (owner
handoff), carrying the byte-level BPE base and the fertility-vs-cost gate forward.

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

Research evidence (L-002, 2026-06-20): the consensus is "pretrain short, extend
late." All five reference models pretrain at 4k-8k, raise RoPE theta (5x10^5-1x10^6),
then extend to 32k->128k with YaRN and validate with needle-in-a-haystack (Llama 3
did this in 6 staged steps over ~800B tokens). Gemma 3's interleaved local/global
attention (5:1, 1024-token local window) is the cheap way to hold a 128k KV-cache.
See `docs/research/open-weight-recipes.md` (Context length). Recommendation:
pretrain at 4k with high RoPE theta; add staged YaRN extension with NIAH validation;
evaluate local/global attention before committing to long-context training cost.

## ADR-005: Checkpoint Format

Status: Proposed

Requirements:

- Safe tensor format where possible
- Hugging Face compatibility for distribution
- Checksums for all release artifacts
- Metadata linking checkpoint to data manifest and training config

Current direction:

Use safetensors-compatible release artifacts whenever possible.

Research evidence (L-002, 2026-06-20): safetensors + Hugging Face compatibility is
universal across all five reference models, confirming this direction. DeepSeek-V3
additionally ships native FP8 weights with an FP8<->BF16 conversion script. License
is a hard release gate for fal'Cie's Apache-2.0 goal: Qwen3 and OLMo 2 are Apache-2.0;
Llama 3 (Community License) and Gemma (Gemma Terms) are not, and both forbid using
their outputs to train a competing model. OLMo 2 also releases data, code, logs, and
thousands of intermediate checkpoints — the reproducibility bar fal'Cie's roadmap
principles target. See `docs/research/open-weight-recipes.md` (Checkpoint/release).
Recommendation: keep safetensors+HF+checksums; add provenance metadata; treat the
Apache-2.0 provenance rule as a data-policy constraint, not just a release step.

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
