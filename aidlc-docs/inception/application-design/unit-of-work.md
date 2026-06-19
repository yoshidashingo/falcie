# Units of Work — fal'Cie M1 (Data + Tokenizer) + Stage 0 Infra

A "unit of work" here is a coherent, independently verifiable module. fal'Cie is a single repository
(monolithic tooling), so units are logical modules, not deployable services. Each unit completes fully
(code + tests + docs) behind the verification gate before the next is claimed done.

## Code Organization (greenfield modules within the brownfield repo)

- `scripts/data/` — data pipeline CLIs (ingest, dedup, filter, contamination, aggregate, loader).
- `scripts/tokenizer/` — tokenizer library + CLIs (bpe, train_bpe, select_tokenizer).
- `scripts/training/` — checkpoint metadata tooling (new).
- `scripts/common/` — shared config/hashing utilities (new).
- `scripts/run_checks.py` — single-command verification gate aggregator (new).
- `tests/` — stdlib PBT harness + property/example tests (new).
- `configs/training/` — checkpoint metadata schema (new).
- `docs/tokenizers/` — generated tokenizer selection reports.

All modules: Python standard library only; `from __future__ import annotations`; `ROOT = parents[N]`;
JSON-compatible YAML; no absolute paths in committed files.

## Unit Catalog

### Tokenizer workstream (M1 exit: "tokenizer selected with evidence")
- **U-T1 — Byte-level BPE library** (`scripts/tokenizer/bpe.py`)
  Train/encode/decode/save/load. Byte-level base alphabet (256) guarantees lossless round-trip and no
  unknown tokens. Deterministic training (frequency + lexicographic tie-break).
  Testable properties: round-trip (decode∘encode = id), determinism (oracle: train twice = equal),
  invariants (ids in range; byte-level never expands token count beyond byte length), save/load round-trip.
- **U-T2 — BPE training CLI** (`scripts/tokenizer/train_bpe.py`)
  Train from a corpus file (or the probe fixture), persist model JSON, print summary.
- **U-T3 — Tokenizer selection report** (`scripts/tokenizer/select_tokenizer.py`)
  Score reference baselines + BPE candidates (several vocab sizes) on the probe fixture; emit a
  machine-readable + markdown selection report with a recommended candidate and rationale into
  `docs/tokenizers/`. Reuses `score_tokenizer.score`.
- **U-T4 — Special-token scheme** (extends `bpe.py` + a config)
  bos/eos/pad/system/user/assistant/tool_call/tool_result reserved tokens (per
  `configs/tokenizer/evaluation.yaml`), never emitted by ordinary `encode`.

### Data workstream (M1 exit: "reproducible data pipeline exists")
- **U-D1 — Ingestion & normalization** (`scripts/data/ingest.py`) — NFC + whitespace/newline
  normalization; emit normalized JSONL with provenance. Properties: idempotent normalize; record count
  preserved minus empties.
- **U-D2 — Deduplication** (`scripts/data/dedup.py`) — exact (hash) + near-dup (n-gram Jaccard / SimHash,
  stdlib). Properties: idempotence `dedup(dedup(x))=dedup(x)`; output ⊆ input; size non-increasing.
- **U-D3 — Quality filtering** (`scripts/data/filter.py`) — configurable length/symbol-ratio/repetition/
  language-heuristic filters. Properties: output ⊆ input; per-filter invariants; idempotence.
- **U-D4 — Contamination check** (`scripts/data/contamination.py`) — near-dup search vs benchmark/eval
  prompts; flag/remove. Properties: oracle (brute-force vs indexed); stable flagged set.
- **U-D5 — Dataset aggregation/report** (`scripts/data/aggregate.py`) — per-source stats + dataset report,
  consistent with manifests; extends `validate_manifest`.

### Training infrastructure (Stage 0 smoke)
- **U-I1 — Config loader + hashing** (`scripts/common/config.py`) — load JSON-compatible YAML; stable
  content hash for provenance. Property: hash invariance under key reordering / round-trip.
- **U-I2 — Checkpoint metadata** (`configs/training/checkpoint.schema.yaml` + `scripts/training/checkpoint_meta.py`)
  — build/validate/save/load metadata (model name/size, tokenizer version, token count, manifest hash,
  config hash, commit SHA, license, status). Property: save/load round-trip; schema validation.
- **U-I3 — Minimal dataset loader** (`scripts/data/loader.py`) — streaming, resumable, seed-deterministic
  shuffle-buffer iteration over processed JSONL. Property: determinism under seed; full coverage.
- **U-I4 — Mock/tiny-model eval hook** (extends `scripts/evals/run_smoke_eval.py`) — score a mock model
  over probes/tasks without real inference.
- **U-I5 — stdlib PBT harness** (`tests/pbt.py`) — seedable generators + shrinking + reproducible seeds
  (the dependency-free substitute mandated by the PBT-09 deviation). Cross-cutting; required by all
  property-bearing units.
- **U-I6 — Verification gate runner** (`scripts/run_checks.py`) — one command runs validate_manifest +
  smoke eval + tokenizer summarize/score + `unittest discover`. Loop-Engineering automation of the gate.

## Priority Order (this iteration implements the first wave)

1. **U-I5** stdlib PBT harness — foundation for testing every property-bearing unit.
2. **U-T1** byte-level BPE library — core tokenizer engine; highest-value foundation.
3. **U-T2** BPE training CLI.
4. **U-T3** tokenizer selection report — builds the **M1 exit-criterion** pipeline (selection with
   evidence) fastest, reusing existing probe/scorer scaffolding.
5. **U-I6** verification gate runner — makes the gate a single command.

Subsequent waves: data workstream (U-D1→U-D5), then infra (U-I1, U-I2, U-I3, U-I4), then U-T4.
Rationale: deliver one complete, verifiable vertical slice (the tokenizer selection pipeline) that
builds toward an M1 exit criterion, while standing up the test + gate foundation the remaining units
reuse. The criterion itself is met once a held-out training corpus is supplied via `--corpus`.
