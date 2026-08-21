import argparse


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
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.version:
        from . import __version__

        print(__version__)
        return

    parser.print_help()

