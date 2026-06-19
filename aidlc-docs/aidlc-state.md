# AI-DLC State Tracking

## Project Information
- **Project Name**: fal'Cie
- **Project Type**: Brownfield
- **Start Date**: 2026-06-16T06:24:39Z
- **Current Phase**: CONSTRUCTION
- **Current Stage**: Per-Unit Loop — all M1 + Stage 0–1 units (tokenizer, data, infra) implemented, independently reviewed, mutation-verified (8-check gate green, 206 tests)
- **Invocation Mode**: opt-in `/aidlc` (this task only; does not override normal requests)
- **Original Request**: "最強のLLMモデルをつくりたい" (build the strongest LLM model)

## Workspace State
- **Existing Code**: Yes
- **Programming Languages**: Python 3 (standard library only, no third-party deps yet)
- **Build System**: None yet (no package.json / pyproject.toml / requirements.txt). Scripts run directly with `python3`.
- **Project Structure**: Early-stage research repository (docs + configs + standalone scripts + eval fixtures). No model/training code yet.
- **Reverse Engineering Needed**: Yes (brownfield, no prior artifacts)
- **Workspace Root**: `.` (repository root; absolute paths intentionally omitted per repo Git rules)

## Code Location Rules
- **Application Code**: Workspace root (NEVER in aidlc-docs/)
- **Documentation**: aidlc-docs/ only
- **Structure patterns**: See construction/code-generation.md Critical Rules

## Project-Specific Constraints (override defaults)
- **opt-in scope**: AI-DLC applies only to this `/aidlc` task; it does not permanently override normal requests.
- **No absolute paths**: never write absolute filesystem paths into committed files. Use `.` / relative paths.
- **No commit/push** without explicit user instruction (per AGENTS.md Git rules). No secrets, no `.omc/` in committed files.
- **Clean-room**: do NOT copy/adapt/port any third-party model's code, weights, UI, copy, or trade dress. Original work only.
- **Measured claims**: every capability claim must map to a reproducible evaluation result (per roadmap principles).

## Extension Configuration
| Extension | Enabled | Decided At |
|---|---|---|
| Security Baseline | No | Requirements Analysis (2026-06-19) |
| Resiliency Baseline | No | Requirements Analysis (2026-06-19) |
| Property-Based Testing | Yes (full) | Requirements Analysis (2026-06-19) |

PBT-09 deviation (dependency-free): Hypothesis is disallowed by the stdlib-only
constraint; a stdlib PBT harness (`tests/pbt.py`) is the recorded substitute.
See `docs/architecture-decisions.md` ADR-006.

## Reverse Engineering Status
- [x] Reverse Engineering - Completed on 2026-06-16T06:24:39Z
- **Artifacts Location**: aidlc-docs/inception/reverse-engineering/

## Stage Progress

### INCEPTION
- [x] Workspace Detection — Brownfield, new AI-DLC project
- [x] Reverse Engineering — artifacts generated; GATE approved on resume (2026-06-19)
- [x] Requirements Analysis — `aidlc-docs/inception/requirements/requirements.md` (M1 + Stage 0–1 scope)
- [~] User Stories — SKIPPED (justified: internal developer/research tooling); see story-map
- [x] Workflow Planning — folded into the unit decomposition + priority order (momentum per user directive)
- [x] Application Design — `aidlc-docs/inception/application-design/` (modules + interfaces, lightweight)
- [x] Units Generation — `unit-of-work.md` + dependency matrix + capability map (M1 + Stage 0–1 units)

### CONSTRUCTION
- Per-Unit Loop (first wave — implemented + verified, all gates green):
  - [x] U-I5 stdlib PBT harness (`tests/pbt.py`)
  - [x] U-T1 byte-level BPE library (`scripts/tokenizer/bpe.py`) + tests
  - [x] U-T2 BPE training CLI (`scripts/tokenizer/train_bpe.py`)
  - [x] U-T3 tokenizer selection report (`scripts/tokenizer/select_tokenizer.py` → `docs/tokenizers/selection-report.md`) — selection pipeline complete; **M1 exit criterion reachable** via `--corpus` (held-out corpus pending; the default smoke run honestly recommends nothing)
  - [x] U-I6 verification gate runner (`scripts/run_checks.py`)
- Data wave (implemented + reviewed + mutation-verified, all gates green):
  - [x] shared `scripts/data/records.py` (Record schema, normalize, hashing, n-gram/Jaccard, JSONL IO)
  - [x] U-D1 ingest (`scripts/data/ingest.py`) + `--start-index` shard offsets
  - [x] U-D2 dedup (`scripts/data/dedup.py`) exact + near-duplicate
  - [x] U-D3 filter (`scripts/data/filter.py`) config-driven heuristics
  - [x] U-D4 contamination (`scripts/data/contamination.py`) flag/remove vs benchmarks
  - [x] U-D5 aggregate (`scripts/data/aggregate.py`) corpus report + cross-file id-uniqueness
  - [x] end-to-end integration test (`tests/test_data_pipeline.py`); see `docs/data-pipeline.md`
- Infra wave (implemented + reviewed [verdict: ship] + mutation-verified, all gates green):
  - [x] U-I1 config loader + content hashing (`scripts/common/config.py`)
  - [x] U-I2 checkpoint metadata + schema (`scripts/training/checkpoint_meta.py`, `configs/training/checkpoint.schema.yaml`) — strict (rejects unknown fields)
  - [x] U-I3 minimal resumable dataset loader (`scripts/data/loader.py`)
  - [x] U-I4 mock/tiny-model eval hook (`scripts/evals/run_mock_eval.py`)
  - [x] U-T4 special-token scheme (`scripts/tokenizer/special_tokens.py`)
- [x] Build and Test — single-command gate `scripts/run_checks.py` (8 checks: validate_manifest, smoke_eval,
  summarize_probes, score_tokenizer, select_tokenizer, special_tokens, mock_eval, unit_tests / 206 tests)

**M1 + Stage 0–1 construction complete.** All 16 planned units are implemented, independently reviewed, and
mutation-verified. Next candidate work (future iterations, not yet scoped): real held-out corpora for tokenizer
selection (M1 exit) and data, then M2 (sub-1B experimental models) which needs a training framework decision (ADR-001)
and is out of the current dependency-free scope.

### OPERATIONS
- [ ] Operations (placeholder)
