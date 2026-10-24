"""Regressions from public-repository review, with executable configs kept inert."""

import pytest

from claimlint.engine import Options, scan


def setup_site(root, config):
    (root / "mkdocs.yml").write_text(config, encoding="utf-8")
    (root / "docs").mkdir(exist_ok=True)
    (root / "README.md").write_text("# Project\n", encoding="utf-8")


def test_attribute_ids_and_generated_anchors_leave_real_drift_visible(project):
    root = project("clean")
    setup_site(
        root,
        """markdown_extensions: [pymdownx.extra]
plugins: [mkdocstrings]
hooks: [docs/plugin.py]
dangerous: !!python/object/apply:builtins.eval ["1/0"]
""",
    )
    (root / "docs/guide.md").write_text(
        """# Before {#custom}

[](){#empty-anchor}

[explicit](#custom) [empty](#empty-anchor) [stale](#old-title)
[API](api.md#demo.render) [included](settings.md#customise-settings-sources)
[example page](examples.md#missing)

`{#inline-fake}`

```markdown
# Fake {#fenced-fake}
```
[bad](#inline-fake) [bad](#fenced-fake)
""",
        encoding="utf-8",
    )
    (root / "docs/api.md").write_text("::: demo\n", encoding="utf-8")
    (root / "docs/settings.md").write_text("{{ external_settings }}\n", encoding="utf-8")
    (root / "docs/examples.md").write_text(
        """# Code samples
```markdown
::: demo
{{ external_settings }}
```
""",
        encoding="utf-8",
    )
    result = scan(root, Options(select={"DP006"}))
    assert {f.evidence["claim"] for f in result.findings} == {
        "#old-title",
        "#inline-fake",
        "#fenced-fake",
        "examples.md#missing",
    }
    skips = result.coverage["DP006"].skipped
    assert len(skips) == 2
    assert any("api.md#demo.render:" in s["reason"] for s in skips)
    assert any("settings.md#customise-settings-sources:" in s["reason"] for s in skips)


def test_myst_labels_are_references_but_missing_labels_and_links_still_fail(project):
    root = project("clean")
    (root / "README.md").write_text("# Project\n")
    docs = root / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "conf.py").write_text("""extensions = ["myst_parser"]
raise RuntimeError("must not import conf.py")
""")
    (docs / "target.md").write_text("""(labels/stability-policy)=
# Policy

```markdown
(labels/example-only)=
```
""")
    (docs / "guide.md").write_text("""[policy](labels/stability-policy)
[anchor](target.md#labels/stability-policy)
[missing](labels/missing)
[code](labels/example-only)
[gone](missing.md)
""")
    result = scan(root, Options(select={"DP006"}))
    assert {f.evidence["claim"] for f in result.findings} == {
        "labels/missing",
        "labels/example-only",
        "missing.md",
    }


def test_mkdocs_routes_resolve_from_the_rendered_page_and_check_the_anchor(project):
    root = project("clean")
    setup_site(root, "site_name: Demo\n")
    (root / "docs/advanced").mkdir()
    (root / "docs/advanced/transports.md").write_text("## ASGI Transport\n")
    (root / "docs/async.md").write_text("""[correct](../advanced/transports#asgi-transport)
[stale](../advanced/transports#asgitransport)
[missing](../advanced/missing#anything)
""")
    result = scan(root, Options(select={"DP006"}))
    assert len(result.findings) == 2
    stale = next(f for f in result.findings if "asgitransport" in f.evidence["claim"])
    assert stale.evidence["resolved"] == "docs/advanced/transports.md"
    assert "anchor #asgitransport does not exist" in stale.message


def test_plain_markdown_does_not_assume_renderer_extensions(project):
    root = project("clean")
    (root / "README.md").write_text("""# Title {#custom}
::: demo
{{ variable }}
[bad](#custom) [bad](#missing)
""")
    result = scan(root, Options(select={"DP006"}))
    assert {f.evidence["claim"] for f in result.findings} == {"#custom", "#missing"}


@pytest.mark.parametrize(
    "directory_urls, destination", [("true", "other#valid"), ("false", "other.html#valid")]
)
def test_mkdocs_root_index_routes_and_directory_url_setting(project, directory_urls, destination):
    root = project("clean")
    setup_site(root, f"use_directory_urls: {directory_urls}\n")
    (root / "docs/index.md").write_text(f"[other]({destination})\n")
    (root / "docs/other.md").write_text("# Valid\n")
    assert scan(root, Options(select={"DP006"})).findings == []


def test_dependency_env_reads_are_uncertain_and_rst_and_prose_mentions_count(project):
    root = project("clean")
    (root / "src/demo/__init__.py").write_text("""import os
from platformdirs import user_cache_dir
TOKEN = os.getenv("DEMO_TOKEN")
HOME = os.getenv("XDG_CONFIG_HOME")
PAGER = os.getenv("PAGER")
cache = user_cache_dir("demo")
""")
    (root / "README.md").write_text("Set `XDG_CACHE_HOME` or `DEMO_OLD_TOKEN`.\n")
    (root / "README.rst").write_text("DEMO_TOKEN is the authentication token.\n")
    (root / "CHANGES.md").write_text("The PAGER variable configures paging.\n")
    docs = root / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "env.md").write_text("XDG_CONFIG_HOME configures settings.\n")
    result = scan(root, Options(select={"DP005"}))
    assert result.findings == []
    assert any(
        "XDG_CACHE_HOME: no literal" in s["reason"] for s in result.coverage["DP005"].skipped
    )
    assert any("README.rst: RST searched" in s["reason"] for s in result.coverage["DP005"].skipped)
