# Data Pipeline

fal'Cie's data pipeline turns raw documents into a clean, auditable training corpus.
It is dependency-free (Python standard library only) and composable: every stage
reads and writes the same JSONL record shape, so stages chain on the command line
and the whole flow runs from a clean checkout with `python3` alone. This is the
roadmap **M1** deliverable "a reproducible data pipeline exists".

## Record format

One JSON object per line (`scripts/data/records.py`):

```json
{"id": "<unique stable id>", "text": "<content>", "source": "<source name>", "meta": {}}
```

- **id** — unique within a file (and, for `aggregate`, across files). Derived by
  `make_id(source, index, text)`; ids must be unique, so re-sharding the same source
  uses `ingest --start-index` to keep shards disjoint.
- **text** — normalized content. `normalize_text` applies Unicode NFC, unifies
  newlines, strips trailing whitespace per line, and trims blank edges. It is
  idempotent, which is what makes the downstream properties hold.
- **meta** — optional provenance (e.g. contamination flags).

## Stages

| Stage | Script | What it does |
|---|---|---|
| Ingest (U-D1) | `scripts/data/ingest.py` | Read raw `.jsonl`/`.txt`, normalize, drop empties, assign ids. |
| Dedup (U-D2) | `scripts/data/dedup.py` | Remove exact (content-hash) and optional near-duplicate (n-gram Jaccard) documents. |
| Filter (U-D3) | `scripts/data/filter.py` | Drop low-quality docs by length / symbol / whitespace / repeat-line heuristics (config-driven). |
| Contamination (U-D4) | `scripts/data/contamination.py` | Flag or remove docs that overlap evaluation benchmarks (exact or near-duplicate). |
| Aggregate (U-D5) | `scripts/data/aggregate.py` | Total the corpus and break it down by source into a report. |

Each stage is deterministic and order-preserving; dedup/filter outputs are
subsequences of their inputs, and the repeatable stages are idempotent.

## Example run

```bash
python3 scripts/data/ingest.py raw.jsonl --source web --output norm.jsonl
python3 scripts/data/dedup.py norm.jsonl --near-dup-threshold 0.8 --output deduped.jsonl
python3 scripts/data/filter.py deduped.jsonl --config configs/data/filter.yaml --output filtered.jsonl
python3 scripts/data/contamination.py filtered.jsonl --remove --output clean.jsonl
python3 scripts/data/aggregate.py clean.jsonl --format md
```

`contamination` defaults its benchmarks to `evals/tokenizer/probes.jsonl`. Before a
training run, point `--benchmarks` at the **canonical eval-benchmark index** instead —
`evals/benchmark-index.jsonl`, built by `scripts/data/build_benchmark_index.py` from
every eval text that must stay out of training (probe texts + scored-suite prompts and
answers). The index is kept in sync with the suites by a gate check
(`build_benchmark_index.py --check`). Decontaminate with:

```bash
python3 scripts/data/build_benchmark_index.py            # refresh the index
python3 scripts/data/contamination.py clean.jsonl \
    --benchmarks evals/benchmark-index.jsonl --remove --output decontaminated.jsonl
```

## Verification

The pipeline is exercised by property-based and example tests under `tests/`
(`test_ingest.py`, `test_dedup.py`, `test_filter.py`, `test_contamination.py`,
`test_aggregate.py`) plus an end-to-end integration test (`test_data_pipeline.py`).
The properties (idempotence, subsequence, threshold monotonicity, contamination
score range, aggregation additivity) are mutation-tested: disabling a stage's core
branch makes the corresponding test fail. Run everything via the gate:

```bash
python3 scripts/run_checks.py
```

## Status & next steps

- Implemented dependency-free; covered by the verification gate.
- Filters and contamination thresholds ship permissive/default; tune them with a
  committed `configs/data/filter.yaml` and a real benchmark set per corpus.
- The minimal dataset loader (U-I3) and checkpoint metadata (U-I2) are the next
  infrastructure units that consume this pipeline's output.
