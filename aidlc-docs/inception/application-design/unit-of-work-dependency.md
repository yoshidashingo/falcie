# Unit-of-Work Dependency Matrix — fal'Cie M1 + Stage 0

"Depends on" = needs the other unit's interface/output to be implemented first.

| Unit | Depends on | Provides to |
|---|---|---|
| U-I5 stdlib PBT harness | (none) | all property-bearing units (U-T1, U-D1–U-D4, U-I1–U-I3) |
| U-T1 BPE library | U-I5 (for its tests) | U-T2, U-T3, U-T4 |
| U-T2 BPE training CLI | U-T1 | U-T3 (optional: persisted models) |
| U-T3 selection report | U-T1, existing `score_tokenizer` | M1 tokenizer exit evidence |
| U-T4 special tokens | U-T1 | future chat/tool formatting |
| U-I6 gate runner | existing scripts; discovers `tests/` | CI / Loop-Engineering gate |
| U-I1 config loader+hash | U-I5 (tests) | U-I2 (config hash), U-D* (config-driven) |
| U-D1 ingestion/normalize | U-I5 | U-D2, U-D3, U-D4, U-D5, U-I3 |
| U-D2 dedup | U-I5, U-D1 | U-D5 |
| U-D3 filtering | U-I5, U-D1 | U-D5 |
| U-D4 contamination | U-I5, U-D1, evals/probes | U-D5 |
| U-D5 aggregation/report | U-D1–U-D4, existing `validate_manifest` | dataset report |
| U-I2 checkpoint metadata | U-I1, U-I5 | training runs (M2+) |
| U-I3 dataset loader | U-D1 (records), U-I1 | training runs (M2+) |
| U-I4 mock eval hook | existing `run_smoke_eval` | evaluation automation |

## Critical Path (first wave)

`U-I5 → U-T1 → U-T2 → U-T3`, with `U-I6` wrapping the gate.

No two first-wave units write the same source file, so they integrate without conflict:
- U-I5 → `tests/pbt.py`
- U-T1 → `scripts/tokenizer/bpe.py`
- U-T2 → `scripts/tokenizer/train_bpe.py`
- U-T3 → `scripts/tokenizer/select_tokenizer.py` (+ generated report under `docs/tokenizers/`)
- U-I6 → `scripts/run_checks.py`
- tests → `tests/test_*.py`
