# Open-Weight Recipe Research Log

> Loop **L-002** (opened 2026-06-20). See `docs/loop/loop-ledger.md`.
> Premise: fal'Cie does not train from scratch on guesswork — it studies how
> recent strong open-weight models are actually built and adapts a proven recipe
> for a **Japanese-first, Apache-2.0, reproducible** model series.

This is a cited comparison of five reference families chosen for coverage of the
design space: **Qwen3** (multilingual + dense/MoE), **Llama 3.1** (canonical dense
recipe), **DeepSeek-V3** (frontier-efficiency MoE), **Gemma 2/3** (distillation +
cheap long context), and **OLMo 2** (fully-open reproducibility benchmark).

Every quantitative claim carries a primary-source URL. Items we could not verify
from a primary source are marked `[unverified]`. Confidence and limitations are in
the last section. This log feeds the "Research evidence (L-002)" annotations in
`docs/architecture-decisions.md`; it does **not** by itself accept any ADR — final
Accept/Reject is an owner decision (handoff).

## TL;DR — what fal'Cie should adopt

1. **Start dense, keep MoE for later (ADR-002).** Meta chose dense for Llama 3
   explicitly "to maximize training stability"; OLMo 2 and Gemma are dense too.
   MoE (DeepSeek-V3, Qwen3-MoE) is a frontier-scale efficiency play. Begin with
   dense experimental models; revisit MoE at M5 scale.
2. **Adopt the OLMo 2 / Qwen3 stability stack now.** RMSNorm + **QK-Norm** +
   Z-loss + reordered (post-) norm + high RoPE θ is the clearest published
   anti-loss-spike recipe, and is independent of language. Bake it in from M2.
3. **Large vocabulary, byte-level BPE, Japanese-weighted (ADR-003).** Vocab sizes
   have converged up: Llama 3 128k, DeepSeek 128k, Qwen3 ~151k, Gemma 256k–262k.
   Gemma 3 explicitly grew its vocab to improve **Japanese/CJK** compression.
   fal'Cie's existing byte-level BPE is the right base; the open decision is
   vocab size — run a JP-fertility bakeoff at 64k / 128k / 256k.
4. **Pretrain short, extend context in stages (ADR-004).** Everyone pretrains at
   4k–8k, raises RoPE θ (to 5×10⁵–1×10⁶), then extends to 32k→128k with YaRN and
   validates with needle-in-a-haystack. Gemma's interleaved local/global
   attention is the cheap way to hold 128k KV-cache.
