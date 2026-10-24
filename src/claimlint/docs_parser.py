from __future__ import annotations

import re
from pathlib import Path

from markdown_it import MarkdownIt

from .model import Claim

DIRECTIVE = re.compile(r"<!--\s*(?:claimlint|docproof):\s*(skip|ignore\s+[^>]+?)\s*-->")


def _directives(lines: list[str], start: int, end: int) -> tuple[frozenset[str], bool]:
    ignored: set[str] = set()
    skip = False
    for match in DIRECTIVE.finditer("\n".join(lines[max(0, start - 1) : end])):
        if match[1] == "skip":
            skip = True
        else:
            ignored.update(re.findall(r"DP\d{3}", match[1]))
    return frozenset(ignored), skip


def parse_document(path: Path, root: Path) -> list[Claim]:
    return parse_text(path.read_text(encoding="utf-8-sig"), path.relative_to(root).as_posix())


def parse_text(text: str, filename: str) -> list[Claim]:
    lines = text.splitlines()
    claims: list[Claim] = []
    tokens = MarkdownIt("commonmark", {"html": True}).parse(text)
    for i, token in enumerate(tokens):
        if token.map is None:
            continue
        start, end = token.map
        ignored, skip = _directives(lines, start, start + 1)
        if token.type in {"fence", "code_block"}:
            first = start + (1 if token.type == "fence" else 0)
            claims.append(
                Claim(
                    filename,
                    first + 1,
                    "code",
                    token.content,
                    token.info.split()[0].lower() if token.info else "",
                    ignored=ignored,
                    skip=skip,
                )
            )
        elif token.type == "heading_open":
            content = tokens[i + 1]
            heading = "".join(
                c.content for c in (content.children or []) if c.type in {"text", "code_inline"}
            )
            claims.append(Claim(filename, start + 1, "heading", heading))
        elif token.type == "inline":
            # markdown-it gives block line maps; track the raw inline cursor to locate spans.
            cursor = 0
            raw = token.content
            for child in token.children or []:
                if child.type in {"softbreak", "hardbreak"}:
                    newline = raw.find("\n", cursor)
                    if newline >= 0:
                        cursor = newline + 1
                    continue
                if child.type == "code_inline":
                    pos = raw.find(child.markup or "`", cursor)
                    if pos < 0:
                        pos = cursor
                    line_start = start + raw[:pos].count("\n")
                    inline_ignore, inline_skip = _directives(lines, line_start, line_start + 1)
                    claims.append(
                        Claim(
                            filename,
                            line_start + 1,
                            "inline",
                            child.content,
                            ignored=inline_ignore,
                            skip=inline_skip,
                        )
                    )
                    close = raw.find(child.markup or "`", pos + len(child.markup or "`"))
                    cursor = (close + len(child.markup or "`")) if close >= 0 else pos + 1
                elif child.type in {"link_open", "image"}:
                    target = child.attrGet("href" if child.type == "link_open" else "src") or ""
                    # Search the label opening, so reference-style links retain their use-site line.
                    pos = raw.find("[", cursor)
                    if pos < 0:
                        pos = cursor
                    line_start = start + raw[:pos].count("\n")
                    link_ignore, link_skip = _directives(lines, line_start, line_start + 1)
                    claims.append(
                        Claim(
                            filename,
                            line_start + 1,
                            "link",
                            child.content,
                            target=target,
                            ignored=link_ignore,
                            skip=link_skip,
                        )
                    )
                    cursor = pos + 1
                elif child.type == "text":
                    pos = raw.find(child.content, cursor)
                    if pos >= 0:
                        cursor = pos + len(child.content)
    return claims


def active(claims: list[Claim], check: str) -> list[Claim]:
    return [claim for claim in claims if check not in claim.ignored and not claim.skip]


def slug(text: str) -> str:
    # GitHub-style heading IDs: punctuation stripped, Unicode letters retained.
    return re.sub(r"[^\w\- ]", "", text.lower()).replace(" ", "-")


def myst_labels(text: str) -> set[str]:
    return {
        match[1]
        for token in MarkdownIt("commonmark").parse(text)
        if token.type == "inline"
        for match in re.finditer(r"(?m)^\(([^\n]+)\)=\s*$", token.content)
    }


def anchors(claims: list[Claim], text: str, *, attribute_ids: bool = False) -> set[str]:
    result: set[str] = set()
    counts: dict[str, int] = {}
    for claim in claims:
        if claim.kind == "heading":
            heading = re.sub(r"\s*\{[^{}]*\}\s*$", "", claim.text) if attribute_ids else claim.text
            base = slug(heading)
            number = counts.get(base, 0)
            candidate = f"{base}-{number}" if number else base
            while candidate in result:
                number += 1
                candidate = f"{base}-{number}"
            result.add(candidate)
            counts[base] = number + 1
    # Only rendered HTML contributes anchors; HTML shown inside code fences does not.
    for token in MarkdownIt("commonmark", {"html": True}).parse(text):
        if attribute_ids and token.type == "inline":
            # Attributes in code spans/fences are examples, not rendered IDs.
            visible = "".join(
                child.content for child in token.children or [] if child.type == "text"
            )
            result.update(re.findall(r"\{[^{}]*#([^\s{}]+)[^{}]*\}", visible))
        html = (
            token.content
            if token.type == "html_block"
            else "".join(
                child.content for child in token.children or [] if child.type == "html_inline"
            )
        )
        html = re.sub(r"<!--.*?-->", "", html, flags=re.S)
        result.update(re.findall(r'\b(?:id|name)=["\']([^"\']+)["\']', html))
    return result
