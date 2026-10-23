from __future__ import annotations

import difflib

from ..cli_introspect import Command
from ..model import Claim, Coverage, Finding
from .common import shell_lines, unwrap


def check(claims: list[Claim], commands: dict[str, Command], coverage: Coverage) -> list[Finding]:
    findings = []
    if not commands:
        coverage.skip("No [project.scripts] entry points")
        return findings
    seen: dict[tuple[str, ...], set[str]] = {}
    touched: dict[tuple[str, ...], Command] = {}
    locations: dict[tuple[str, ...], Claim] = {}
    for claim in claims:
        for location, tokens in shell_lines(claim):
            tokens = unwrap(tokens)
            if not tokens or tokens[0] not in commands:
                continue
            command = commands[tokens[0]]
            path = (tokens[0],)
            locations.setdefault(path, location)
            touched[path] = command
            seen.setdefault(path, set())
            coverage.checked += 1
            complete = command.complete
            values: set[str] = set()
            consume_value = False
            after_dash = False
            for token in tokens[1:]:
                if consume_value:
                    consume_value = False
                    continue
                if token == "--":
                    after_dash = True
                    continue
                if after_dash:
                    continue
                flags = command.flags
                values = command.values
                touched[path] = command
                seen.setdefault(path, set())
                if token.startswith("-"):
                    flag = token.split("=", 1)[0]
                    if flag in flags:
                        coverage.checked += 1
                        seen[path].add(flag)
                    elif not complete:
                        coverage.skip(command.reason or "Incomplete parser definition", location)
                    elif flag.startswith("--") and any(f.startswith(flag) for f in flags):
                        coverage.skip("Possible argparse option abbreviation", location)
                    elif flag.startswith("-") and not flag.startswith("--") and len(flag) > 2:
                        coverage.skip(
                            "Short-option clusters or attached values are not resolved", location
                        )
                    else:
                        coverage.checked += 1
                        close = difflib.get_close_matches(flag, sorted(flags), n=1)
                        findings.append(
                            Finding(
                                "DP001",
                                "error",
                                location.file,
                                location.line,
                                f"Unknown option {flag!r} for {' '.join(path)!r}",
                                {"claim": flag, "command": list(path), "available": sorted(flags)},
                                command.ref,
                                f"Use {close[0]}" if close else None,
                            )
                        )
                    consume_value = flag in values and "=" not in token
                elif command.children:
                    if not complete:
                        coverage.skip(
                            command.reason or "Incomplete subcommand definition", location
                        )
                    elif token not in command.children:
                        coverage.checked += 1
                        findings.append(
                            Finding(
                                "DP001",
                                "error",
                                location.file,
                                location.line,
                                f"Unknown subcommand {token!r} for {' '.join(path)!r}",
                                {"claim": token, "available": sorted(command.children)},
                                command.ref,
                            )
                        )
                        break
                    if token in command.children:
                        command = command.children[token]
                        complete = complete and command.complete
                        path = (*path, token)
                        locations.setdefault(path, location)
                        touched[path] = command
                        seen.setdefault(path, set())
                        coverage.checked += 1
    for path, command in sorted(touched.items()):
        for flag in sorted(command.flags - seen.get(path, set()) - {"--help", "-h"}):
            if not flag.startswith("--"):
                continue
            # Absence is documentation coverage, not a contradiction; opt in via severity=note.
            anchor = locations.get(path)
            if anchor:
                findings.append(
                    Finding(
                        "DP001",
                        "note",
                        anchor.file,
                        anchor.line,
                        f"Option {flag!r} for {' '.join(path)!r} "
                        "is not demonstrated in scanned commands",
                        {"claim": flag, "command": list(path)},
                        command.ref,
                    )
                )
    if not touched:
        coverage.skip("No documented invocation of a declared project command")
    return findings
