from __future__ import annotations

import re

from ..code_index import CodeIndex
from ..config import Config
from ..model import Claim, Coverage, Finding
from .common import SHELL_LANGUAGES

ENV = re.compile(r"(?:\$\{?|\bexport\s+|\bos\.(?:getenv|environ\.get)\(['\"])([A-Z][A-Z0-9_]+)")


def documentation_text(config: Config, coverage: Coverage) -> str:
    paths = set(config.documents())
    # RST is searched only for mentions, not parsed as Markdown for other checks.
    for pattern in config.docs:
        if pattern.endswith(".md"):
            for path in config.root.glob(pattern[:-3] + ".rst"):
                if path.is_file() and not config.ignored(path):
                    paths.add(path)
                    relative = path.relative_to(config.root).as_posix()
                    coverage.skip(f"{relative}: RST searched for mentions only")
    for name in (
        "CHANGES.md",
        "CHANGELOG.md",
        "HISTORY.md",
        "CHANGES.rst",
        "CHANGELOG.rst",
        "HISTORY.rst",
    ):
        path = config.root / name
        if path.is_file() and path not in paths and not config.ignored(path):
            paths.add(path)
            coverage.skip(f"{name}: changelog searched for mentions only")
    return "\n".join(path.read_text(encoding="utf-8-sig") for path in sorted(paths))


def check(
    claims: list[Claim], index: CodeIndex, coverage: Coverage, documentation: str = ""
) -> list[Finding]:
    findings = []
    content = documentation or "\n".join(claim.text for claim in claims)
    if not claims:
        coverage.skip("No active documentation claims")
        return findings
    anchor = claims[0]
    for variable, ref in sorted(index.env.items()):
        coverage.checked += 1
        if not re.search(rf"\b{re.escape(variable)}\b", content):
            findings.append(
                Finding(
                    "DP005",
                    "note",
                    anchor.file,
                    anchor.line,
                    f"Environment variable {variable!r} read by the project "
                    "has no mention in searched documentation",
                    {"claim": variable, "read_at": ref},
                    ref,
                )
            )
    for claim in claims:
        documented = set(ENV.findall(claim.text))
        if claim.kind == "code" and claim.language in SHELL_LANGUAGES:
            # A shell-local directory variable is not a claim about Python environment reads.
            locals_ = set(
                re.findall(
                    r"""(?m)^\s*([A-Z][A-Z0-9_]+)=(?:'[^']*'|"[^"]*"|[^\s]+)\s*$""",
                    claim.text,
                )
            )
            documented -= locals_
        if claim.kind == "inline" and re.fullmatch(r"[A-Z][A-Z0-9]*_[A-Z0-9_]+", claim.text):
            documented.add(claim.text)
        for variable in sorted(documented - index.env.keys()):
            coverage.skip(
                f"{variable}: no literal project read; dynamic or dependency reads are unverified",
                claim,
            )
    for symbol in sorted(index.symbols.values(), key=lambda s: s.name):
        if not symbol.settings:
            continue
        short_name = symbol.name.rsplit(".", 1)[-1]
        unique = (
            sum(
                s.settings and s.name.rsplit(".", 1)[-1] == short_name
                for s in index.symbols.values()
            )
            == 1
        )
        prefixes = [symbol.name, short_name] if unique else [symbol.name]
        for claim in claims:
            if claim.kind != "inline":
                continue
            for prefix in prefixes:
                match = re.fullmatch(rf"{re.escape(prefix)}\.([A-Za-z_]\w*)", claim.text)
                if match and match[1] not in symbol.fields:
                    coverage.checked += 1
                    findings.append(
                        Finding(
                            "DP005",
                            "warning",
                            claim.file,
                            claim.line,
                            f"Settings field {claim.text!r} has no local annotation",
                            {"claim": claim.text, "local_fields": sorted(symbol.fields)},
                            symbol.ref,
                            "Check for a rename, inherited field or computed property",
                        )
                    )
                    break
        for field in sorted(symbol.fields):
            coverage.checked += 1
            if not re.search(rf"\b{re.escape(field)}\b", content):
                findings.append(
                    Finding(
                        "DP005",
                        "note",
                        anchor.file,
                        anchor.line,
                        f"Settings field {symbol.name}.{field} is undocumented",
                        {"claim": f"{symbol.name}.{field}", "fields": sorted(symbol.fields)},
                        symbol.ref,
                    )
                )
    return findings
