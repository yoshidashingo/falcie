#!/usr/bin/env python3
"""Tests for the deterministic mock/tiny-model eval hook (unit U-I4).

Property-based tests (PBT category in parentheses):
  * determinism (PBT-01): build_report over the same config twice yields identical
    per-task results and summary (the report carries no timestamp field, so the
    whole report is compared with a fixed commit seam).
  * coverage (PBT-03): the report has exactly one task entry per config task, with
    ids preserved in order.
  * summary accounting (PBT-03): summary.passed == count of per-task passed flags,
    and summary.task_count == number of tasks.
  * mock_model determinism (PBT-01): mock_model is a pure function -- equal prompts
    yield equal outputs.
  * trivial metric oracle (PBT-04): a task whose prompt has non-whitespace content
    passes; an all-whitespace/empty prompt does not.

Example-based tests complement the properties with the real smoke.yaml config,
the validation-error path, the CLI (stdout + --output), and the repo-relative
path rule.
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts" / "evals"))
sys.path.insert(0, str(_ROOT / "scripts" / "common"))
sys.path.insert(0, str(_ROOT / "tests"))

import pbt  # noqa: E402
import run_mock_eval as MOCK  # noqa: E402

SMOKE_CONFIG = _ROOT / "configs" / "evals" / "smoke.yaml"
_FIXED_SHA = "deadbeef"


# --- generators -----------------------------------------------------------


def gen_task(rng):
    """Generate one well-formed eval task dict with a unique-ish id."""
    idx = pbt.integers(0, 10_000)(rng)
    area = pbt.sampled_from(["japanese", "reasoning", "code", "safety"])(rng)
    ttype = pbt.sampled_from(["static_prompt_shape", "generation", "classification"])(rng)
    # Prompt may be empty / whitespace-only sometimes so the trivial metric sees
    # both passing and non-passing tasks.
    prompt = pbt.one_of(
        pbt.text(max_len=30),
        pbt.sampled_from(["", "   ", "\n\t", " a "]),
    )(rng)
    return {
        "id": f"task_{idx}_{rng.randint(0, 1_000_000)}",
        "area": area,
        "type": ttype,
        "prompt": prompt,
        "expected_behavior": "deterministic mock scoring",
    }


def gen_config(rng):
    """Generate a valid config dict with a non-empty, unique-id task list."""
    tasks = pbt.lists(gen_task, min_len=1, max_len=6)(rng)
    # Guarantee unique ids regardless of collisions from the generator.
    for i, task in enumerate(tasks):
        task["id"] = f"{task['id']}_{i}"
    return {
        "eval_id": "pbt-mock-eval",
        "version": "2026-06-19",
        "description": "Generated config for property-based tests.",
        "model": {"id": "not-yet-released", "status": "coming_soon"},
        "tasks": tasks,
    }


# --- property-based tests -------------------------------------------------


class TestMockEvalProperties(unittest.TestCase):
    def test_build_report_is_deterministic(self):
        # PBT-01: same config -> identical report (no timestamp in report).
        def prop(config):
            a = MOCK.build_report(config, SMOKE_CONFIG, commit_sha=_FIXED_SHA)
            b = MOCK.build_report(config, SMOKE_CONFIG, commit_sha=_FIXED_SHA)
            return a == b and a["tasks"] == b["tasks"] and a["summary"] == b["summary"]

        pbt.for_all(gen_config, prop, label="build_report determinism")

    def test_coverage_one_entry_per_task_ids_preserved(self):
        # PBT-03: one report task per config task, ids preserved in order.
        def prop(config):
            report = MOCK.build_report(config, SMOKE_CONFIG, commit_sha=_FIXED_SHA)
            if len(report["tasks"]) != len(config["tasks"]):
                return False
            report_ids = [entry["id"] for entry in report["tasks"]]
            config_ids = [task["id"] for task in config["tasks"]]
            return report_ids == config_ids

        pbt.for_all(gen_config, prop, label="coverage")

    def test_summary_passed_matches_count(self):
        # PBT-03: summary.passed == count of passed tasks; task_count == len.
        def prop(config):
            report = MOCK.build_report(config, SMOKE_CONFIG, commit_sha=_FIXED_SHA)
            expected_passed = sum(1 for e in report["tasks"] if e["passed"])
            summary = report["summary"]
            return (
                summary["passed"] == expected_passed
                and summary["task_count"] == len(report["tasks"])
                and summary["status"] == "mock_scored"
            )

        pbt.for_all(gen_config, prop, label="summary accounting")

    def test_mock_model_is_pure(self):
        # PBT-01: mock_model is deterministic in its input.
        def prop(prompt):
            return MOCK.mock_model(prompt) == MOCK.mock_model(prompt)

        pbt.for_all(pbt.text(max_len=60), prop, label="mock_model purity")

    def test_trivial_metric_oracle(self):
        # PBT-04: non-whitespace prompt passes; whitespace/empty does not.
        def prop(prompt):
            entry = MOCK.score_task(
                {
                    "id": "x",
                    "area": "a",
                    "type": "t",
                    "prompt": prompt,
                    "expected_behavior": "b",
                }
            )
            return entry["passed"] == bool(prompt.strip())

        pbt.for_all(
            pbt.one_of(pbt.text(max_len=40), pbt.sampled_from(["", " ", "\n\t", "  x "])),
            prop,
            label="trivial metric oracle",
        )

    def test_deliberately_wrong_property_returns_false(self):
        # Sanity: a property the harness must reject returns False (does not raise),
        # so for_all surfaces it as a counterexample.
        def wrong(config):
            report = MOCK.build_report(config, SMOKE_CONFIG, commit_sha=_FIXED_SHA)
            # Claim every task passed -- false whenever any task has empty output.
            return report["summary"]["passed"] == report["summary"]["task_count"] + 1

        with self.assertRaises(pbt.Counterexample):
            pbt.for_all(gen_config, wrong, label="intentionally wrong")


# --- example-based tests --------------------------------------------------


class TestMockEvalExamples(unittest.TestCase):
    def setUp(self):
        self.config = MOCK.SMOKE.load_json_compatible_yaml(SMOKE_CONFIG)

    def test_smoke_report_shape(self):
        report = MOCK.build_report(self.config, SMOKE_CONFIG, commit_sha=_FIXED_SHA)
        self.assertEqual(report["eval_id"], "falcie-smoke-eval")
        self.assertEqual(report["model_id"], MOCK.MOCK_MODEL_ID)
        self.assertEqual(report["commit_sha"], _FIXED_SHA)
        self.assertEqual(report["summary"]["status"], "mock_scored")
        self.assertEqual(report["summary"]["task_count"], 3)
        # All three smoke tasks have non-empty prompts -> all pass.
        self.assertEqual(report["summary"]["passed"], 3)
        self.assertEqual(
            [t["id"] for t in report["tasks"]],
            ["japanese_instruction_shape", "english_reasoning_shape", "code_prompt_shape"],
        )
        for entry in report["tasks"]:
            self.assertTrue(entry["passed"])
            self.assertGreater(entry["output_len"], 0)
            self.assertIn("area", entry)
            self.assertIn("type", entry)

    def test_config_path_is_repo_relative(self):
        report = MOCK.build_report(self.config, SMOKE_CONFIG, commit_sha=_FIXED_SHA)
        self.assertEqual(report["config_path"], "configs/evals/smoke.yaml")
        self.assertFalse(Path(report["config_path"]).is_absolute())

    def test_rel_out_of_repo_falls_back_to_basename(self):
        self.assertEqual(MOCK._rel(Path("/tmp/somewhere/else.yaml")), "else.yaml")

    def test_mock_model_no_real_inference_examples(self):
        self.assertEqual(MOCK.mock_model("Hello   world"), "[mock] Hello world")
        self.assertEqual(MOCK.mock_model("   "), "")
        self.assertEqual(MOCK.mock_model(""), "")
        # Japanese prompt is preserved.
        self.assertEqual(
            MOCK.mock_model("次の文章を一文で要約してください。"),
            "[mock] 次の文章を一文で要約してください。",
        )

    def test_score_task_empty_prompt_does_not_pass(self):
        entry = MOCK.score_task(
            {"id": "e", "area": "a", "type": "t", "prompt": "   ", "expected_behavior": "b"}
        )
        self.assertFalse(entry["passed"])
        self.assertEqual(entry["output_len"], 0)

    def test_cli_stdout_smoke(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = MOCK.main(["run_mock_eval.py", str(SMOKE_CONFIG)])
        self.assertEqual(rc, 0)
        report = json.loads(buf.getvalue())
        self.assertEqual(report["model_id"], MOCK.MOCK_MODEL_ID)
        self.assertEqual(report["summary"]["status"], "mock_scored")
        self.assertEqual(report["config_path"], "configs/evals/smoke.yaml")

    def test_cli_default_config(self):
        # No positional arg -> defaults to configs/evals/smoke.yaml.
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = MOCK.main(["run_mock_eval.py"])
        self.assertEqual(rc, 0)
        report = json.loads(buf.getvalue())
        self.assertEqual(report["eval_id"], "falcie-smoke-eval")

    def test_cli_writes_output_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "mock_report.json"
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = MOCK.main(["run_mock_eval.py", str(SMOKE_CONFIG), "--output", str(out)])
            self.assertEqual(rc, 0)
            self.assertTrue(out.exists())
            written = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(written["summary"]["task_count"], 3)
            # Confirm no absolute paths leaked into the report.
            self.assertNotIn(str(_ROOT), out.read_text(encoding="utf-8"))

    def test_cli_validation_error_returns_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.yaml"
            bad.write_text(json.dumps({"eval_id": "x"}), encoding="utf-8")
            rc = MOCK.main(["run_mock_eval.py", str(bad)])
        self.assertEqual(rc, 1)

    def test_cli_run_twice_identical_scored_content(self):
        # End-to-end determinism of the scored content via the CLI.
        def run():
            buf = io.StringIO()
            with redirect_stdout(buf):
                MOCK.main(["run_mock_eval.py", str(SMOKE_CONFIG)])
            return json.loads(buf.getvalue())

        a, b = run(), run()
        self.assertEqual(a["tasks"], b["tasks"])
        self.assertEqual(a["summary"], b["summary"])


MOCK_MODEL_ID = MOCK.MOCK_MODEL_ID


if __name__ == "__main__":
    unittest.main()
