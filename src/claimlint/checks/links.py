from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlsplit

from ..doc_context import DocContext
from ..docs_parser import anchors, myst_labels, parse_text
from ..model import Claim, Coverage, Finding


def check(claims: list[Claim], root: Path, coverage: Coverage) -> list[Finding]:
    findings = []
    cache: dict[Path, set[str]] = {}
    text_cache: dict[Path, str] = {}
    context = DocContext.load(root)
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
        if unquote(url.path) in context.labels(source) and not url.fragment:
            coverage.checked += 1
            continue
        target = (source.parent / unquote(url.path)).resolve() if url.path else source
        if url.path and (not target.exists() or target.is_dir()):
            target = context.route(source, unquote(url.path)) or target
        if not target.is_relative_to(root):
            coverage.skip("Link resolves outside the project", claim)
            continue
        reason = ""
        if not target.exists():
            reason = "target does not exist"
        elif url.fragment and target.suffix.lower() == ".md":
            if target not in cache:
                text = target.read_text(encoding="utf-8-sig")
                text_cache[target] = text
                cache[target] = anchors(
                    parse_text(text, target.relative_to(root).as_posix()),
                    text,
                    attribute_ids=context.in_site(target) and context.attribute_ids,
                )
                if context.myst_root(target):
                    cache[target].update(myst_labels(text))
            if unquote(url.fragment) not in cache[target]:
                text = text_cache[target]
                if context.generated_anchors(target, text):
                    coverage.skip(
                        f"{claim.target}: target anchor depends on generated API "
                        "or template content",
                        claim,
                    )
                    continue
                reason = f"anchor #{unquote(url.fragment)} does not exist"
        coverage.checked += 1
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
