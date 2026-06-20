# M2 Implementation Plan — Small Experimental Models (proposal)

> Loop **L-006**. This is a **proposal for owner approval**, not a decision — it does
> not change any ADR, and M2 *execution* (training real neural models) remains an
> explicit go/no-go. Its job is to turn "should we start M2?" into "approve or adjust
> this concrete plan." It synthesizes the committed evidence:
> [recipe research](research/open-weight-recipes.md) (L-002),
> [tokenizer vocab bakeoff](tokenizers/vocab-bakeoff-report.md) (L-003),
> [base-LM BPB eval](evals/lm-baseline-report.md) (L-005), the
> [ADRs](architecture-decisions.md), and [`roadmap.md`](roadmap.md) M2 /
> [`training-plan.md`](training-plan.md) Stage 2.

## Goal & scope

Train **sub-1B and 1B-class dense models** to validate the pipeline end to end —
data quality, loss behavior, eval automation, training stability and scaling — *not*
to claim frontier capability. M2 is the first time fal'Cie leaves the dependency-free
phase: it needs a real training framework, third-party dependencies, and compute.

Roadmap M2 / training-plan Stage 2 **exit criteria** this plan must satisfy:

- Training **resumes from checkpoint** after interruption.
- **Evaluation runs automatically** at fixed token intervals.
- **Model-card draft** exists per experimental checkpoint.
- Loss curves are stable; the **data mix changes without code edits**.
- Checkpoint metadata carries the data-manifest + config hashes
  (schema already exists: `configs/training/checkpoint.schema.yaml`,
  `scripts/training/checkpoint_meta.py`).

## Recommended model family (dense, stability-first)

Dense decoder-only — the stability choice the evidence supports (Llama 3 chose dense
"to maximize training stability"; OLMo 2 and Gemma are dense; see
[research](research/open-weight-recipes.md) → Model family, and
[ADR-002](architecture-decisions.md)). MoE is deferred to a later milestone.

Adopt the **OLMo 2 stability stack** wholesale (it is language-agnostic and is the
clearest published anti-loss-spike recipe — [research](research/open-weight-recipes.md)
→ Training recipe & stability):

- **RMSNorm**, applied **after** the attention/FFN sublayers (reordered/post-norm), with **QK-Norm**
- **Z-loss** regularization; truncated-normal init (std 0.02); **no biases**
- **SwiGLU** FFN; **GQA**; **RoPE** with base θ = 5×10⁵ (set up for later context extension per [ADR-004](architecture-decisions.md))
- **Tied input/output embeddings** (halves the embedding-matrix cost — see the vocab note below)

We adopt the full stack even at 160M (where sub-1B models rarely spike) for
consistency across the ladder and forward-compatibility with the Stage-3 7B run,
where it earns its keep; the per-step cost at this scale is negligible.

Three experimental sizes (illustrative, Pythia/OLMo-shaped — exact dims are a tuning detail):

| Model | Layers | d_model | Heads (Q/KV) | FFN (SwiGLU) | Context | ~Params |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| falcie-160m | 12 | 768 | 12 / 4 | ~2048 | 2048 | ~160M |
| falcie-410m | 24 | 1024 | 16 / 4 | ~2730 | 2048 | ~410M |
| falcie-1b | 16 | 2048 | 16 / 8 | ~5461 | 4096 | ~0.9B |

Rationale for a ladder: it exercises scaling behavior (loss vs size/tokens) cheaply
before any 7B run (training-plan Stage 3), and each size is a real checkpoint the
eval harness can score.

## Tokenizer & vocabulary

Carry forward the byte-level BPE base ([ADR-003](architecture-decisions.md); lossless,
no UNK). The open decision is **vocab size**, and the
[bakeoff](tokenizers/vocab-bakeoff-report.md) (L-003) quantified the tradeoff:
larger vocab → better Japanese fertility (monotonic in the tested range) but the
embedding matrix cost grows **linearly** (vocab × d_model).

That cost bites hardest at small scale: a 64k vocab at d_model 768 is ~49M params —
~30% of falcie-160m. **Recommendation:** train **one shared byte-BPE vocabulary
(~48k–64k)** on the JP-heavy pretraining mix and use it across the series (tokenizer
consistency matters more than per-size optimization), with **tied embeddings** to
halve the cost. The full 64k/128k/256k decision (where reference models settle at
128k–256k) belongs to the Stage 3 / larger-model run, not these tiny models.

## Data & curriculum

Use the existing dependency-free pipeline ([data-pipeline.md](data-pipeline.md):
ingest → dedup → filter → contamination → aggregate) to build a frozen, manifested
corpus, and adopt the **two-stage curriculum** the evidence favors
([research](research/open-weight-recipes.md) → Pretraining data):

1. **Stage-1 (web-scale):** a Japanese-first mix (raise the JP share well above the
   ~8% multilingual slice typical of English-first models), plus English, code, and
   math. Run the full pipeline; run **contamination checks against the real eval set**
   (not just the probe fixture) before training.
2. **Stage-2 (high-quality mid-training / annealing):** a curated "Japanese Dolmino"
   equivalent (JP Wikipedia, filtered CC-JP/CulturaX-JP, STEM/math, synthetic
   reasoning with provenance), with accelerated LR decay — OLMo 2's reproducibility-
   winning move.

Token budgets (experimental, validate-then-scale; small models are over-trained well
past compute-optimal, as Gemma/Llama do):

| Model | Stage-1 tokens (approx) | Stage-2 tokens |
| --- | ---: | ---: |
| falcie-160m | ~10B | ~1B |
| falcie-410m | ~30B | ~3B |
| falcie-1b | ~100B | ~10B |

