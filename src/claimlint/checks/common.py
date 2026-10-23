from __future__ import annotations

import ast
import re
import shlex
from dataclasses import replace

from ..code_index import CodeIndex, dotted
from ..model import Claim

SHELL_LANGUAGES = {
    "",
    "sh",
    "shell",
    "bash",
    "console",
    "shell-session",
    "zsh",
    "powershell",
    "ps1",
}


def shell_lines(claim: Claim):
    if claim.kind not in {"inline", "code"} or (
        claim.kind == "code" and claim.language not in SHELL_LANGUAGES
    ):
        return
    pending = ""
    first = claim.line
    for offset, line in enumerate(claim.text.splitlines()):
        if not pending:
            first = claim.line + offset
        line = line.strip()
        if line.endswith(("\\", "`")):
            pending += line[:-1] + " "
            continue
        line = pending + line
        pending = ""
        line = re.sub(r"^(?:\$ |PS> |> )", "", line)
        try:
            lexer = shlex.shlex(line, posix=True, punctuation_chars=";&|")
            lexer.whitespace_split = True
            lexer.commenters = "#"
            parts = list(lexer)
        except ValueError:
            continue
        current: list[str] = []
        for token in parts + [";"]:
            if token in {";", "&&", "||", "|"}:
                if current:
                    yield replace(claim, line=first, text=line), current
                current = []
            else:
                current.append(token)


def unwrap(tokens: list[str]) -> list[str]:
    tokens = tokens.copy()
    while tokens and re.match(r"^[A-Za-z_]\w*=", tokens[0]):
        tokens.pop(0)
    if tokens[:2] == ["uv", "run"]:
        tokens = tokens[2:]
    elif tokens[:2] == ["poetry", "run"]:
        tokens = tokens[2:]
    elif tokens[:1] in [["uvx"], ["pipx"]]:
        tokens = tokens[1:]
        if tokens[:1] == ["run"]:
            tokens = tokens[1:]
    return tokens


def python_tree(claim: Claim) -> ast.Module | None:
    if claim.kind != "code" or claim.language not in {"python", "py", "python3"}:
        return None
    try:
        return ast.parse(claim.text)
    except SyntaxError:
        return None


def bindings(tree: ast.Module) -> dict[str, str]:
    names = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for item in node.names:
                names[item.asname or item.name.split(".")[0]] = (
                    item.name if item.asname else item.name.split(".")[0]
                )
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            for item in node.names:
                if item.name != "*":
                    names[item.asname or item.name] = f"{node.module}.{item.name}"
        elif isinstance(node, ast.Assign | ast.AnnAssign | ast.FunctionDef | ast.ClassDef):
            targets = (
                node.targets
                if isinstance(node, ast.Assign)
                else [node.target]
                if isinstance(node, ast.AnnAssign)
                else []
            )
            for target in targets:
                if isinstance(target, ast.Name):
                    names[target.id] = ""
            if isinstance(node, ast.FunctionDef | ast.ClassDef):
                names[node.name] = ""
    return names


def resolve_name(node: ast.AST, names: dict[str, str]) -> str:
    value = dotted(node)
    root, *tail = value.split(".")
    if root in names and not names[root]:
        return ""
    return ".".join([names.get(root, root), *tail])


def owned(name: str, index: CodeIndex) -> bool:
    return name.split(".")[0] in index.roots


def external_alias(name: str, index: CodeIndex) -> bool:
    canonical = index.canonical(name)
    return canonical is None or not owned(canonical, index)
