from __future__ import annotations

import ast
import inspect
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config


def dotted(node: ast.AST | None) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = dotted(node.value)
        return f"{prefix}.{node.attr}" if prefix else ""
    return ""


@dataclass
class Symbol:
    name: str
    file: str
    line: int
    kind: str
    signature: inspect.Signature | None = None
    fields: set[str] = field(default_factory=set)
    settings: bool = False

    @property
    def ref(self) -> str:
        return f"{self.file}:{self.line}"


@dataclass
class CodeIndex:
    root: Path
    symbols: dict[str, Symbol] = field(default_factory=dict)
    modules: dict[str, tuple[str, ast.Module]] = field(default_factory=dict)
    aliases: dict[str, str] = field(default_factory=dict)
    dynamic: set[str] = field(default_factory=set)
    env: dict[str, str] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)

    @property
    def roots(self) -> set[str]:
        return {name.split(".")[0] for name in self.modules}

    def canonical(self, name: str) -> str | None:
        seen: set[str] = set()
        while name not in seen:
            seen.add(name)
            if name in self.symbols:
                return name
            parts = name.split(".")
            for n in range(len(parts), 0, -1):
                prefix = ".".join(parts[:n])
                if prefix in self.aliases:
                    name = ".".join([self.aliases[prefix], *parts[n:]])
                    break
            else:
                return name
        return None

    def resolve(self, name: str) -> Symbol | None:
        return self.symbols.get(self.canonical(name))

    def uncertain(self, name: str) -> bool:
        canonical = self.canonical(name)
        if canonical is None:
            return True
        return any(
            value == module or value.startswith(module + ".")
            for value in {name, canonical}
            for module in self.dynamic
        )


def signature(
    node: ast.FunctionDef | ast.AsyncFunctionDef, drop_first: bool = False
) -> inspect.Signature:
    args = node.args
    params = []
    positional = args.posonlyargs + args.args
    required = len(positional) - len(args.defaults)
    for i, arg in enumerate(positional):
        kind = (
            inspect.Parameter.POSITIONAL_ONLY
            if i < len(args.posonlyargs)
            else inspect.Parameter.POSITIONAL_OR_KEYWORD
        )
        default = inspect.Parameter.empty if i < required else "..."
        params.append(inspect.Parameter(arg.arg, kind, default=default))
    if drop_first and params:
        params.pop(0)
    if args.vararg:
        params.append(inspect.Parameter(args.vararg.arg, inspect.Parameter.VAR_POSITIONAL))
    for arg, default_node in zip(args.kwonlyargs, args.kw_defaults, strict=True):
        default = inspect.Parameter.empty if default_node is None else "..."
        params.append(inspect.Parameter(arg.arg, inspect.Parameter.KEYWORD_ONLY, default=default))
    if args.kwarg:
        params.append(inspect.Parameter(args.kwarg.arg, inspect.Parameter.VAR_KEYWORD))
    return inspect.Signature(params)


def _imports(tree: ast.Module, module: str, package: bool) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name.split(".")[0]] = (
                    item.name if item.asname else item.name.split(".")[0]
                )
        elif isinstance(node, ast.ImportFrom):
            prefix = node.module or ""
            if node.level:
                parent = module.split(".") if package else module.split(".")[:-1]
                parent = parent[: len(parent) - node.level + 1]
                prefix = ".".join([*parent, *([prefix] if prefix else [])])
            for item in node.names:
                aliases[item.asname or item.name] = f"{prefix}.{item.name}"
    return aliases


