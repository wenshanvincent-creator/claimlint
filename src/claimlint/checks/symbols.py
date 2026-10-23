from __future__ import annotations

import ast
import difflib
import re
from dataclasses import replace

from ..code_index import CodeIndex
from ..model import Claim, Coverage, Finding
from .common import bindings, external_alias, owned, python_tree, resolve_name


def check(claims: list[Claim], index: CodeIndex, coverage: Coverage) -> list[Finding]:
    findings = []
    references: list[tuple[Claim, str]] = []
    for claim in claims:
        if claim.kind == "inline":
            references.extend(
                (claim, value)
                for value in re.findall(r"(?<![\w/])\b[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+", claim.text)
            )
        tree = python_tree(claim)
        if tree is None:
            continue
        names = bindings(tree)
        nodes = []
        for statement in tree.body:
            if not isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                nodes.extend(ast.walk(statement))
        for node in nodes:
            location = (
                replace(claim, line=claim.line + node.lineno - 1)
                if hasattr(node, "lineno")
                else claim
            )
            if isinstance(node, ast.ImportFrom) and node.module:
                for item in node.names:
                    if item.name != "*":
                        references.append((location, f"{node.module}.{item.name}"))
            elif isinstance(node, ast.Import):
                references.extend((location, item.name) for item in node.names)
            elif isinstance(node, ast.Call):
                references.append((location, resolve_name(node.func, names)))
    for claim, name in references:
        if not owned(name, index):
            continue
        if index.resolve(name):
            coverage.checked += 1
        elif index.uncertain(name) or external_alias(name, index):
            coverage.skip(f"{name}: dynamic, inherited or external namespace", claim)
        else:
            coverage.checked += 1
            parent = name.rpartition(".")[0]
            symbol = index.resolve(parent)
            close = difflib.get_close_matches(
                name, sorted(index.symbols | index.aliases), n=1, cutoff=0.65
            )
            findings.append(
                Finding(
                    "DP002",
                    "error",
                    claim.file,
                    claim.line,
                    f"Project symbol {name!r} does not exist",
                    {"claim": name, "namespace": parent},
                    symbol.ref if symbol else None,
                    f"Did you mean {close[0]}?" if close else None,
                )
            )
    return findings
