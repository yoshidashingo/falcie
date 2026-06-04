# Data Sources

This file tracks candidate data sources for fal'Cie. Raw datasets must not be committed to this repository. Add source manifests, retrieval instructions, filtering notes, and review status instead.

## Review Status

Use these statuses consistently:

- `candidate`: proposed but not yet reviewed.
- `approved`: reviewed for license, privacy, quality, and contamination risk.
- `quarantined`: potentially useful, but blocked by unresolved legal, quality, or safety concerns.
- `rejected`: not acceptable for training.
- `deprecated`: previously accepted, but no longer used.

## Manifest Requirements

Every candidate source needs a manifest that follows `configs/data/manifest.schema.yaml`.

For now, manifest files use JSON-compatible YAML so they can be checked with the Python standard library. Native YAML can be introduced later if the project adopts a dependency-managed Python environment.

Required review dimensions:

- License compatibility with open-weight release
- Intended use: pretraining, supervised fine-tuning, preference training, evaluation, or tokenizer
- Language and domain tags
- Estimated token count
- Retrieval and processing reproducibility
- PII filtering requirements
- Benchmark contamination check requirements
- Final review status

## Current Sources

| Name | Manifest | Use | Status | Notes |
| --- | --- | --- | --- | --- |
| example-synthetic-corpus | `configs/data/example-manifest.yaml` | pretraining | rejected | Schema smoke-test example only. Not a real dataset. |

## Adding a Source

1. Create a manifest under `configs/data/sources/`.
2. Run the manifest validator.
3. Add a row to the table above.
4. Do not add retrieval code until the source passes initial license review.
5. Do not use the source for training until it is marked `approved`.

## Minimum Approval Bar

A source can be marked `approved` only when:

- License or terms are documented.
- Open-weight release risk is understood.
- PII policy is defined.
- Benchmark contamination check is planned or complete.
- Reproducible retrieval or snapshot instructions exist.
- Exclusion conditions are documented.
