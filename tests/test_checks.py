import json

import pytest

from claimlint.engine import Options, scan
from claimlint.model import SEVERITIES


@pytest.mark.parametrize("check", ["DP001", "DP002", "DP003", "DP005", "DP006", "DP007"])
def test_planted_drift_matches_receipts(project, check):
    root = project()
    expected = json.loads((root / "expected.json").read_text())
    expected = sorted(row for row in expected if row[0] == check)
    result = scan(root, Options(select={check}))
    actual = sorted(
        [f.check, f.severity, f.doc_file, f.doc_line, f.evidence["claim"]]
        for f in result.findings
        if SEVERITIES[f.severity] >= SEVERITIES["warning"]
    )
    assert actual == expected


def test_clean_fixture_has_no_findings_and_can_execute(project):
    result = scan(project("clean"), Options(run_examples=True, introspect_cli=True))
    assert result.findings == []
    assert result.coverage["DP004"].checked == 1


def test_default_scan_never_imports_project(project):
    root = project("clean")
    init = root / "src/demo/__init__.py"
    init.write_text("raise RuntimeError('project was imported')\n" + init.read_text())
    assert not scan(root).findings


def test_signature_kinds_and_unpacked_arguments(project):
    root = project()
    (root / "README.md").write_text("""```python
from demo.api import positional
positional(1, 2, mode="x")
positional(value=1, required=2, mode="x")
positional(1, mode="x")
positional(1, 2, 3, mode="x")
positional(1, 2, required=3, mode="x")
positional(*unknown)
```
""")
    result = scan(root, Options(select={"DP003"}))
    assert [f.doc_line for f in result.findings] == [4, 5, 6, 7]
    assert len(result.coverage["DP003"].skipped) == 1


def test_dynamic_namespace_and_external_reexports_are_not_dead_symbols(project):
    root = project()
    (root / "src/demo/dynamic.py").write_text("""def __getattr__(name):
    return object()
""")
    with (root / "src/demo/__init__.py").open("a") as stream:
        stream.write("\nfrom pathlib import Path\n")
    (root / "README.md").write_text("""`demo.dynamic.anything` and `demo.Path`.
```python
import demo
from demo import render as render_alias
render_alias("hello")
```
""")
    result = scan(root, Options(select={"DP002", "DP003"}))
    assert result.findings == []
    assert result.coverage["DP002"].skipped


def test_cli_flags_belong_to_each_subcommand(project):
    result = scan(project(), Options(select={"DP001"}))
    errors = [f for f in result.findings if f.severity == "error"]
    assert [f.evidence["command"] for f in errors] == [["demo", "build"], ["demo", "serve"]]


def test_dynamic_argparse_is_not_treated_as_complete(project):
    root = project()
    cli = root / "src/demo/cli.py"
    cli.write_text(
        cli.read_text().replace(
            'parser.add_argument("--verbose", action="store_true")',
            "for option in options:\n        parser.add_argument(option)",
        )
    )
    result = scan(root, Options(select={"DP001"}))
    assert not [f for f in result.findings if f.severity == "error"]
    assert result.coverage["DP001"].skipped


def test_example_execution_is_opt_in_and_classifies_errors(project):
    root = project("clean")
    (root / "README.md").write_text("""```python
raise TypeError("wrong call")
```
<!-- claimlint: skip -->
```python
raise RuntimeError("must not run")
```
""")
    assert not scan(root, Options(select={"DP004"})).findings
    result = scan(root, Options(select={"DP004"}, run_examples=True))
    assert len(result.findings) == 1
    assert result.findings[0].evidence["category"] == "TypeError"


def test_example_timeout(project):
    root = project("clean")
    (root / "README.md").write_text("```python\nwhile True: pass\n```\n")
    result = scan(root, Options(select={"DP004"}, run_examples=True, timeout=0.2))
    assert result.findings[0].evidence["category"] == "Timeout"


def test_parent_flags_are_not_accepted_after_subcommand(project):
    root = project()
    (root / "README.md").write_text("```sh\ndemo build --verbose\n```\n")
    result = scan(root, Options(select={"DP001"}))
    assert [f.evidence["claim"] for f in result.findings if f.severity == "error"] == ["--verbose"]


def test_pinned_upstream_agent_commands_do_not_claim_external_tools_are_project_scripts():
    from pathlib import Path

    root = Path(__file__).parent / "fixtures/upstream-agent"
    result = scan(root)
    assert not result.findings
