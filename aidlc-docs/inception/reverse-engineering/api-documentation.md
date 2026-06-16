# API Documentation

There are no network/REST APIs in the repository. The "interfaces" are command-line entry points and the data schemas they enforce.

## Command-Line Interfaces

### validate_manifest.py
- **Invocation**: `python3 scripts/data/validate_manifest.py [manifest_path ...]`
- **Default**: validates `configs/data/example-manifest.yaml` when no paths are given.
- **Behavior**: also parses `configs/data/manifest.schema.yaml` to ensure it stays well-formed.
- **Output**: `"<path>: ok"` per valid file (stdout); `"<path>: invalid"` plus indented `- <error>` lines (stderr) per invalid file.
- **Exit code**: `0` if all valid, `1` if any invalid.

### run_smoke_eval.py
- **Invocation**: `python3 scripts/evals/run_smoke_eval.py [config] [--output PATH]`
- **Default config**: `configs/evals/smoke.yaml`.
- **Behavior**: validates the eval config shape; builds a JSON report including `commit_sha` (via `git rev-parse HEAD`, or `"unknown"`), `created_at` (UTC ISO), and one entry per task with `status: validated_not_run`.
- **Output**: JSON report to stdout, or to `--output` file if provided.
- **Exit code**: `0` on success, `1` if validation errors.

### summarize_probes.py
- **Invocation**: `python3 scripts/tokenizer/summarize_probes.py [probes_path]`
- **Default**: `evals/tokenizer/probes.jsonl`.
- **Behavior**: validates each JSONL probe and computes coverage.
- **Output**: human-readable summary (probe count, total characters, total bytes, counts by language, counts by domain).
- **Exit code**: `0` on success; raises `ValueError` on malformed probes.

## Internal Functions (selected signatures)

### validate_manifest.py
- `load_json_compatible_yaml(path: Path) -> dict[str, Any]`
- `require_non_empty_string(manifest, field) -> list[str]`
- `validate_string_list(manifest, field) -> list[str]`
- `validate_check_object(manifest, field) -> list[str]`
- `validate_manifest(path: Path) -> list[str]`
- `main(argv: list[str]) -> int`

### run_smoke_eval.py
- `load_json_compatible_yaml(path: Path) -> dict[str, Any]`
- `current_commit() -> str`
- `validate_config(config: dict[str, Any]) -> list[str]`
- `build_report(config, config_path: Path) -> dict[str, Any]`
- `main(argv: list[str]) -> int`

### summarize_probes.py
- `load_probes(path: Path) -> list[dict[str, Any]]`
- `main(argv: list[str]) -> int`

## Data Models

### Dataset Manifest (enforced by validate_manifest.py)
- **Required fields**: `name`, `version`, `source`, `license`, `license_review`, `use`, `languages`, `domains`, `estimated_tokens`, `retrieval_script`, `processing_config`, `filters`, `status`, `pii_policy`, `contamination_check`.
- **Field rules**:
  - Non-empty strings: `name`, `version`, `source`, `license`, `retrieval_script`, `processing_config`.
  - `license_review` ∈ {compatible, needs_review, restricted, rejected}.
  - `use` ∈ {pretraining, supervised_fine_tuning, preference_training, evaluation, tokenizer}.
  - `status` ∈ {candidate, approved, quarantined, rejected, deprecated}.
  - `languages`: non-empty, unique strings matching `^[a-z]{2,3}(-[A-Z]{2})?$` (e.g., `ja`, `en`, `en-US`).
  - `domains`, `filters`: non-empty, unique string lists.
  - `estimated_tokens`: non-negative integer.
  - `pii_policy`, `contamination_check`: objects with `required: bool`, `method: non-empty string`, `status` ∈ {not_started, planned, complete, not_applicable}.
  - `reviewed_at` (optional): `YYYY-MM-DD`.

### Evaluation Smoke Config (enforced by run_smoke_eval.py)
- **Required top-level**: `eval_id`, `version`, `description`, `model`, `tasks`.
- `model`: object with string `model.id` (optional `status`).
- `tasks`: non-empty array; each task requires `id`, `area`, `type`, `prompt`, `expected_behavior` (all non-empty strings); `id` must be unique.

### Evaluation Smoke Report (produced by run_smoke_eval.py)
- Fields: `eval_id`, `version`, `config_path` (repo-relative), `model_id`, `model_status`, `commit_sha`, `created_at`, `tasks[]` (`id`, `area`, `type`, `status="validated_not_run"`), `summary` (`task_count`, `status`, `note`).

### Tokenizer Probe (enforced by summarize_probes.py)
- **Per JSONL line**: `id`, `language`, `domain`, `text` (all non-empty strings); `id` must be unique across the file.
