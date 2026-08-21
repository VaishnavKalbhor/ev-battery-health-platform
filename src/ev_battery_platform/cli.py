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

    parser.print_help()
