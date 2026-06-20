# Data Policy

fal'Cie must be trained on data that can support an open-weight release. This policy defines the baseline requirements for data collection, filtering, documentation, and exclusion.

## Policy Goals

- Preserve the ability to release weights under Apache 2.0.
- Avoid undocumented or legally ambiguous data sources.
- Make data decisions auditable.
- Improve quality through filtering, deduplication, and contamination checks.
- Support strong Japanese, English, code, and reasoning capability.

## Data Source Requirements

Every dataset must have a manifest entry with:

- Dataset name
- Source URL or retrieval method
- Version or snapshot date
- License or terms summary
- Intended use: pretraining, supervised fine-tuning, preference training, or evaluation
- Language/domain tags
- Estimated token count
- Filtering rules applied
- Exclusion rationale, if rejected

Raw datasets should not be committed to this repository. Store retrieval scripts, manifests, hashes, and processing rules instead.

## Allowed Data Categories

Potentially acceptable categories include:

- Public-domain text
- Permissively licensed text
- Open government and institutional data with compatible terms
- User-contributed data with explicit permission
- Synthetic data generated under controlled, documented conditions
- Open-source code where license compatibility is tracked
- Internal evaluation data that is not used for training

## Restricted or Rejected Data

Reject or quarantine data when:

- License terms are unknown or incompatible with open-weight release.
- The source prohibits model training or redistribution of derived artifacts.
- The data contains private personal information.
- The data is a benchmark or near-duplicate of benchmark prompts.
- The dataset cannot be attributed or reproduced.
- The dataset is low-quality spam, malware, credential dumps, or poisoned content.

## Privacy and PII

The data pipeline must include PII detection and removal where feasible.

Required checks:

- Email addresses
- Phone numbers
- Physical addresses
- API keys and credentials
- Government identifiers
- Private conversational logs
- Sensitive medical, legal, or financial records

Findings should be logged as aggregate counts, not as raw sensitive examples.

## Deduplication and Quality Filtering

The pipeline should include:

- Exact duplicate removal
- Near-duplicate removal
- Language identification
- Boilerplate and template filtering
- Toxicity and unsafe-content tagging
- Code license tagging
- Document quality scoring
- Domain balancing

## Benchmark Contamination

Before release, public benchmark prompts and answers must be checked against the training corpus using exact and approximate matching.

This is wired: `scripts/data/build_benchmark_index.py` assembles the canonical
"do-not-train-on-these" set (`evals/benchmark-index.jsonl`) from every eval text —
probe texts plus scored-suite prompts and answers — and `scripts/data/contamination.py`
removes any training record that exactly matches or is a near-duplicate (char n-gram
Jaccard) of a benchmark item. The index is regenerated as suites grow and a gate check
fails if it drifts out of sync.

Contamination reports should include:

- Benchmark name
- Matching method
- Number of suspected matches
- Action taken
- Residual risk

## Dataset Manifest Draft

A future machine-readable manifest can use this shape:

```yaml
name: example-dataset
version: 2026-05-26
source: https://example.com/dataset
license: CC-BY-4.0
use: pretraining
languages:
  - en
  - ja
domains:
  - web
  - reference
estimated_tokens: 1000000000
retrieval_script: scripts/data/fetch_example.py
processing_config: configs/data/example.yaml
filters:
  - exact_dedup
  - pii_redaction
  - language_id
status: candidate
notes: Synthetic example only.
```

## Immediate Implementation Tasks

1. Add `configs/data/manifest.schema.yaml`.
2. Add `docs/data-sources.md` for reviewed datasets.
3. Implement a small local data processing smoke test.
4. Add benchmark contamination checks before any release.
