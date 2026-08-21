from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ev_battery_platform.pipeline import run_pipeline
from ev_battery_platform.quality import run_quality_checks
from ev_battery_platform.reporting import build_reports
from ev_battery_platform.simulator import GenerationConfig, generate_telemetry


class PipelineIntegrationTest(unittest.TestCase):
    def test_full_medallion_flow_produces_quality_checked_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            root = Path(workspace)
            bronze_path = root / "bronze" / "events.jsonl"
            silver_dir = root / "silver"
            gold_dir = root / "gold"
            report_path = root / "reports" / "quality.md"

            config = GenerationConfig(
                seed=7,
                fleet_size=4,
                days=2,
                events_per_vehicle_per_day=24,
                start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
                output_path=bronze_path,
            )
            generated = generate_telemetry(config)
            result = run_pipeline(bronze_path=bronze_path, silver_dir=silver_dir, gold_dir=gold_dir)
            quality = run_quality_checks(silver_dir=silver_dir, gold_dir=gold_dir, report_path=report_path)
            reports = build_reports(gold_dir=gold_dir, silver_dir=silver_dir, output_dir=root / "reports")

            self.assertEqual(generated, 192)
            self.assertEqual(result.raw_events, 192)
            self.assertGreater(result.silver_events, 0)
            self.assertGreater(result.charging_sessions, 0)
            self.assertTrue((silver_dir / "battery_events.csv").exists())
            self.assertTrue((gold_dir / "battery_health_summary.csv").exists())
            self.assertTrue(quality.passed)
            self.assertIn("Overall status: PASS", report_path.read_text(encoding="utf-8"))
            self.assertEqual(reports.vehicles, 4)
            self.assertTrue(reports.dashboard_path.exists())
            self.assertTrue(reports.summary_path.exists())
            self.assertIn("EV Battery Health Dashboard", reports.dashboard_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
