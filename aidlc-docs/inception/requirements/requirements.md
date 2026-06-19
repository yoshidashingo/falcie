# Requirements — fal'Cie M1 (Data + Tokenizer Prototype)

## Intent Analysis

- **User request**: "最強のLLMモデルをつくりたい" → on resume: "タスクに分解して、実装を進めて。"
- **Request type**: New Project capability build-out (continuation of an in-flight brownfield program).
- **Scope estimate**: Multiple Components (data, tokenizer, training-infra tooling) within one repository.
- **Complexity estimate**: Moderate. The *program* goal (frontier open-weight LLM) is long-horizon (M0–M5);
  this iteration scopes the **immediately implementable, dependency-free slice**: Milestone **M1 (Data and
  Tokenizer Prototype)** plus Training-Plan **Stage 0 (Infrastructure Smoke Tests)** and **Stage 1
  (Tokenizer Selection)**.

## Scope Decision (this iteration)

Confirmed with the user at Requirements Analysis (2026-06-19):

- **Target**: Decompose all of M1 + Stage 0–1 into units of work and implement in priority order.
- **Hard constraint (inherited)**: dependency-free — Python standard library only. No third-party deps
  (no PyTorch, no Hugging Face, no Hypothesis, no PyYAML). Configs remain JSON-compatible YAML.
- **Out of scope (this iteration)**: actual neural-network training (M2+), real large-corpus acquisition,
  cloud/infra, instruction tuning, release. Those depend on compute/data not yet secured.

## Functional Requirements

### Data pipeline (M1 exit: "reproducible data pipeline exists")
- FR-D1: Ingest raw text sources referenced by a manifest and normalize them deterministically
  (Unicode NFC, newline/whitespace normalization), emitting normalized records with provenance.
- FR-D2: Deduplicate normalized records (exact + near-duplicate) deterministically.
- FR-D3: Apply configurable heuristic quality filters (length, symbol/whitespace ratio, repetition,
  language heuristic).
- FR-D4: Run contamination checks of corpus records against benchmark/eval prompts and flag/remove hits.
- FR-D5: Aggregate per-source statistics into a reviewable dataset report consistent with the manifests.

### Tokenizer (M1 exit: "tokenizer candidate is selected with evidence")
- FR-T1: Provide a dependency-free byte-level BPE tokenizer: train, encode, decode, save, load.
- FR-T2: Provide a CLI to train a tokenizer from a corpus and persist the model.
- FR-T3: Produce a tokenizer **selection report** comparing candidates (reference baselines + BPE at
  several vocab sizes) on the stable probe fixture, with a recommended candidate and rationale.
- FR-T4: Define a special-token scheme (bos/eos/pad/roles/tool) integrated with the tokenizer.

### Training infrastructure (Stage 0 smoke)
- FR-I1: A reproducible config loader with stable content hashing for provenance.
- FR-I2: A checkpoint-metadata schema with build/validate/save/load (per training-plan fields).
- FR-I3: A minimal, resumable, seed-deterministic dataset loader over processed records.
- FR-I4: A mock/tiny-model evaluation hook that scores over probes/tasks without real inference.

## Non-Functional Requirements

- NFR-1 (Reproducibility): every transform is deterministic given inputs + seed; provenance (config hash,
  manifest hash, commit SHA) is recorded. (Roadmap principle: "reproducible training".)
- NFR-2 (Dependency-free): standard library only; runs from a clean checkout with `python3` alone.
- NFR-3 (Measured claims): tokenizer/data claims map to a reproducible report artifact (Roadmap principle).
- NFR-4 (Clean-room): no copying/porting of third-party model code, weights, vocab, or trade dress.
- NFR-5 (Testability / PBT): units with round-trip, invariant, idempotence, or oracle properties carry
  property-based tests (extension enabled — see below).
- NFR-6 (No absolute paths in committed files; no secrets; no commit/push without explicit instruction.)

## Extension Configuration (decided at Requirements Analysis, 2026-06-19)

| Extension | Enabled | Notes |
|---|---|---|
| Security Baseline | No | Dependency-free CLI tooling; no network/auth/secret handling. App-security rules largely N/A. Data license/PII/contamination handled by the domain (data-policy + contamination checks), not this extension. |
| Resiliency Baseline | No | No running services/infra (HA/DR/observability) yet. Checkpoint resumability handled as a domain requirement (FR-I2/FR-I3). |
| Property-Based Testing | Yes (full) | Tokenizer/dedup/serialization/filter are round-trip/invariant/idempotence-heavy — ideal for PBT. **PBT-09 deviation**: the dependency-free constraint forbids Hypothesis; a stdlib-only PBT harness (seedable generators + shrinking + reproducible seeds) is provided instead (`tests/pbt.py`). Recorded in `docs/architecture-decisions.md`. |

## Success Criteria

- Each unit completes behind the repo verification gate (existing checks stay green + new unit tests pass).
- The tokenizer selection pipeline is demonstrable and reproducible; the M1 exit criterion
  ("candidate selected with evidence") is reachable via `--corpus` once a held-out corpus exists
  (the default smoke run honestly recommends nothing and discloses the train==eval memorization).
- A single command runs all checks (`scripts/run_checks.py`), making the gate cheap to re-run.

## Traceability

Requirements derive from `docs/roadmap.md` (M1), `docs/training-plan.md` (Stage 0–1, checkpoint metadata),
`docs/evaluation-plan.md` (probes, contamination), and the reverse-engineering artifacts under
`aidlc-docs/inception/reverse-engineering/`. Unit mapping: see
`aidlc-docs/inception/application-design/unit-of-work-story-map.md`.
