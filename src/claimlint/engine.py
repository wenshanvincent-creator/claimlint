from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .checks import agent_commands, cli_flags, config_env, examples, links, signatures, symbols
from .cli_introspect import runtime_commands, static_commands
from .code_index import build_index
from .config import Config, load_config
from .docs_parser import active, parse_document
from .model import Coverage, ScanResult


@dataclass
class Options:
    select: set[str] | None = None
    run_examples: bool = False
    introspect_cli: bool = False
    timeout: float = 10


def scan(root: Path, options: Options | None = None, config: Config | None = None) -> ScanResult:
    options = options or Options()
    config = config or load_config(root)
    selected = options.select if options.select is not None else config.select
    documents = config.documents()
    claims = [claim for path in documents for claim in parse_document(path, config.root)]
    index = build_index(config)
    coverage = {key: Coverage() for key in sorted(selected)}
    findings = []
    for key, stats in coverage.items():
        current = active(claims, key)
        for problem in index.problems:
            stats.skip(problem)
        if key == "DP001":
            commands = (
                runtime_commands(config, options.timeout)
                if options.introspect_cli
                else static_commands(config, index)
            )
            for name, command in commands.items():
                if not command.complete:
                    stats.skip(f"{name}: {command.reason}")
            findings.extend(cli_flags.check(current, commands, stats))
        elif key == "DP002":
            findings.extend(symbols.check(current, index, stats))
        elif key == "DP003":
            findings.extend(signatures.check(current, index, stats))
        elif key == "DP004":
            if options.run_examples:
                findings.extend(examples.check(current, config.root, stats, options.timeout))
            else:
                stats.skip("Example execution is disabled; enable --run-examples for trusted code")
        elif key == "DP005":
            findings.extend(config_env.check(current, index, stats))
        elif key == "DP006":
            findings.extend(links.check(current, config.root, stats))
        elif key == "DP007":
            findings.extend(agent_commands.check(current, config, stats))
    unique = {(f.id, f.doc_line): f for f in findings}
    return ScanResult(
        sorted(unique.values(), key=lambda f: (f.doc_file, f.doc_line, f.check, f.message)),
        coverage,
        [p.relative_to(config.root).as_posix() for p in documents],
    )
