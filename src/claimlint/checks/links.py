from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlsplit

from ..docs_parser import anchors, parse_text
from ..model import Claim, Coverage, Finding


def check(claims: list[Claim], root: Path, coverage: Coverage) -> list[Finding]:
    findings = []
    cache: dict[Path, set[str]] = {}
    for claim in claims:
        if claim.kind != "link":
            continue
        url = urlsplit(claim.target)
        if url.scheme or url.netloc or claim.target.startswith("/"):
            coverage.skip("External or site-root URL; no network link checking", claim)
            continue
        if not url.path and not url.fragment:
            continue
        source = root / claim.file
        target = (source.parent / unquote(url.path)).resolve() if url.path else source
        if not target.is_relative_to(root):
            coverage.skip("Link resolves outside the project", claim)
            continue
        coverage.checked += 1
        reason = ""
        if not target.exists():
            reason = "target does not exist"
        elif url.fragment and target.suffix.lower() == ".md":
            if target not in cache:
                text = target.read_text(encoding="utf-8-sig")
                cache[target] = anchors(parse_text(text, target.relative_to(root).as_posix()), text)
            if unquote(url.fragment) not in cache[target]:
                reason = f"anchor #{unquote(url.fragment)} does not exist"
        if reason:
            findings.append(
                Finding(
                    "DP006",
                    "error",
                    claim.file,
                    claim.line,
                    f"Broken link {claim.target!r}: {reason}",
                    {"claim": claim.target, "resolved": target.relative_to(root).as_posix()},
                    claim.file if target == source else target.relative_to(root).as_posix(),
                )
            )
    return findings