Data acquisition (a real multi-GB JP corpus, with licensing/provenance per
[`data-policy.md`](data-policy.md)) is itself an owner-gated step — the small
public-domain bakeoff corpus is for tokenizer/eval scaffolding, not pretraining.

## Training recipe

From the converged reference recipes ([research](research/open-weight-recipes.md) →
Training recipe & stability):

- **Optimizer:** AdamW, β=(0.9, 0.95), weight decay 0.1, gradient clip 1.0.
- **LR schedule:** linear warmup (~1–2% of steps) → cosine decay to ~10% of peak →
  short final anneal to ~0 on the Stage-2 high-quality mix. Peak LR ~3×10⁻⁴ for the
  small models (tune by size).
- **Batch:** ramp the global batch (start ~0.5–1M tokens) as in Llama 3.
- **Precision:** bf16 to start; FP8 (DeepSeek-V3-style, GEMMs only) is an opt-in
  efficiency lever once on H100-class hardware — out of scope for the first runs.
- **Context:** pretrain at 2k (1b at 4k); extend later via YaRN with needle-in-a-
  haystack validation ([ADR-004](architecture-decisions.md)) — not in M2's first pass.
- **Divergence recovery:** the stability stack reduces but does not eliminate loss
  spikes; if loss diverges anyway, rewind to the last good checkpoint and resume with
  a reduced LR and/or a reshuffled data shard — the resume path (T3) makes this cheap.

## Evaluation (already built)

- **Base-LM:** bits-per-byte / perplexity on a held-out slice at **fixed token
  intervals** (roadmap M2), via the L-005 harness
  ([`scripts/evals/lm_eval.py`](../scripts/evals/lm_eval.py),
  [report](evals/lm-baseline-report.md)). The n-gram baseline (~2.18 bits/byte) is the
  floor every M2 checkpoint must beat — this is the concrete first comparison point.
- **Scored tasks:** the L-004 harness ([`scripts/evals/run_eval.py`](../scripts/evals/run_eval.py))
  once instruction tuning begins (Stage 4). For base models, BPB + loss curves suffice.
- Track loss curves and per-language BPB; gate scaling on stable curves.

## Checkpoints

Safetensors, HF-compatible ([ADR-005](architecture-decisions.md)); metadata via the
existing `checkpoint_meta` (model name/size, arch config, tokenizer version, training
token count, **dataset-manifest hash**, **config hash**, commit SHA, license, status).
Resume-from-checkpoint is a hard M2 exit criterion, so build it into the loop from T1.

## Decisions required (owner)

M2 execution cannot start until these are made — they are deliberately left to the owner:

1. **Training framework ([ADR-001](architecture-decisions.md)).** Recommended: start
   with **Hugging Face Transformers + Accelerate** for the fastest experimental path,
   studying **OLMo-core** (PyTorch, Apache-2.0) as the reproducibility reference; or
   commit to OLMo-core directly. Either promotes ADR-001 Proposed → Accepted.
2. **Dependency adoption ([ADR-006](architecture-decisions.md)).** ADR-006 is already
   *Accepted (for the dependency-free phase)* and explicitly says to revisit "when the
   project adopts a dependency-managed environment" — so this is not a Proposed→Accepted
   promotion like the others, but the trigger of that built-in revisit clause: approve
   leaving the stdlib-only phase for the training environment (PyTorch, tokenizers, eval
   deps). The dependency-free data/tokenizer/eval scaffolding stays as the reproducible core.
3. **Compute & budget.** Rough estimate (6·N·D FLOPs; ~50% MFU on A100-class):
   falcie-160m ≈ tens of GPU-hours; falcie-1b at ~100B tokens ≈ ~1,000 GPU-hours
   (~5 days on 8×A100; the figure is for the ~0.9B config above — re-scale if dims
   change). The full 160m→410m→1b ladder is on the order of
   **~1,000–3,000 GPU-hours** — modest cloud budget. Owned vs cloud is an owner call.
4. **ADR promotions.** Promote ADR-002 (dense-first), ADR-003 (byte-BPE + the chosen
   vocab), ADR-004 (short→extend) Proposed → **Accepted** for M2, on the L-002/L-003 evidence.
5. **Real pretraining data.** Approve acquiring/curating the JP-heavy corpus (provenance
   per [`data-policy.md`](data-policy.md)) — distinct from the bakeoff fixture corpus.

## Staged task breakdown (maps to M2 exit criteria)

| Task | Output | Exit criterion served |
| --- | --- | --- |
| T1 | Training env + framework (ADR-001/006); model code (dense + stability stack); `configs/training/` model configs | foundation |
| T2 | Scale + freeze the pretraining corpus via the pipeline; manifest + contamination vs real eval set | data mix changeable without code edits |
| T3 | Training loop with **resume-from-checkpoint** + `checkpoint_meta` integration | training resumes after interruption |
| T4 | **Automatic eval hooks** — BPB at fixed token intervals (L-005 harness) | evaluation runs automatically |
| T5 | Train falcie-160m → 410m → 1b; loss curves + per-language BPB; scaling notes | stable loss curves; scaling behavior tracked |
| T6 | **Model-card draft** per checkpoint (template: `model-card-template.md`) | model-card draft per experimental checkpoint |

## Non-goals for M2

Instruction tuning (Stage 4), MoE, 7B+ scaling (Stage 3), long-context training,
FP8, and any release claim. M2 proves the pipeline; it does not ship a product.
