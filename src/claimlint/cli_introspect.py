"""Read argparse trees statically; executing --help is a separate, opt-in mode."""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field

from .code_index import CodeIndex, dotted
from .config import Config


@dataclass
class Command:
    name: str
    ref: str
    flags: set[str] = field(default_factory=lambda: {"-h", "--help"})
    values: set[str] = field(default_factory=set)
    children: dict[str, Command] = field(default_factory=dict)
    complete: bool = True
    reason: str = ""


def _literal(node: ast.AST | None, default=None):
    try:
        return ast.literal_eval(node) if node is not None else default
    except (ValueError, TypeError):
        return default


def static_commands(config: Config, index: CodeIndex) -> dict[str, Command]:
    return {
        name: _static_command(name, entry, index) for name, entry in config.entry_points.items()
    }


def _static_command(name: str, entry: str, index: CodeIndex) -> Command:
    module, _, func = entry.partition(":")
    command = Command(
        name,
        "pyproject.toml",
        complete=False,
        reason="Entry point source is unavailable or is not static argparse",
    )
    if module not in index.modules:
        return command
    file, tree = index.modules[module]
    # Restrict to the entry point and local functions it calls, excluding unrelated parsers.
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    reachable = {func.split("[")[0].strip()}
    pending = list(reachable)
    while pending:
        current = functions.get(pending.pop())
        if current:
            for node in ast.walk(current):
                if isinstance(node, ast.Call) and dotted(node.func) in functions:
                    target = dotted(node.func)
                    if target not in reachable:
                        reachable.add(target)
                        pending.append(target)
    statements = [n for n in tree.body if not isinstance(n, ast.FunctionDef | ast.ClassDef)]
    for fname in functions:
        if fname in reachable:
            statements.extend(functions[fname].body)
    parsers: dict[str, Command] = {}
    groups: dict[str, Command] = {}
    candidates: list[Command] = []
    incomplete = False

    def visit(nodes: list[ast.stmt], conditional: bool = False) -> None:
        nonlocal incomplete
        for stmt in nodes:
            call = stmt.value if isinstance(stmt, ast.Assign | ast.Expr) else None
            target = dotted(stmt.targets[0]) if isinstance(stmt, ast.Assign) else ""
            if isinstance(call, ast.Call):
                method = dotted(call.func)
                owner, _, operation = method.rpartition(".")
                kwargs = {k.arg: k.value for k in call.keywords}
                if operation == "ArgumentParser":
                    parser = Command(name, f"{file}:{stmt.lineno}")
                    if _literal(kwargs.get("add_help"), True) is False:
                        parser.flags.clear()
                    for parent in getattr(kwargs.get("parents"), "elts", []):
                        inherited = parsers.get(dotted(parent))
                        if inherited:
                            parser.flags.update(inherited.flags)
                            parser.values.update(inherited.values)
                        else:
                            incomplete = True
                    parsers[target] = parser
                    if _literal(kwargs.get("add_help"), True):
                        candidates.append(parser)
                elif operation == "add_subparsers" and owner in parsers:
                    groups[target] = parsers[owner]
                elif operation == "add_parser" and owner in groups:
                    label = _literal(call.args[0]) if call.args else None
                    if not isinstance(label, str) or conditional:
                        incomplete = True
                        continue
                    child = Command(label, f"{file}:{stmt.lineno}")
                    for parent in getattr(kwargs.get("parents"), "elts", []):
                        inherited = parsers.get(dotted(parent))
                        if inherited:
                            child.flags.update(inherited.flags)
                            child.values.update(inherited.values)
                        else:
                            incomplete = True
                    groups[owner].children[label] = child
                    for alias in _literal(kwargs.get("aliases"), []):
                        groups[owner].children[alias] = child
                    parsers[target] = child
                elif operation in {"add_argument_group", "add_mutually_exclusive_group"}:
                    if owner in parsers:
                        parsers[target] = parsers[owner]
                elif operation == "add_argument" and owner in parsers:
                    options = [_literal(a) for a in call.args]
                    if conditional or any(not isinstance(a, str) for a in options):
                        incomplete = True
                    else:
                        flags = {a for a in options if a.startswith("-")}
                        parsers[owner].flags.update(flags)
                        action = _literal(kwargs.get("action"), "store")
                        if action not in {
                            "store_true",
                            "store_false",
                            "count",
                            "help",
                            "version",
                            "store_const",
                            "append_const",
                        }:
                            if _literal(kwargs.get("nargs"), 1) != 0:
                                parsers[owner].values.update(flags)
                elif operation in {"parse_known_args", "parse_known_intermixed_args"}:
                    incomplete = True
                elif any(dotted(arg) in parsers for arg in call.args):
                    # A helper can add arbitrary flags. Refuse to claim completeness.
                    incomplete = True
            if isinstance(stmt, ast.If | ast.For | ast.While | ast.With | ast.Try):
                visit(getattr(stmt, "body", []), True)
                visit(getattr(stmt, "orelse", []), True)
                for handler in getattr(stmt, "handlers", []):
                    visit(handler.body, True)

    visit(statements)
    child_ids = {id(c) for p in parsers.values() for c in p.children.values()}
    candidates = [p for p in candidates if id(p) not in child_ids]
    if len(candidates) == 1:
        command = candidates[0]
        command.complete = not incomplete
        command.reason = (
            "Parser is modified dynamically or accepts unknown arguments" if incomplete else ""
        )
    return command


