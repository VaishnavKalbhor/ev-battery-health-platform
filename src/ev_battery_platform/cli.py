import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ev-battery-platform",
        description="Run the EV battery health medallion pipeline.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print the package version.",
    )
    subparsers = parser.add_subparsers(dest="command")

    generate = subparsers.add_parser("generate", help="Generate synthetic bronze telemetry.")
    generate.add_argument(
        "--config",
        default="config/fleet_sample.json",
        help="Path to the generator configuration JSON.",
    )

    run = subparsers.add_parser("run", help="Run bronze, silver, and gold medallion jobs.")
    run.add_argument(
        "--bronze-path",
        default="data/bronze/ev_telemetry_raw.jsonl",
        help="Path to raw bronze JSONL telemetry.",
    )
    run.add_argument(
        "--silver-dir",
        default="data/silver",
        help="Directory for silver output datasets.",
    )
    run.add_argument(
        "--gold-dir",
        default="data/gold",
        help="Directory for gold output datasets.",
    )

    quality = subparsers.add_parser("quality", help="Run data quality checks.")
    quality.add_argument(
        "--silver-dir",
        default="data/silver",
        help="Directory containing silver datasets.",
    )
    quality.add_argument(
        "--gold-dir",
        default="data/gold",
        help="Directory containing gold datasets.",
    )
    quality.add_argument(
        "--report-path",
        default="reports/data_quality.md",
        help="Markdown report output path.",
    )

    dashboard = subparsers.add_parser("dashboard", help="Build HTML dashboard and executive summary.")
    dashboard.add_argument(
        "--gold-dir",
        default="data/gold",
        help="Directory containing gold datasets.",
    )
    dashboard.add_argument(
        "--silver-dir",
        default="data/silver",
        help="Directory containing silver datasets.",
    )
    dashboard.add_argument(
        "--output-dir",
        default="reports",
        help="Directory for generated dashboard and summary files.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.version:
        from . import __version__

        print(__version__)
        return

    if args.command == "generate":
        from .simulator.generate import generate_telemetry, load_config

        config = load_config(Path(args.config))
        count = generate_telemetry(config)
        print(f"Wrote {count} raw telemetry events to {config.output_path}")
        return

    if args.command == "run":
        from .pipeline import run_pipeline

        result = run_pipeline(
            bronze_path=Path(args.bronze_path),
            silver_dir=Path(args.silver_dir),
            gold_dir=Path(args.gold_dir),
        )
        print(
            "Processed "
            f"{result.raw_events} raw events into {result.silver_events} silver events, "
            f"{result.rejected_events} rejects, and {result.charging_sessions} charging sessions."
        )
        for output in result.gold_outputs:
            print(f"Gold output: {output}")
        return

    if args.command == "quality":
        from .quality import run_quality_checks

        report = run_quality_checks(
            silver_dir=Path(args.silver_dir),
            gold_dir=Path(args.gold_dir),
            report_path=Path(args.report_path),
        )
        print(f"Data quality status: {'PASS' if report.passed else 'FAIL'}")
        for check in report.checks:
            status = "PASS" if check.passed else "FAIL"
            print(f"{status} {check.name}: {check.details}")
        return

    if args.command == "dashboard":
        from .reporting import build_reports

        result = build_reports(
            gold_dir=Path(args.gold_dir),
            silver_dir=Path(args.silver_dir),
            output_dir=Path(args.output_dir),
        )
        print(f"Dashboard: {result.dashboard_path}")
        print(f"Executive summary: {result.summary_path}")
        print(
            f"Coverage: {result.vehicles} vehicles, {result.regions} regions, "
            f"{result.high_risk_vehicles} high-risk vehicles"
        )
        return

    parser.print_help()
