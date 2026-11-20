"""Command line interface for envlens."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from envlens import __version__
from envlens.analysis import analyze
from envlens.config import Config
from envlens.models import Severity
from envlens.render import render_json, render_markdown, render_table
from envlens.sync import sync_example

_FAIL_ON = ("critical", "high", "medium", "low", "info", "none")
_FORMATS = ("table", "json", "markdown")


def build_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="envlens",
        description="X-ray vision for environment variables: find drift, leaks and missing config.",
        epilog=(
            "Examples: envlens scan . --format table | envlens scan --fail-on critical "
            "| envlens sync-example"
        ),
    )
    parser.add_argument("--version", action="version", version=f"envlens {__version__}")
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    scan = subparsers.add_parser("scan", help="analyze a project (default command)")
    scan.add_argument(
        "path", nargs="?", default=".", help="project root (default: current directory)"
    )
    scan.add_argument(
        "--format", choices=_FORMATS, default="table", help="output format (default: table)"
    )
    scan.add_argument(
        "--fail-on",
        choices=_FAIL_ON,
        default="high",
        help="minimum severity that fails the command (default: high)",
    )
    scan.add_argument("--no-color", action="store_true", help="disable ANSI colors")

    sync = subparsers.add_parser("sync-example", help="append missing keys to .env.example safely")
    sync.add_argument(
        "path", nargs="?", default=".", help="project root (default: current directory)"
    )
    sync.add_argument(
        "--output", default=".env.example", help="template path (default: .env.example)"
    )
    return parser


def _use_color(no_color: bool) -> bool:
    return not no_color and sys.stdout.isatty() and "NO_COLOR" not in os.environ


def _resolve(path: str) -> Path:
    return Path(path).expanduser().resolve()


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "scan"
    path = _resolve(args.path if hasattr(args, "path") else ".")

    if not path.is_dir():
        parser.error(f"not a directory: {path}")

    if command == "sync-example":
        added = sync_example(path, Config.load(path), args.output)
        if added:
            print(f"Added {len(added)} variable(s) to {args.output}: {', '.join(added)}")
        else:
            print(f"{args.output} is already up to date.")
        return 0

    report = analyze(path)
    output_format = getattr(args, "format", "table")
    if output_format == "json":
        print(render_json(report))
    elif output_format == "markdown":
        print(render_markdown(report))
    else:
        print(render_table(report, color=_use_color(getattr(args, "no_color", False))))

    threshold = getattr(args, "fail_on", "high")
    if threshold == "none":
        return 0
    limit = Severity(threshold).rank
    return 1 if any(finding.severity.rank >= limit for finding in report.findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
