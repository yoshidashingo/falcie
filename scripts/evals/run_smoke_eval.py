#!/usr/bin/env python3
"""Run the dependency-free fal'Cie evaluation smoke check.

The smoke check validates evaluation configuration shape and emits a JSON report.
It intentionally does not call a model yet.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "configs" / "evals" / "smoke.yaml"
REQUIRED_TOP_LEVEL = {"eval_id", "version", "description", "model", "tasks"}
REQUIRED_TASK_FIELDS = {"id", "area", "type", "prompt", "expected_behavior"}


def load_json_compatible_yaml(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: not JSON-compatible YAML: {exc}") from exc

    if not isinstance(value, dict):
        raise ValueError(f"{path}: config root must be an object")
    return value


def current_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"
    return result.stdout.strip()


def validate_config(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    missing = sorted(REQUIRED_TOP_LEVEL - config.keys())
    if missing:
        errors.append(f"missing top-level fields: {', '.join(missing)}")

    model = config.get("model")
    if not isinstance(model, dict) or not isinstance(model.get("id"), str):
        errors.append("model.id must be present")

    tasks = config.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        errors.append("tasks must be a non-empty array")
        return errors

    seen_ids: set[str] = set()
    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            errors.append(f"tasks[{index}] must be an object")
            continue
        missing_task_fields = sorted(REQUIRED_TASK_FIELDS - task.keys())
        if missing_task_fields:
            errors.append(
                f"tasks[{index}] missing fields: {', '.join(missing_task_fields)}"
            )
        task_id = task.get("id")
        if not isinstance(task_id, str) or not task_id:
            errors.append(f"tasks[{index}].id must be a non-empty string")
        elif task_id in seen_ids:
            errors.append(f"duplicate task id: {task_id}")
        else:
            seen_ids.add(task_id)

        for field in ["area", "type", "prompt", "expected_behavior"]:
            if not isinstance(task.get(field), str) or not task.get(field):
                errors.append(f"tasks[{index}].{field} must be a non-empty string")

    return errors


def build_report(config: dict[str, Any], config_path: Path) -> dict[str, Any]:
    tasks = config["tasks"]
    return {
        "eval_id": config["eval_id"],
        "version": config["version"],
        "config_path": str(config_path.relative_to(ROOT)),
        "model_id": config["model"]["id"],
        "model_status": config["model"].get("status", "unknown"),
        "commit_sha": current_commit(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tasks": [
            {
                "id": task["id"],
                "area": task["area"],
                "type": task["type"],
                "status": "validated_not_run",
            }
            for task in tasks
        ],
        "summary": {
            "task_count": len(tasks),
            "status": "ok",
            "note": "Smoke validation only; no model inference was run.",
        },
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", nargs="?", default=str(DEFAULT_CONFIG))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv[1:])

    config_path = Path(args.config)
    config = load_json_compatible_yaml(config_path)
    errors = validate_config(config)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1

    report = build_report(config, config_path.resolve())
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
