import json
import os
import subprocess
import sys

import pytest

from claimlint.baseline import apply_baseline, write_baseline
from claimlint.cli import main
from claimlint.engine import scan
from claimlint.model import Coverage, Finding, ScanResult
from claimlint.report import render


def test_exit_codes_and_json(project, capsys):
    root = project()
    assert main(["check", str(root), "--format", "json"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["findings"] and report["coverage"]
    assert main(["check", str(root), "--select", "UNKNOWN"]) == 2
    assert "Unknown check" in capsys.readouterr().err
    assert main(["check", str(root.parent)]) == 2


def test_baseline_survives_line_moves_but_not_new_errors(project, capsys):
    root = project()
    path = root / "baseline.json"
    assert main(["baseline", str(root), "--output", str(path)]) == 0
    assert main(["check", str(root), "--baseline", str(path)]) == 0
    readme = root / "README.md"
    readme.write_text("\n\n" + readme.read_text())
    result = scan(root)
    apply_baseline(path, result)
    assert result.findings == []
    readme.write_text(readme.read_text() + "\n[another](newly-missing.md)\n")
    assert main(["check", str(root), "--baseline", str(path)]) == 1


def test_suppression_reduces_only_selected_check(project):
    root = project()
    readme = root / "README.md"
    readme.write_text(
        readme.read_text().replace(
            "```python\nfrom demo", "<!-- claimlint: ignore DP003 -->\n```python\nfrom demo"
        )
    )
    assert not [f for f in scan(root).findings if f.check == "DP003"]
    assert [f for f in scan(root).findings if f.check == "DP002"]


def test_annotations_escape_untrusted_workflow_commands():
    finding = Finding("DP006", "error", "a,b.md", 3, "bad\n::error::injected%", {"claim": "x"})
    result = ScanResult([finding], {"DP006": Coverage()}, ["a,b.md"])
    text = render(result, "github")
    assert "file=a%2Cb.md" in text
    assert text.count("\n") == 1
    assert "%0A::error::injected%25" in text


def test_invalid_baseline_is_an_operational_error(project, capsys):
    root = project()
    baseline = root / "invalid.json"
    baseline.write_text('{"schema_version": 99}')
    assert main(["check", str(root), "--baseline", str(baseline)]) == 2


def test_baseline_json_is_versioned(project):
    root = project()
    path = root / "baseline.json"
    write_baseline(path, scan(root))
    assert json.loads(path.read_text())["schema_version"] == 1


def test_summary_and_nested_project_annotation_paths(project, capsys, monkeypatch):
    root = project()
    monkeypatch.chdir(root.parent)
    summary = root.parent / "summary.md"
    assert main(["check", str(root), "--format", "github", "--summary", str(summary)]) == 1
    assert "file=drift/README.md" in capsys.readouterr().out
    assert "### claimlint:" in summary.read_text(encoding="utf-8")


@pytest.mark.parametrize("format", ["json", "text", "github"])
def test_unicode_output_with_windows_legacy_pipe_encoding(project, format):
    root = project("clean")
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs/不存在🤦.md").write_text("[missing](absent.md)\n", encoding="utf-8")
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "claimlint",
            "check",
            str(root),
            "--format",
            format,
            "--select",
            "DP006",
        ],
        env={**os.environ, "PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"},
        capture_output=True,
    )
    assert process.returncode == 1, process.stderr.decode("utf-8")
    output = process.stdout.decode("utf-8")
    assert "不存在🤦.md" in output
    if format == "json":
        assert json.loads(output)["findings"][0]["check"] == "DP006"