def build_index(config: Config) -> CodeIndex:
    index = CodeIndex(config.root)
    roots = [config.root / r for r in config.source_roots]
    if not roots:
        roots = [config.root / "src"] if (config.root / "src").is_dir() else [config.root]
    files: dict[Path, Path] = {}
    for root in roots:
        for path in root.rglob("*.py"):
            relative = path.relative_to(root)
            if not config.ignored(path) and not any(
                p.startswith(".") or p in {"tests", "test", "examples", "docs"}
                for p in relative.parts[:-1]
            ):
                files[path] = root
    # Console scripts sometimes live beside, rather than inside, src/.
    for path in config.root.glob("*.py"):
        if not config.ignored(path):
            files[path] = config.root
    for path, root in sorted(files.items()):
        parts = list(path.relative_to(root).with_suffix("").parts)
        package = parts[-1] == "__init__"
        if package:
            parts.pop()
        module = ".".join(parts)
        if not module:
            continue
        ref = path.relative_to(config.root).as_posix()
        try:
            tree = ast.parse(path.read_bytes(), filename=ref)
        except SyntaxError as exc:
            index.dynamic.add(module)
            index.problems.append(f"{ref}:{exc.lineno}: cannot parse source: {exc.msg}")
            continue
        index.modules[module] = (ref, tree)
        # Namespace packages are real modules even without an __init__.py.
        for n in range(1, len(parts) + 1):
            name = ".".join(parts[:n])
            index.symbols.setdefault(name, Symbol(name, ref, 1, "module"))
        imports = _imports(tree, module, package)
        index.aliases.update({f"{module}.{name}": target for name, target in imports.items()})
        for node in tree.body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                decorators = [
                    dotted(d.func if isinstance(d, ast.Call) else d) for d in node.decorator_list
                ]
                sig = signature(node) if not decorators else None
                name = f"{module}.{node.name}"
                index.symbols[name] = Symbol(name, ref, node.lineno, "function", sig)
                if node.name == "__getattr__":
                    index.dynamic.add(module)
            elif isinstance(node, ast.ClassDef):
                name = f"{module}.{node.name}"
                bases = [imports.get(dotted(b), dotted(b)) for b in node.bases]
                settings = any(
                    b
                    in {
                        "pydantic.BaseModel",
                        "pydantic.BaseSettings",
                        "pydantic_settings.BaseSettings",
                    }
                    for b in bases
                )
                decorators = [
                    imports.get(
                        dotted(d.func if isinstance(d, ast.Call) else d),
                        dotted(d.func if isinstance(d, ast.Call) else d),
                    )
                    for d in node.decorator_list
                ]
                dataclass = "dataclasses.dataclass" in decorators
                fields = {
                    n.target.id
                    for n in node.body
                    if isinstance(n, ast.AnnAssign)
                    and isinstance(n.target, ast.Name)
                    and not n.target.id.startswith("_")
                    and not dotted(n.annotation).endswith("ClassVar")
                }
                init = next(
                    (
                        n
                        for n in node.body
                        if isinstance(n, ast.FunctionDef) and n.name == "__init__"
                    ),
                    None,
                )
                sig = signature(init, True) if init and not init.decorator_list else None
                index.symbols[name] = Symbol(name, ref, node.lineno, "class", sig, fields, settings)
                if node.bases:
                    # Inherited attributes may be real even when the subclass has no local binding.
                    index.dynamic.add(name)
                for child in node.body:
                    if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                        member = f"{name}.{child.name}"
                        # Unbound methods need an explicit instance; class/static methods differ.
                        decs = [dotted(d) for d in child.decorator_list]
                        member_sig = (
                            signature(child, "classmethod" in decs)
                            if all(d in {"staticmethod", "classmethod"} for d in decs)
                            else None
                        )
                        index.symbols[member] = Symbol(
                            member, ref, child.lineno, "method", member_sig
                        )
                    elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
                        member = f"{name}.{child.target.id}"
                        index.symbols[member] = Symbol(member, ref, child.lineno, "field")
                if dataclass and not init:
                    # Inheritance, kw_only, InitVar and field(init=False) need runtime semantics.
                    index.symbols[name].signature = None
            elif isinstance(node, ast.Assign | ast.AnnAssign):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name):
                        name = f"{module}.{target.id}"
                        index.symbols[name] = Symbol(name, ref, node.lineno, "variable")
        # Conditional bindings and star imports leave an incomplete namespace.
        for node in tree.body:
            if isinstance(node, ast.If | ast.Try | ast.For | ast.With):
                index.dynamic.add(module)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and any(n.name == "*" for n in node.names):
                index.dynamic.add(module)
            if isinstance(node, ast.Call):
                call = dotted(node.func)
                first, *tail = call.split(".")
                call = ".".join([imports.get(first, first), *tail])
                if call in {"os.getenv", "os.environ.get", "os.environ.setdefault"} and node.args:
                    if isinstance(node.args[0], ast.Constant) and isinstance(
                        node.args[0].value, str
                    ):
                        index.env[node.args[0].value] = f"{ref}:{node.lineno}"
            elif isinstance(node, ast.Subscript):
                name = dotted(node.value)
                first, *tail = name.split(".")
                name = ".".join([imports.get(first, first), *tail])
                if name == "os.environ" and isinstance(node.slice, ast.Constant):
                    if isinstance(node.slice.value, str) and isinstance(node.ctx, ast.Load):
                        index.env[node.slice.value] = f"{ref}:{node.lineno}"
    return index
