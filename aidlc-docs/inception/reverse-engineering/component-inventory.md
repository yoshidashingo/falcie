# Component Inventory

> "Package" here means a coherent directory/concern, since the repo has no formal package manager yet.

## Application Packages (CLI tooling)
- `scripts/data/` — manifest validation tooling.
- `scripts/evals/` — evaluation smoke runner.
- `scripts/tokenizer/` — tokenizer probe summarizer.

## Configuration Packages
- `configs/data/` — `manifest.schema.yaml`, `example-manifest.yaml`.
- `configs/evals/` — `smoke.yaml`.
- `configs/tokenizer/` — `evaluation.yaml`.

## Documentation Packages
- `docs/` — roadmap, evaluation-plan, training-plan, data-policy, data-sources, architecture-decisions, tokenizer-evaluation, model-card-template, release-checklist, plus `index.html` / `ja.html` landing pages.
- Repo meta — `README.md`, `README-ja.md`, `CONTRIBUTING.md`, `LICENSE`, `AGENTS.md`.

## Test / Fixture Packages
- `evals/tokenizer/` — `probes.jsonl` fixtures.
- `evals/` — `README.md` benchmark inventory.

## Infrastructure Packages
- None (no CDK / Terraform / CloudFormation / Docker / CI workflows present).

## Total Count
- **Total source scripts**: 3 Python files (excluding `__pycache__` bytecode).
- **Config files**: 4 YAML (JSON-compatible) specs.
- **Fixtures**: 1 JSONL probe file.
- **Docs**: 9 markdown plans + 2 HTML landing pages + 4 repo-meta files.
- **Application**: 3 concerns (data, evals, tokenizer).
- **Infrastructure**: 0.
- **Shared**: 0 (no shared library yet).
- **Test/Fixture**: 2 (probes + eval inventory).
