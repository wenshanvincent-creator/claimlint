from __future__ import annotations

import re
from pathlib import Path

from ..config import Config
from ..model import Claim, Coverage, Finding
from .common import shell_lines, unwrap

TOOLS = {"pytest", "ruff", "uv", "mypy", "black", "coverage", "tox"}
PATH = re.compile(r"^(?:\.?\.?/)?[\w.@/-]+(?:\.(?:py|toml|json|ya?ml|md|txt|sh|ps1)|/)$")


def _dependencies(config: Config) -> set[str]:
    project = config.project.get("project", {})
    dependencies = list(project.get("dependencies", []))
    for group in project.get("optional-dependencies", {}).values():
        dependencies.extend(group)
    for group in config.project.get("dependency-groups", {}).values():
        dependencies.extend(dep for dep in group if isinstance(dep, str))
    dependencies.extend(config.project.get("build-system", {}).get("requires", []))
    return {re.split(r"[\s<>=!~\[;]", d)[0].lower().replace("_", "-") for d in dependencies}


def check(claims: list[Claim], config: Config, coverage: Coverage) -> list[Finding]:
    findings = []
    dependencies = _dependencies(config)
    targets: set[str] = set()
    makefile = config.root / "Makefile"
    if makefile.is_file():
        targets = set(
            re.findall(r"^([\w.-]+)\s*:(?!=)", makefile.read_text(encoding="utf-8"), re.M)
        )
    seen_tools: set[tuple[str, str]] = set()
    for claim in claims:
        if Path(claim.file).name not in {"AGENTS.md", "CLAUDE.md"}:
            continue
        candidates: list[tuple[Claim, str]] = []
        if claim.kind == "inline" and PATH.fullmatch(claim.text):
            candidates.append((claim, claim.text))
        for location, raw in shell_lines(claim):
            tokens = unwrap(raw)
            if not tokens:
                continue
            tool = tokens[0]
            args = tokens[1:]
            if tool in {"python", "python3", "py"} and args[:1] == ["-m"]:
                tool, args = (args[1], args[2:]) if len(args) >= 2 else (tool, [])
            if tool in TOOLS:
                coverage.checked += 1
                pair = (location.file, tool)
                if tool not in dependencies and pair not in seen_tools:
                    seen_tools.add(pair)
                    findings.append(
                        Finding(
                            "DP007",
                            "note",
                            location.file,
                            location.line,
                            f"Agent command uses {tool!r}, "
                            "absent from declared project dependencies",
                            {"claim": tool, "dependencies": sorted(dependencies)},
                            "pyproject.toml",
                            "Document how this tool is provisioned, or declare a dev dependency",
                        )
                    )
            if tool == "make":
                for target in args:
                    if target.startswith("-") or "=" in target:
                        continue
                    coverage.checked += 1
                    if target not in targets:
                        findings.append(
                            Finding(
                                "DP007",
                                "error",
                                location.file,
                                location.line,
                                f"Make target {target!r} does not exist",
                                {"claim": target, "targets": sorted(targets)},
                                "Makefile",
                            )
                        )
            if tool in {"python", "python3", "py", "pytest", "ruff", "mypy", "black", "bash", "sh"}:
                for arg in args:
                    arg = arg.split("::", 1)[0]
                    if PATH.fullmatch(arg) or arg.startswith(
                        ("tests/", "test/", "scripts/", "src/")
                    ):
                        candidates.append((location, arg))
        for location, value in candidates:
            if any(char in value for char in "*?{}<>") or value.startswith(("http", "/")):
                continue
            # Commands execute at the root; prose references may be local to the agent file.
            target = (config.root / value).resolve()
            local = (config.root / location.file).parent / value
            if not target.is_relative_to(config.root):
                coverage.skip("File reference resolves outside the repository", location)
                continue
            coverage.checked += 1
            if not target.exists() and not local.exists():
                findings.append(
                    Finding(
                        "DP007",
                        "error",
                        location.file,
                        location.line,
                        f"Agent instruction references missing file or test path {value!r}",
                        {"claim": value, "resolved": target.relative_to(config.root).as_posix()},
                        target.relative_to(config.root).as_posix(),
                    )
                )
    return findings
