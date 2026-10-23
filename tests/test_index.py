from claimlint.code_index import build_index
from claimlint.config import load_config
from claimlint.engine import Options, scan


def test_fields_environment_aliases_and_reexports(project):
    root = project("clean")
    (root / "src/demo/settings.py").write_text("""from dataclasses import dataclass
from pydantic_settings import BaseSettings as Base
from os import getenv as read
from os import environ as env

@dataclass
class Record:
    name: str

class Settings(Base):
    timeout: int = 10

token = read("DEMO_OTHER")
key = env["DEMO_KEY"]
""")
    index = build_index(load_config(root))
    assert index.symbols["demo.settings.Record"].fields == {"name"}
    assert index.symbols["demo.settings.Settings"].settings
    assert index.symbols["demo.settings.Settings"].fields == {"timeout"}
    assert {"DEMO_OTHER", "DEMO_KEY"} <= index.env.keys()
    with (root / "README.md").open("a") as stream:
        stream.write("\n`Settings.old_timeout`\n")
    result = scan(root, Options(select={"DP005"}))
    assert any(f.evidence["claim"] == "Settings.old_timeout" for f in result.findings)


def test_shell_local_variables_are_not_stale_environment_claims(project):
    root = project("clean")
    with (root / "README.md").open("a") as stream:
        stream.write("""
```sh
DEMO_CONFIG_DIR='/some/local/directory'
mkdir -p "$DEMO_CONFIG_DIR/config"
```
""")
    assert not scan(root, Options(select={"DP005"})).findings


def test_rebinding_import_does_not_report_a_dead_project_symbol(project):
    root = project("clean")
    (root / "README.md").write_text("""```python
import demo
demo = object()
demo.not_a_project_method()
```
""")
    assert not scan(root, Options(select={"DP002", "DP003"})).findings


def test_dynamic_and_external_names_remain_uncertain_through_reexport_chains(project):
    root = project("clean")
    (root / "src/demo/dynamic.py").write_text("def __getattr__(name): return object()\n")
    (root / "src/demo/aliases.py").write_text(
        "from pathlib import Path\nfrom .dynamic import Generated\n"
    )
    with (root / "src/demo/__init__.py").open("a") as stream:
        stream.write("\nfrom .aliases import Path, Generated\n")
    (root / "README.md").write_text("`demo.Path` and `demo.Generated`\n")
    result = scan(root, Options(select={"DP002"}))
    assert not result.findings
    assert len(result.coverage["DP002"].skipped) == 2
