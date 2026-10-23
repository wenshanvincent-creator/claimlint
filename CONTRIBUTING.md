# Contributing

Use Python 3.10 or newer. Install the source with development dependencies:

```sh
python -m pip install -e ".[dev]"
python -m pytest
ruff check .
claimlint check .
```

For a checker change, include a small example of the real regression and its expected
finding or skip reason. Keep attribution narrow: do not report third-party commands,
illustrative reader-project paths or dynamic APIs as proven repository defects.

The checked project must never be imported during a default scan. Keep subprocess work
behind explicit execution flags. A fixer backend proposes text; the validator owns writes.
Use fake backends for patch validation tests so tests need no model credentials.

Run the focused tests for your change. Before a release, also run the project's CI commands
and inspect the built wheel/source archive. See [RELEASING](RELEASING.md).
