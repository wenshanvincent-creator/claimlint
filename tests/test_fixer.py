import difflib
from contextlib import contextmanager
from pathlib import Path

import pytest

from claimlint.engine import Options, scan
from claimlint.fixer import apply_patch, fix


class ReplaceBackend:
    def __init__(self, old, new):
        self.old = old
        self.new = new

    def propose(self, finding, document):
        return "".join(
            difflib.unified_diff(
                document.splitlines(keepends=True),
                document.replace(self.old, self.new).splitlines(keepends=True),
                fromfile=f"a/{finding.doc_file}",
                tofile=f"b/{finding.doc_file}",
            )
        )


def test_fixer_dry_run_then_apply_and_recheck(project):
    root = project()
    original = (root / "README.md").read_bytes()
    backend = ReplaceBackend("columns=80", "width=80")
    options = Options(select={"DP003"})
    result = fix(root, backend, options)
    assert len(result.accepted) == 1 and not result.rejected
    assert '-render("hello", columns=80)' in result.diff
    assert (root / "README.md").read_bytes() == original
    applied = fix(root, backend, options, apply=True)
    assert applied.accepted
    assert not scan(root, options).findings


def test_fixer_rejects_new_findings_and_preserves_original(project):
    root = project()
    original = (root / "README.md").read_bytes()
    result = fix(
        root, ReplaceBackend("columns=80", "new_typo=80"), Options(select={"DP003"}), apply=True
    )
    assert result.rejected and not result.accepted
    assert (root / "README.md").read_bytes() == original


def test_fixer_rejects_broken_python_syntax(project):
    root = project()
    result = fix(root, ReplaceBackend("columns=80", "width="), Options(select={"DP003"}))
    assert result.rejected and not result.accepted
    assert "unverified" in result.rejected[0]


def test_fixer_preserves_windows_line_endings():
    patch = "--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-old\n+new\n"
    assert apply_patch("old\r\n", patch, "README.md") == "new\r\n"


def test_fixer_canonicalizes_temporary_directory_aliases(project, monkeypatch):
    import claimlint.fixer as fixer_module

    temporary_directory = fixer_module.tempfile.TemporaryDirectory

    @contextmanager
    def aliased_directory(*args, **kwargs):
        with temporary_directory(*args, **kwargs) as directory:
            path = Path(directory)
            yield str(path / ".." / path.name)

    monkeypatch.setattr(fixer_module.tempfile, "TemporaryDirectory", aliased_directory)
    result = fix(project(), ReplaceBackend("columns=80", "width=80"), Options(select={"DP003"}))
    assert len(result.accepted) == 1 and not result.rejected


@pytest.mark.parametrize(
    "patch",
    [
        "--- a/src/demo/api.py\n+++ b/src/demo/api.py\n@@ -1 +1 @@\n-x\n+y\n",
        "--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-wrong context\n+y\n",
        "--- a/README.md\n+++ b/README.md\n@@ -1 +1,2 @@\n x\n+<!-- claimlint: skip -->\n",
    ],
)
def test_rejects_code_edits_stale_context_and_suppression(patch):
    with pytest.raises(ValueError):
        apply_patch("x\n", patch, "README.md")


def test_rejects_a_second_file():
    patch = (
        "--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-x\n+y\n"
        "--- a/other.md\n+++ b/other.md\n@@ -1 +1 @@\n-a\n+b\n"
    )
    with pytest.raises(ValueError):
        apply_patch("x\n", patch, "README.md")
