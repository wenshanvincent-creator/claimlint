# claimlint

Catch checkable documentation drift before a maintainer or coding agent follows it.

claimlint compares Markdown examples and agent instructions with Python source and project
metadata. Findings include the documentation line, source reference, and the concrete claim
that failed. Detection uses no model and makes no network requests.

Requires Python 3.10 or newer and a project with a `pyproject.toml`.

## Install and run

Install the release:

```sh
python -m pip install claimlint==0.1.0
claimlint check .
```

Or install from a source checkout:

```sh
python -m pip install .
claimlint check .
claimlint --version
claimlint check . --format json
claimlint check . --select DP002,DP003,DP006 --min-severity error
```

The distribution name is `claimlint`. The original working name, docproof, belongs to an existing project.
See the [usefulness assessment](docs/assessment.md) for the comparison and design choices.

## What it checks

| Check | Evidence | Scope |
| --- | --- | --- |
| DP001 | argparse definitions or opt-in help output | Documented options and subcommands for project console scripts |
| DP002 | AST symbol table and local re-exports | Project-owned dotted references and imports in Python examples |
| DP003 | AST function/method signatures | Bound arguments of calls in complete Python examples |
| DP004 | Subprocess exit status and traceback | Opt-in execution of Python fences, one fresh process per block |
| DP005 | Literal environment reads and settings fields | Environment names and pydantic settings documentation coverage |
| DP006 | Filesystem and Markdown heading IDs | Relative links, images, reference links, and anchors |
| DP007 | Project metadata, Makefile, filesystem | Commands and file/test paths in AGENTS.md and CLAUDE.md |

Unknown flags, symbols, invalid calls, missing agent paths, and broken links are errors.
Potentially stale environment names are warnings. Undocumented options, environment variables,
settings fields, and undeclared agent tools are notes. Notes do not fail the default gate.
`--min-severity note` makes documentation coverage a gate too.

A report names how many documents it read and how many claims each check examined or skipped.
Dynamic namespaces, decorators, unpacked arguments, unsupported CLI frameworks, and external
names are skipped where they prevent a reliable decision. A clean report applies to those
checks and documents only. See [limits](docs/limits.md).

## Example finding

```text
README.md:12: error DP003 Call to demo.render(text, *, width='...') does not bind: got an unexpected keyword argument 'columns'
  source: src/demo/__init__.py:4
  evidence: {"claim": "render('hello', columns=80)", "signature": "(text, *, width='...')"}
```

This is illustrative output. The planted example repositories and their expected findings
are under [tests/fixtures](tests/fixtures/).

The parser can also be used directly:

```python
from claimlint.docs_parser import parse_text

claims = parse_text("# Usage\n\nCall `demo.render()`.\n", "README.md")
assert claims[0].kind == "heading"
assert claims[1].line == 3
```

## Configuration

```toml
[tool.claimlint]
docs = ["README.md", "docs/**/*.md"]
agent_files = ["**/AGENTS.md", "**/CLAUDE.md"]
ignore_paths = ["docs/archive/**"]
select = ["DP001", "DP002", "DP003", "DP005", "DP006", "DP007"]
ignore = []
# Optional for unconventional layouts; defaults to src/ when present, otherwise the root.
source_roots = ["src"]

[tool.claimlint.entry_points]
# Override or add a console script's module:function target.
# demo = "demo.cli:main"
```

Configuration belongs in the checked project's pyproject file. Document globs and source roots
must stay inside that project. By default, README.md, docs Markdown, and nested agent files
are scanned. Virtual environments, build output, Git internals, and node_modules are excluded.
Tests, examples, and docs are excluded from the source index.

Put an HTML comment directly before the relevant inline claim, paragraph, link, or fence:

````markdown
<!-- claimlint: ignore DP001,DP003 -->
```python
# An intentionally incomplete example.
```
````

`<!-- claimlint: skip -->` excludes the next claim or block from all checks, including
execution. The original `docproof:` spelling is accepted for the supplied spec's compatibility.

## Baselines

```sh
claimlint baseline .
claimlint baseline . --output .claimlint-baseline.json --select DP001,DP002,DP003,DP005,DP006,DP007
claimlint check . --baseline .claimlint-baseline.json
```

The baseline stores finding identities rather than line numbers, so adding paragraphs does
not resurrect an existing finding. Changing a failing claim or its error creates a new identity.
Paths passed to `--baseline`, `--output`, and `--summary` are relative to the shell's current directory.

## Trusted execution

```sh
claimlint check . --introspect-cli --timeout 5
claimlint check . --run-examples --timeout 5
```

Both flags execute project code with your Python interpreter and installed dependencies.
Use them only on trusted projects. A temporary example working directory and a timeout are
**not an operating-system sandbox**: examples still have your filesystem, credentials,
network access, and ability to start child processes. Use an isolated CI runner when needed.
The static default never imports the checked project.

Runtime help traversal supports argparse-style subcommands and Click-style Commands sections.
It is bounded to five levels and fifty invocations per entry point. Required application
initialization or custom help formatting may leave a subtree unverified.

## Optional Codex fixes

```sh
claimlint fix .
claimlint fix . --codex codex --timeout 120 --select DP002,DP003,DP006
claimlint fix . --apply
```

Requires an authenticated Codex CLI. This optional step sends the affected document and
finding evidence to your configured Codex service and may consume model usage. It runs in
a temporary directory with a read-only sandbox request. The backend returns a diff; the
validator accepts only the requested document, exact patch context, no new suppression,
the original finding gone, and no new findings across the selected static checks.

Dry runs print the validated diff. Only `--apply` writes documentation. Validation uses a
temporary project copy and never executes model-edited examples. Notes are not auto-fixed.
Live backend availability depends on your Codex installation; rejection and timeout are surfaced.

## GitHub Actions

The root [composite action](action.yml) installs claimlint and emits line annotations plus
a job summary. It requires no model API key and runs static checks by default:

```yaml
jobs:
  docs:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v6
      - uses: wenshanvincent-creator/claimlint@v0.1.0
        with:
          path: .
          min-severity: warning
```

For reproducible action use, replace the version tag with its reviewed immutable commit.
The [CI workflow](.github/workflows/ci.yml) tests supported Python
versions, lints, dogfoods static and runtime checks, and builds the wheel and source archive.
The action does not post PR comments or open PRs; job summaries and annotations require
only read permissions and work on fork pull requests.

To produce a summary outside Actions:

```sh
claimlint check . --format github --summary claimlint-summary.md
```

Exit codes: **0** no finding at the chosen threshold; **1** findings (or rejected fixes);
**2** invalid usage/configuration or an operational error.

## Development

```sh
python -m pip install -e ".[dev]"
python -m pytest
ruff check .
claimlint check .
python -m build
```

See [CONTRIBUTING](CONTRIBUTING.md), the [changelog](CHANGELOG.md), and [release steps](RELEASING.md).
MIT licensed.
