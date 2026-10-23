from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .baseline import apply_baseline, write_baseline
from .config import check_ids
from .engine import Options, scan
from .fixer import CodexFixer, fix
from .report import fails, render


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="claimlint", description="Check Python documentation against source evidence"
    )
    parser.add_argument("--version", action="version", version=__version__)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "path", nargs="?", default=".", help="Project directory containing pyproject.toml"
    )
    common.add_argument("--select", help="Comma-separated check IDs, e.g. DP002,DP003")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", parents=[common], help="Report documentation drift")
    check.add_argument("--format", choices=["text", "json", "github"], default="text")
    check.add_argument("--min-severity", choices=["note", "warning", "error"], default="warning")
    check.add_argument("--baseline", type=Path, help="Hide findings already in a baseline file")
    check.add_argument(
        "--run-examples",
        action="store_true",
        help="Execute trusted Python examples (not sandboxed)",
    )
    check.add_argument(
        "--introspect-cli", action="store_true", help="Execute trusted entry points with --help"
    )
    check.add_argument("--timeout", type=float, default=10, help="Subprocess timeout in seconds")
    check.add_argument(
        "--summary", type=Path, help="Write Markdown summary, e.g. to GITHUB_STEP_SUMMARY"
    )
    baseline = commands.add_parser("baseline", parents=[common], help="Record existing findings")
    baseline.add_argument(
        "--output", type=Path, help="Output path (default: project/.claimlint-baseline.json)"
    )
    fixing = commands.add_parser(
        "fix", parents=[common], help="Propose and validate documentation-only Codex patches"
    )
    fixing.add_argument(
        "--apply", action="store_true", help="Write validated patches to the documentation"
    )
    fixing.add_argument("--codex", default="codex", help="Codex executable")
    fixing.add_argument(
        "--timeout", type=float, default=120, help="Model subprocess timeout in seconds"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        root = Path(args.path).resolve()
        selected = check_ids(args.select.split(",")) if args.select is not None else None
        options = Options(select=selected)
        if getattr(args, "timeout", 1) <= 0:
            raise ValueError("--timeout must be positive")
        if args.command == "fix":
            result = fix(root, CodexFixer(args.codex, args.timeout), options, apply=args.apply)
            sys.stdout.write(result.diff)
            print(
                f"{len(result.accepted)} validated fix(es), {len(result.rejected)} rejected",
                file=sys.stderr,
            )
            for rejection in result.rejected:
                print(rejection, file=sys.stderr)
            return 1 if result.rejected else 0
        if args.command == "check":
            options.run_examples = args.run_examples
            options.introspect_cli = args.introspect_cli
            options.timeout = args.timeout
        scanned = scan(root, options)
        if args.command == "baseline":
            output = args.output or root / ".claimlint-baseline.json"
            write_baseline(output, scanned)
            print(f"Recorded {len(scanned.findings)} finding(s) in {output}")
            return 0
        if args.baseline:
            apply_baseline(args.baseline, scanned)
        prefix = root.relative_to(Path.cwd()).as_posix() if root.is_relative_to(Path.cwd()) else ""
        prefix = prefix + "/" if prefix and prefix != "." else ""
        sys.stdout.write(render(scanned, args.format, annotation_prefix=prefix))
        summary = args.summary
        if summary:
            lines = [
                f"### claimlint: {len(scanned.findings)} finding(s) "
                f"in {len(scanned.documents)} documents",
                "",
            ]
            for finding in scanned.findings:
                message = finding.message.replace("\n", " ").replace("`", "'")
                lines.append(
                    f"- **{finding.check}** `{finding.doc_file}:{finding.doc_line}` — {message}"
                )
            lines.extend(
                [
                    "",
                    "Coverage: "
                    + "; ".join(
                        f"{key}: {stat.checked} checked, {len(stat.skipped)} skipped"
                        for key, stat in scanned.coverage.items()
                    ),
                    "",
                ]
            )
            with summary.open("a", encoding="utf-8") as stream:
                stream.write("\n".join(lines))
        if args.format == "github":
            print(
                f"Scanned {len(scanned.documents)} documents; "
                + "; ".join(
                    f"{key}: {stat.checked} checked/{len(stat.skipped)} skipped"
                    for key, stat in scanned.coverage.items()
                ),
                file=sys.stderr,
            )
        return int(fails(scanned, args.min_severity))
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"claimlint: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"claimlint: internal error ({type(exc).__name__}): {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
