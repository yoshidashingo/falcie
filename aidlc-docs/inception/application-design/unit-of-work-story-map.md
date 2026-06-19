# Capability → Unit Map — fal'Cie M1 + Stage 0

User Stories stage was **skipped** (justification below). This map traces program capabilities /
roadmap exit criteria to units instead of to formal user stories.

## Justification for skipping User Stories

Per `core-workflow.md` User Stories assessment, this iteration is internal **developer/research tooling**
with no end-user-facing UI or workflow change: the "users" are project maintainers and researchers running
CLIs. It falls under "SKIP ONLY IF … developer tooling or build-process improvements". Capabilities are
already captured as measurable roadmap/training-plan exit criteria, so a capability→unit map is the
higher-value artifact.

## Map

| Capability / Exit criterion (source) | Unit(s) |
|---|---|
| Reproducible data pipeline exists (roadmap M1) | U-D1, U-D2, U-D3, U-D4, U-D5 |
| Dataset licenses & exclusions documented (roadmap M1) | U-D5 + existing `validate_manifest` / data-policy |
| Tokenizer candidate selected with evidence (roadmap M1) | U-T1, U-T2, U-T3 |
| Tokenizer artifacts versioned; selection explained (training-plan Stage 1) | U-T2, U-T3 |
| Special tokens for chat/tools/system (training-plan Stage 1) | U-T4 |
| Reproducible config format (training-plan Stage 0) | U-I1 |
| Checkpoint save/load test; checkpoint metadata (training-plan Stage 0/§Checkpoint Metadata) | U-I2 |
| Minimal dataset loader (training-plan Stage 0) | U-I3 |
| Tiny/external small-model evaluation harness (training-plan Stage 0) | U-I4 + existing `run_smoke_eval` |
| Evaluation runs automatically; gate from clean checkout (eval-plan release gates) | U-I6 |
| Capability claims map to reproducible results (roadmap principle) | U-T3, U-D5, U-I6 |

## First-wave coverage (this iteration)

Implements the **selection pipeline** for the "tokenizer candidate selected with evidence" M1
exit criterion (U-T1 + U-T2 + U-T3), on top of the testing + gate foundation (U-I5 + U-I6). The
criterion is *reached* once a held-out training corpus is supplied via `--corpus`; the default
smoke run recommends nothing and discloses the train==eval memorization.
