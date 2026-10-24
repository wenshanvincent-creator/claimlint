"""Read renderer configuration as data, without importing docs plugins or conf.py."""

from __future__ import annotations

import ast
import posixpath
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urljoin

import yaml
from markdown_it import MarkdownIt

from .docs_parser import myst_labels


def _names(values: list) -> set[str]:
    return {name for value in values for name in (value if isinstance(value, dict) else [value])}


@dataclass
class DocContext:
    root: Path
    docs_dir: Path | None = None
    attribute_ids: bool = False
    mkdocstrings: bool = False
    templates: bool = False
    directory_urls: bool = True
    routes: dict[str, Path] = field(default_factory=dict)
    _myst: dict[Path, bool] = field(default_factory=dict)
    _labels: dict[Path, set[str]] = field(default_factory=dict)

    @classmethod
    def load(cls, root: Path) -> DocContext:
        context = cls(root)
        config = next(
            (root / name for name in ("mkdocs.yml", "mkdocs.yaml") if (root / name).is_file()), None
        )
        if config is None:
            return context
        # BaseLoader treats even !!python/name and !ENV as data, never constructors.
        data = yaml.load(config.read_text(encoding="utf-8-sig"), Loader=yaml.BaseLoader)
        if not isinstance(data, dict):
            raise ValueError(f"{config.name} must contain a mapping")
        docs_dir = (root / data.get("docs_dir", "docs")).resolve()
        if not docs_dir.is_relative_to(root):
            raise ValueError("MkDocs docs_dir must stay inside the project")
        context.docs_dir = docs_dir
        extensions = _names(data.get("markdown_extensions", []))
        plugins = _names(data.get("plugins", []))
        context.attribute_ids = bool(extensions & {"attr_list", "extra", "pymdownx.extra"})
        context.mkdocstrings = "mkdocstrings" in plugins
        context.templates = bool(data.get("hooks")) or "macros" in plugins
        context.directory_urls = data.get("use_directory_urls", "true").lower() == "true"
        for path in docs_dir.rglob("*.md"):
            context.routes[context.page_url(path).rstrip("/")] = path.resolve()
        return context

    def in_site(self, path: Path) -> bool:
        return self.docs_dir is not None and path.is_relative_to(self.docs_dir)

    def page_url(self, path: Path) -> str:
        relative = path.relative_to(self.docs_dir)
        if self.directory_urls:
            if relative.stem == "index":
                return "" if relative.parent == Path(".") else relative.parent.as_posix() + "/"
            return relative.with_suffix("").as_posix() + "/"
        return relative.with_suffix(".html").as_posix()

    def route(self, source: Path, url: str) -> Path | None:
        if not self.in_site(source):
            return None
        route = posixpath.normpath(urljoin(self.page_url(source), url)).rstrip("/")
        if route == ".":
            route = ""
        return self.routes.get(route)

    def myst_root(self, path: Path) -> Path | None:
        for parent in path.parents:
            if not parent.is_relative_to(self.root):
                break
            if parent not in self._myst:
                config = parent / "conf.py"
                enabled = False
                if config.is_file():
                    tree = ast.parse(config.read_text(encoding="utf-8-sig"))
                    for node in tree.body:
                        if isinstance(node, ast.Assign) and any(
                            isinstance(t, ast.Name) and t.id == "extensions" for t in node.targets
                        ):
                            enabled = any(
                                isinstance(n, ast.Constant) and n.value == "myst_parser"
                                for n in ast.walk(node.value)
                            )
                self._myst[parent] = enabled
            if self._myst[parent]:
                return parent
        return None

    def labels(self, source: Path) -> set[str]:
        docs_root = self.myst_root(source)
        if docs_root is None:
            return set()
        if docs_root not in self._labels:
            self._labels[docs_root] = {
                label
                for path in docs_root.rglob("*.md")
                for label in myst_labels(path.read_text(encoding="utf-8-sig"))
            }
        return self._labels[docs_root]

    def generated_anchors(self, target: Path, text: str) -> bool:
        if not self.in_site(target):
            return False
        # A directive/macro shown inside a code example does not generate a page.
        visible = "\n".join(
            "".join(child.content for child in token.children or [] if child.type == "text")
            for token in MarkdownIt("commonmark").parse(text)
            if token.type == "inline"
        )
        return bool(
            (self.mkdocstrings and re.search(r"(?m)^\s*:::\s+\S+", visible))
            or (self.templates and re.search(r"\{\{.+?\}\}", visible, re.S))
        )