5. **Two-stage data curriculum.** Web-scale Stage 1 (~90% of FLOPs) then a small
   curated high-quality "mid-training/annealing" Stage 2 (OLMo's Dolmino, Llama's
   annealing, Qwen3's stage-2). fal'Cie needs a **Japanese Dolmino** equivalent.
6. **Distill large→small.** Gemma 2's 2B/9B and Qwen3's small models are distilled
   from a large teacher — the key small-budget quality lever.
7. **Apache-2.0 provenance discipline (ADR-005 + data-policy).** Study **Qwen3**
   and **OLMo 2** (both Apache-2.0). Do **not** train on Llama or Gemma *outputs* —
   their licenses forbid using outputs to improve a competing model. Release
   safetensors + HF-compatible configs + checksums; consider OLMo-style
   intermediate-checkpoint releases for reproducibility.

## Cross-model comparison

| Dimension | Qwen3 | Llama 3.1 | DeepSeek-V3 | Gemma 2 / 3 | OLMo 2 |
| --- | --- | --- | --- | --- | --- |
| Family | Dense 0.6–32B + MoE (30B-A3B, 235B-A22B) | Dense 8/70/405B | MoE 671B/**37B active** | Dense 2/9/27B; 1/4/12/27B | Dense 7/13/32B |
| Attention | GQA, **QK-Norm**, no QKV bias | GQA (8 KV heads) | **MLA** (KV-cache compression) | Interleaved local/global; GQA; G2 soft-cap, G3 QK-Norm | MHA (7/13B), GQA (32B), **QK-Norm** |
| Tokenizer | Byte-level BPE | tiktoken BPE | Byte-level BPE | SentencePiece | BPE (cl100k base, `dolma2`) |
| Vocab | 151,669 | 128,256 | 128,000 | 256k (G2) / 262k (G3) | 100,278 |
| Pretrain tokens | ~36T | ~15.6T | 14.8T | 2–14T by size | 4.05–6T |
| Pretrain seq len | 4k → 32k | 8k → 128k | 4k → 32k → 128k | 8k (G2) / 32k–128k (G3) | 4k |
| Long-ctx method | ABF θ=1M + YaRN + DCA | staged 8k→128k (6 stages) | YaRN (2 stages) | local/global + θ=1M global | RoPE θ=5×10⁵ (base for future ext.) |
| Precision | BF16 (FP8 `[unverified]`) | BF16 train, FP8 infer | **FP8 train** (E4M3) | bfloat16 | bfloat16 `[unverified exact]` |
| Distillation | strong→weak for small models | — | — | **yes** (small from 27B / Gemini teacher) | — |
| Format | safetensors | safetensors | safetensors (FP8) | safetensors | safetensors |
| License | **Apache-2.0** | Llama Community (restrictive) | MIT code / DeepSeek model license | Gemma Terms (not OSI) | **Apache-2.0** |
| Openness | weights + report | weights + report | weights + report | weights + report | **data+code+logs+ckpts** |

Sources for the table are the per-model profiles below.

## Per-dimension synthesis (mapped to ADRs)

### Model family — ADR-002

- **Dense is the stability choice.** Llama 3: dense "to maximize training
  stability" ([Llama 3 paper](https://ar5iv.labs.arxiv.org/html/2407.21783)).
  OLMo 2 and Gemma 2/3 are dense. This validates fal'Cie's existing ADR-002
  direction (dense experimental models first).
- **MoE is the efficiency frontier.** DeepSeek-V3 activates only 37B of 671B
  params via fine-grained DeepSeekMoE (1 shared + 256 routed, top-8) with
  **auxiliary-loss-free** bias-update balancing
  ([DeepSeek-V3](https://arxiv.org/html/2412.19437v1)). Qwen3-MoE uses 128
  experts, 8 active, and **dropped shared experts** vs Qwen2.5
  ([Qwen3](https://arxiv.org/html/2505.09388v1)).
- **JP caveat for MoE:** Qwen3 removed shared experts to push specialization; for
  a model that must be strong in *both* Japanese and English, a shared expert
  helps maintain cross-lingual common representations. If/when fal'Cie does MoE,
  keep 1+ shared expert and prefer aux-loss-free balancing.

### Tokenizer — ADR-003

- **Vocab has converged upward.** 128k (Llama 3, DeepSeek) → 151,669 (Qwen3) → 256k+
  (Gemma). Llama 3's jump from 32k→128k (≈100k base + ≈28k language-specific tokens)
  improved tokenization efficiency
  ([Arize](https://arize.com/blog/breaking-down-meta-llama-3/)).
- **Bigger vocab helps Japanese.** Gemma 3's 262k tokenizer "significantly improves
  the encoding of _Chinese_, _Japanese_ and _Korean_ text, at the expense of a slight
  increase of the token counts for English and Code"
  ([HF Gemma 3 blog](https://huggingface.co/blog/gemma3), accessed 2026-06).
- **Byte-level BPE is the mainstream lossless base** (Qwen3, Llama 3, DeepSeek);
  Gemma uses SentencePiece with byte fallback. fal'Cie already chose byte-level
  BPE (256 byte base alphabet, lossless round-trip — see ADR-003 progress note).
- **Open decision:** vocab size. Recommend a bakeoff at **64k / 128k / 256k**
  measuring Japanese fertility (chars/token) and embedding-parameter cost
  (~`d_model × vocab` per the embed+unembed matrices) on a JP-heavy held-out
  corpus, per `docs/tokenizer-evaluation.md`.

### Pretraining data — informs `data-policy.md` / `training-plan.md`

- **Token budgets** scale with model size; 14.8–36T at the frontier, but Gemma 2B
  used 2T and OLMo 7B used ~4T — adequate for fal'Cie's experimental scales.
- **Disclosed mixes are English/code/math-first.** Llama 3.1: ~50% general / 25%
  math+reasoning / 17% code / 8% multilingual
  ([Oxen.ai](https://www.oxen.ai/blog/llama-3-1-herd-of-models),
  [Meta](https://ai.meta.com/blog/meta-llama-3/)). A JP-first model must raise the
  Japanese share substantially and accept English benchmarks as secondary.
- **Quality pipeline is classifier-driven.** Llama 3 used fastText + RoBERTa
  quality classifiers, bootstrapped from the previous model's judgments
  ([Meta](https://ai.meta.com/blog/meta-llama-3/)); MinHash near-dedup + line-level
  dedup ([Llama 3 paper](https://ar5iv.labs.arxiv.org/html/2407.21783)). fal'Cie's
  data pipeline (dedup/filter/contamination) already mirrors this shape.
- **Two-stage curriculum is the consensus.** OLMo 2 released **Dolmino-Mix-1124**,
  the first systematic mid-training dataset, run as a high-quality annealing Stage 2
  after web-scale Stage 1 ([Dolmino](https://huggingface.co/datasets/allenai/dolmino-mix-1124),
  [OLMo 2](https://allenai.org/blog/olmo2)). Llama anneals on highest-quality data
  in the final tokens; Qwen3 runs a high-quality STEM/code Stage 2 with accelerated
  LR decay. **Action:** build a "Japanese Dolmino" curated annealing mix.

### Training recipe & stability — ADR-001 (framework) + recipe

- **Stability stack (strong consensus):** RMSNorm; **QK-Norm** (Qwen3, OLMo 2,
  Gemma 3); Z-loss + reordered post-norm (OLMo 2); high RoPE θ. OLMo 2 frames all
  of these as stability fixes that eliminated loss spikes
  ([OLMo 2](https://arxiv.org/abs/2501.00656)). Adopt as baseline.
- **Optimizer:** AdamW, β≈(0.9, 0.95), wd≈0.1, cosine decay with warmup — common
  across Llama 3, DeepSeek-V3, OLMo 2 (exact tables vary; some values `[unverified]`).
- **Precision/efficiency (frontier):** DeepSeek-V3 trains in **FP8 (E4M3)** for all
  GEMMs while keeping embeddings/norms/gating/attention in higher precision, with
  fine-grained per-tile/-block quantization, for ~2.788M H800-hours total and no
  irrecoverable loss spikes ([DeepSeek-V3](https://arxiv.org/html/2412.19437v1)).
  FP8 is an opt-in efficiency lever once fal'Cie trains on H100-class hardware.
- **Framework (ADR-001):** Llama 3 used custom PyTorch 4D parallelism (TP+CP+PP+FSDP)
  ([Llama 3 paper](https://ar5iv.labs.arxiv.org/html/2407.21783)); Gemma used
  JAX/Pathways; **OLMo 2's training stack (`OLMo-core`, PyTorch, Apache-2.0) is the
  most reproducible open reference** ([OLMo GitHub](https://github.com/allenai/OLMo)).
  This supports an ADR-001 direction of PyTorch-first, studying OLMo-core.

### Context length — ADR-004

- **Pretrain short, extend late.** All five pretrain at 4k–8k, then extend. Llama 3
  extended 8k→128k in **six stages** over ~800B tokens, validating short-context
  recovery + perfect needle-in-a-haystack at each step
  ([Llama 3 paper](https://arxiv.org/abs/2407.21783)). DeepSeek-V3 uses two YaRN
  stages (→32k→128k). Qwen3 stacks ABF (θ=1M) + YaRN + Dual Chunk Attention.
- **Cheap long context:** Gemma 3's 5:1 local/global attention (1024-token local
  window) keeps 5 of every 6 layers' KV-cache tiny while one global layer (RoPE
  θ=1M) carries long range ([HF Gemma 3](https://huggingface.co/blog/gemma3)).
- **Recommendation:** pretrain at 4k with high RoPE θ; add staged YaRN extension to
  32k then 128k with NIAH validation; evaluate local/global attention before
  committing to long-context training cost.

### Checkpoint / release & license — ADR-005 + `data-policy.md`

- **safetensors + HF compatibility is universal.** DeepSeek additionally ships
  native FP8 weights with an FP8↔BF16 conversion script.
- **License is a hard gate for fal'Cie's Apache-2.0 goal** (licenses accessed
  2026-06; licenses change, so re-check before relying on any one). Apache-2.0:
  **Qwen3**, **OLMo 2**. Restrictive: **Llama 3 Community License** (>700M-MAU clause, and an
  explicit ban on using Llama outputs to train competing models —
  [WCR.Legal](https://wcr.legal/llama-3-license-700m-mau-limit/)); **Gemma Terms of
  Use** (not OSI-approved, propagating restrictions —
  [Gemma terms](https://ai.google.dev/gemma/terms); a switch to Apache-2.0 for a
  later Gemma generation is reported but `[unverified]` here). DeepSeek: MIT code +
  DeepSeek model license.
- **Reproducibility bar:** OLMo 2 releases data + code + training logs + thousands
  of intermediate checkpoints ([OLMo 2](https://arxiv.org/abs/2501.00656)) — the
  standard fal'Cie's roadmap principles ("reproducible training") should match.

## Reference profiles (condensed, with sources)

### Qwen3 (Alibaba, 2025) — multilingual dense + MoE, Apache-2.0
Dense 0.6–32B + MoE 30B-A3B / 235B-A22B; GQA + QK-Norm, no QKV bias; SwiGLU;
RMSNorm; RoPE θ 10k→1M (ABF). MoE: 128 experts, 8 active, no shared experts.
Byte-level BPE, 151,669 vocab, 119 languages (incl. Japanese). ~36T pretrain
tokens; 3-stage pretraining (general 4k → STEM/reasoning 4k → long-context 32k).
Context to 128k via ABF+YaRN+Dual Chunk Attention. Strong→weak distillation for
small models at ~1/10 GPU-hours. Apache-2.0, safetensors.
Sources: [tech report](https://arxiv.org/html/2505.09388v1) ·
[blog](https://qwenlm.github.io/blog/qwen3/) ·
[Qwen3-8B card](https://huggingface.co/Qwen/Qwen3-8B).

### Llama 3.1 (Meta, 2024) — canonical dense recipe, restrictive license
Dense 8/70/405B; GQA (8 KV heads), SwiGLU, RMSNorm, RoPE θ=500k; chose dense for
stability. tiktoken BPE, 128,256 vocab (~100k base + ~28k language tokens);
**Japanese not among the 8 officially supported languages**. ~15.6T tokens
(~50% general / 25% math / 17% code / 8% multilingual); MinHash + line dedup;
fastText/RoBERTa quality classifiers; final-token annealing. Staged 8k→128k
(6 stages, ~800B tokens, NIAH-validated). BF16 train / FP8 infer; 16k H100s, 4D
parallelism. **Llama 3 Community License** (not Apache; outputs cannot train a
competing model). safetensors.
Sources: [Llama 3 paper](https://arxiv.org/abs/2407.21783) ·
[ar5iv HTML](https://ar5iv.labs.arxiv.org/html/2407.21783) ·
[Meta blog](https://ai.meta.com/blog/meta-llama-3/) ·
[license analysis](https://wcr.legal/llama-3-license-700m-mau-limit/).

### DeepSeek-V3 (DeepSeek-AI, 2024) — frontier-efficiency MoE
MoE 671B / 37B active; 61 layers; **MLA** KV-cache compression; DeepSeekMoE
(1 shared + 256 routed, top-8); **auxiliary-loss-free** bias-update balancing;
**Multi-Token Prediction**. Byte-level BPE, 128k vocab, multilingual beyond
EN/ZH (Japanese `[unverified]`). 14.8T tokens. **FP8 (E4M3) training** with
fine-grained quantization; DualPipe overlap; 2.788M H800-hours; no loss spikes.
4k→32k→128k via YaRN. safetensors (FP8); MIT code + DeepSeek model license.
Sources: [tech report](https://arxiv.org/html/2412.19437v1) ·
[abstract](https://arxiv.org/abs/2412.19437) ·
[HF card](https://huggingface.co/deepseek-ai/DeepSeek-V3).

### Gemma 2 / 3 (Google DeepMind, 2024/2025) — distillation + cheap long context
Dense; G2 2/9/27B (8k ctx, 1:1 local/global, soft-capping), G3 1/4/12/27B
(32k–128k, 5:1 local/global window=1024, QK-Norm, SigLIP vision on 4B+).
SentencePiece, 256k (G2) / 262k (G3) vocab; G3 vocab explicitly improves
**Japanese/CJK**; 140+ languages. 2–14T tokens by size. **Knowledge distillation**:
small models trained from the 27B / a Gemini teacher (256 logits/token). bfloat16,
TPU/Pathways. **Gemma Terms of Use** (not OSI-approved). safetensors.
Sources: [Gemma 2 report](https://arxiv.org/html/2408.00118v1) ·
[Gemma 3 report](https://arxiv.org/html/2503.19786v1) ·
[HF Gemma 3 blog](https://huggingface.co/blog/gemma3) ·
[what's new in Gemma 3](https://developers.googleblog.com/en/gemma-explained-whats-new-in-gemma-3/).

### OLMo 2 (AI2, 2024/2025) — fully-open reproducibility benchmark, Apache-2.0
Dense 7/13/32B; stability stack: RMSNorm + **post-norm placement** + **QK-Norm** +
**Z-loss** + RoPE θ=500k; SwiGLU; no biases; MHA (7/13B), GQA (32B). BPE
(`dolma2`, cl100k base), 100,278 vocab; **English-only** — the key gap for fal'Cie.
Two-stage curriculum: Stage 1 **OLMo-Mix-1124** (~3.9T, >90% FLOPs: DCLM + Dolma +
StarCoder + Proof Pile II) → Stage 2 **Dolmino-Mix-1124** (843B, ~50% DCLM + curated
STEM/math/instruction) annealing. 4k context (θ set up for future extension).
**Apache-2.0** weights+code; releases data, `OLMo-core` code, training logs, and
thousands of intermediate checkpoints.
Sources: [OLMo 2 report](https://arxiv.org/abs/2501.00656) ·
[AI2 blog](https://allenai.org/blog/olmo2) ·
[Dolmino dataset](https://huggingface.co/datasets/allenai/dolmino-mix-1124) ·
[OLMo-7B card](https://huggingface.co/allenai/OLMo-2-1124-7B).

## Confidence & limitations

- **High confidence** (primary-source, cross-checked): model family, vocab sizes,
  token budgets, license type, context-extension method, the stability-stack and
  two-stage-curriculum consensus.
- **Medium / `[unverified]`**: exact optimizer hyperparameter tables (several
  reports omit them); Qwen3 training precision; per-language data percentages
  (rarely disclosed); Japanese-specific fertility for each tokenizer; the reported
  later-Gemma Apache-2.0 switch.
- **Scope:** this is a recipe survey to back-fill ADRs, not an endorsement of any
  single model. fal'Cie's differentiator — Japanese-first data + tokenizer at
  Apache-2.0 with OLMo-level reproducibility — is not directly copyable from any
  one reference and is the project's own design work.
- **Provenance rule:** architecture and published recipes are fine to study and
  reimplement; **weights and generated outputs of Llama and Gemma are not usable**
  for training fal'Cie under their licenses. Prefer Qwen3 / OLMo 2 (Apache-2.0)
  when a concrete artifact is needed.

## Next loops this unblocks

- Move ADR-002/003/004/005 from "Proposed" toward "Testing/Accepted" (owner handoff).
- Tokenizer vocab-size bakeoff (64k/128k/256k) on a JP-heavy corpus (ADR-003).
- Draft a "Japanese Dolmino" curated mid-training mix spec (`data-policy.md`).
- Prototype the stability stack (RMSNorm+QK-Norm+Z-loss) in the M2 model code.