HELP_RUNNER = """import importlib,sys
module, target = sys.argv[1].split(':', 1)
obj = importlib.import_module(module)
for part in target.split('.'):
    obj = getattr(obj, part)
sys.argv = [sys.argv[1], *sys.argv[2:]]
raise SystemExit(obj())
"""


def runtime_commands(config: Config, timeout: float) -> dict[str, Command]:
    result = {}
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(config.root / "src"), str(config.root), env.get("PYTHONPATH", "")]
    )
    for name, entry in config.entry_points.items():
        result[name] = _runtime_command(name, entry, config, env, timeout)
    return result


def _runtime_command(
    name: str, entry: str, config: Config, env: dict[str, str], timeout: float
) -> Command:
    count = 0

    def collect(args: list[str]) -> Command:
        nonlocal count
        count += 1
        cmd = Command(args[-1] if args else name, "pyproject.toml")
        if len(args) > 5 or count > 50:
            cmd.complete = False
            cmd.reason = "Help traversal limit reached"
            return cmd
        try:
            proc = subprocess.run(
                [sys.executable, "-c", HELP_RUNNER, entry, *args, "--help"],
                cwd=config.root,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            cmd.complete = False
            cmd.reason = f"--help timed out after {timeout:g}s"
            return cmd
        if proc.returncode:
            cmd.complete = False
            cmd.reason = f"--help exited {proc.returncode}: {proc.stderr[-500:]}"
            return cmd
        help_text = proc.stdout + proc.stderr
        cmd.flags = set(re.findall(r"(?<![\w-])--?[a-zA-Z][\w-]*", help_text))
        # Only options declaring a metavar consume a following token.
        cmd.values = set(re.findall(r"(--?[\w-]+)(?:[ =])(?:[A-Z][A-Z_]+|\{[^}]+\})", help_text))
        # argparse brace groups and Click/Typer Commands sections.
        names: set[str] = set()
        for line in help_text.splitlines():
            if match := re.match(r"\s{2,}\{([\w, -]+)\}\s*$", line):
                names.update(match[1].split(","))
        section = False
        for line in help_text.splitlines():
            if re.match(r"\s*Commands:\s*$", line):
                section = True
            elif section:
                match = re.match(r"\s{2,}([\w-]+)\s{2,}", line)
                if match:
                    names.add(match[1])
                elif line and not line[0].isspace():
                    section = False
        for sub in sorted(names):
            cmd.children[sub] = collect([*args, sub])
        return cmd

    return collect([])
