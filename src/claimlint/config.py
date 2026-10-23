from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

from .model import CHECKS

EXCLUDED = {".git", ".venv", "venv", "node_modules", "__pycache__", "build", "dist"}


def check_ids(values: list[str]) -> set[str]:
    result = set(values)
    unknown = result - CHECKS
    if unknown:
        raise ValueError(f"Unknown check IDs: {', '.join(sorted(unknown))}")
    return result


@dataclass
class Config:
    root: Path
    project: dict[str, Any]
    docs: list[str] = field(default_factory=lambda: ["README.md", "docs/**/*.md"])
    agent_files: list[str] = field(default_factory=lambda: ["**/AGENTS.md", "**/CLAUDE.md"])
    ignore_paths: list[str] = field(default_factory=list)
    select: set[str] = field(default_factory=lambda: CHECKS.copy())
    entry_points: dict[str, str] = field(default_factory=dict)
    source_roots: list[str] = field(default_factory=list)

    def ignored(self, path: Path) -> bool:
        relative = path.relative_to(self.root)
        return bool(EXCLUDED.intersection(relative.parts)) or any(
            fnmatch.fnmatchcase(relative.as_posix(), pattern) for pattern in self.ignore_paths
        )

    def documents(self) -> list[Path]:
        paths = {p for glob in self.docs + self.agent_files for p in self.root.glob(glob)}
        return sorted(p for p in paths if p.is_file() and not self.ignored(p))


def load_config(root: Path) -> Config:
    root = root.resolve()
    path = root / "pyproject.toml"
    if not path.is_file():
        raise ValueError(f"No pyproject.toml in {root}")
    data = tomllib.loads(path.read_text(encoding="utf-8-sig"))
    raw = data.get("tool", {}).get("claimlint", {})
    allowed = {
        "docs",
        "agent_files",
        "ignore_paths",
        "select",
        "ignore",
        "entry_points",
        "source_roots",
    }
    if extra := raw.keys() - allowed:
        raise ValueError(f"Unknown [tool.claimlint] keys: {', '.join(sorted(extra))}")
    for key in ("docs", "agent_files", "ignore_paths", "select", "ignore", "source_roots"):
        if key in raw and (
            not isinstance(raw[key], list) or not all(isinstance(v, str) for v in raw[key])
        ):
            raise ValueError(f"{key} must be an array of strings")
    overrides = raw.get("entry_points", {})
    if not isinstance(overrides, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in overrides.items()
    ):
        raise ValueError("entry_points must map command names to module:function strings")
    scripts = {**data.get("project", {}).get("scripts", {}), **overrides}
    config = Config(root, data, entry_points=scripts)
    for key in ("docs", "agent_files", "ignore_paths", "source_roots"):
        if key in raw:
            setattr(config, key, raw[key])
    for glob in config.docs + config.agent_files:
        if Path(glob).is_absolute() or ".." in Path(glob).parts:
            raise ValueError("Document globs must stay inside the project")
    for source in config.source_roots:
        if not (root / source).resolve().is_relative_to(root):
            raise ValueError("source_roots must stay inside the project")
    config.select = check_ids(raw.get("select", sorted(CHECKS))) - check_ids(raw.get("ignore", []))
    return config
