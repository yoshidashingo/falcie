#!/usr/bin/env python3
"""End-to-end integration test for the fal'Cie data pipeline (U-D1..U-D5).

The five stages are unit-tested individually; this pins that they *compose*:
``ingest -> dedup -> filter -> contamination -> aggregate`` works both at the
library level and as a CLI chain over real files. It is the integration guard the
per-stage unit tests cannot give on their own.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts" / "data"))

import aggregate as A  # noqa: E402
import contamination as C  # noqa: E402
import dedup as D  # noqa: E402
import filter as F  # noqa: E402
import ingest as I  # noqa: E402
import records as R  # noqa: E402

BENCHMARK = "this exact sentence is a held-out benchmark item"
RAW_TEXTS = [
    "fal'Cie is an open-weight language model.",
    "fal'Cie is an open-weight language model.",  # exact dup of #0
    "fal'Cie is an open weight language model!!",  # near-dup of #0
    "   ",  # empties dropped by ingest
    "",
    "ok",  # short — dropped by a min_chars=3 filter
    "日本語の文書もパイプラインを通過します。",
    BENCHMARK,  # contaminated: equals a benchmark item
]


class TestDataPipelineLibrary(unittest.TestCase):
    def test_library_composition(self) -> None:
        recs = I.ingest_records(RAW_TEXTS, source="smoke")
        # ingest drops the two empty/blank docs; ids are unique and texts non-empty.
        self.assertEqual(len(recs), 6)
        self.assertTrue(all(r.text for r in recs))
        self.assertEqual(len({r.id for r in recs}), len(recs))

        deduped = D.dedup(recs, near_dup_threshold=0.8)
        # exact dup removed; deduped is an order-preserving subsequence of input.
        ids = [r.id for r in recs]
        deduped_ids = [r.id for r in deduped]
        self.assertLess(len(deduped), len(recs))
        self.assertEqual(deduped_ids, [i for i in ids if i in set(deduped_ids)])

        filtered = F.filter_records(deduped, {"min_chars": 3})
        self.assertTrue(all(len(r.text) >= 3 for r in filtered))
        self.assertTrue(set(r.id for r in filtered).issubset(set(r.id for r in deduped)))

        clean = C.remove_contaminated(filtered, [BENCHMARK], threshold=0.8)
        # the record equal to the benchmark must be gone.
        self.assertFalse(any(r.text == BENCHMARK for r in clean))
        self.assertTrue(set(r.id for r in clean).issubset(set(r.id for r in filtered)))

        report = A.aggregate(clean)
        self.assertEqual(report["total_records"], len(clean))
        self.assertEqual(
            report["total_records"],
            sum(b["records"] for b in report["by_source"].values()),
        )
        self.assertEqual(
            report["total_chars"], sum(len(r.text) for r in clean)
        )

    def test_pipeline_is_idempotent_at_each_repeatable_stage(self) -> None:
        recs = I.ingest_records(RAW_TEXTS, source="smoke")
        deduped = D.dedup(recs, near_dup_threshold=0.8)
        self.assertEqual(
            [r.id for r in D.dedup(deduped, near_dup_threshold=0.8)],
            [r.id for r in deduped],
        )
        filtered = F.filter_records(deduped, {"min_chars": 3})
        self.assertEqual(
            [r.id for r in F.filter_records(filtered, {"min_chars": 3})],
            [r.id for r in filtered],
        )


class TestDataPipelineCLIChain(unittest.TestCase):
    def _run(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, *args],
            cwd=_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, msg=f"{args} failed:\n{result.stderr}")
        return result

    def test_cli_chain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            raw = d / "raw.txt"
            raw.write_text("\n".join(RAW_TEXTS), encoding="utf-8")
            bench = d / "bench.txt"
            bench.write_text(BENCHMARK + "\n", encoding="utf-8")

            norm, ded, filt, clean = (d / "norm.jsonl", d / "ded.jsonl", d / "filt.jsonl", d / "clean.jsonl")
            self._run(["scripts/data/ingest.py", str(raw), "--source", "smoke", "--output", str(norm)])
            self._run(["scripts/data/dedup.py", str(norm), "--near-dup-threshold", "0.8", "--output", str(ded)])
            cfg = d / "filter.yaml"
            cfg.write_text('{"min_chars": 3}', encoding="utf-8")
            self._run(["scripts/data/filter.py", str(ded), "--config", str(cfg), "--output", str(filt)])
            self._run(
                ["scripts/data/contamination.py", str(filt), "--benchmarks", str(bench),
                 "--threshold", "0.8", "--remove", "--output", str(clean)]
            )
            # Flag mode (no --remove): every record carries contamination meta, and
            # that meta survives the JSONL write and a downstream aggregate read.
            flagged = d / "flagged.jsonl"
            self._run(
                ["scripts/data/contamination.py", str(filt), "--benchmarks", str(bench),
                 "--threshold", "0.8", "--output", str(flagged)]
            )
            flagged_recs = R.read_records(flagged)
            self.assertTrue(all("contaminated" in r.meta for r in flagged_recs))
            self.assertTrue(
                all(0.0 <= r.meta["contamination_score"] <= 1.0 for r in flagged_recs)
            )
            self.assertTrue(any(r.meta["contaminated"] for r in flagged_recs))  # benchmark item
            self._run(["scripts/data/aggregate.py", str(flagged), "--format", "json"])

            report = self._run(["scripts/data/aggregate.py", str(clean), "--format", "md"])
            self.assertIn("# Dataset Aggregation Report", report.stdout)

            # The benchmark item must not survive into the cleaned corpus.
            final = R.read_records(clean)
            self.assertFalse(any(r.text == BENCHMARK for r in final))
            self.assertGreater(len(final), 0)


if __name__ == "__main__":
    unittest.main()
