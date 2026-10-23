from __future__ import annotations

import ast

from ..code_index import CodeIndex
from ..model import Claim, Coverage, Finding
from .common import bindings, owned, python_tree, resolve_name


def check(claims: list[Claim], index: CodeIndex, coverage: Coverage) -> list[Finding]:
    findings = []
    for claim in claims:
        tree = python_tree(claim)
        if tree is None:
            if claim.kind == "code" and claim.language in {"python", "py", "python3"}:
                coverage.skip("Example is not a complete Python program", claim)
            continue
        names = bindings(tree)
        # Local scopes can shadow imports; only inspect top-level executable statements.
        nodes = []
        for statement in tree.body:
            if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                continue
            nodes.extend(ast.walk(statement))
        for node in nodes:
            if not isinstance(node, ast.Call):
                continue
            name = resolve_name(node.func, names)
            if not owned(name, index):
                continue
            symbol = index.resolve(name)
            if symbol is None:
                continue  # DP002 owns unresolved names.
            if symbol.signature is None:
                coverage.skip(
                    f"{name}: signature is dynamic, decorated, generated or unavailable", claim
                )
                continue
            if any(isinstance(arg, ast.Starred) for arg in node.args) or any(
                keyword.arg is None for keyword in node.keywords
            ):
                coverage.skip(f"{name}: unpacked arguments cannot be bound statically", claim)
                continue
            coverage.checked += 1
            try:
                symbol.signature.bind(
                    *([None] * len(node.args)), **{k.arg: None for k in node.keywords}
                )
            except TypeError as exc:
                findings.append(
                    Finding(
                        "DP003",
                        "error",
                        claim.file,
                        claim.line + node.lineno - 1,
                        f"Call to {name}{symbol.signature} does not bind: {exc}",
                        {
                            "claim": ast.unparse(node),
                            "signature": str(symbol.signature),
                            "error": str(exc),
                        },
                        symbol.ref,
                    )
                )
    return findings
