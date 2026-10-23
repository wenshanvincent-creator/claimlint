# Working on claimlint

Keep deterministic checks grounded in claims attributable to the checked repository.
Report incomplete analysis as skipped coverage. Default scans must not import project code.
The fixer transport only proposes patches; the validator owns acceptance and file writes.

Useful commands, run from the repository root after installing development dependencies:

```sh
python -m pytest tests/
ruff check src/ tests/
python -m claimlint check .
python -m build
```

Tests use planted repositories under `tests/fixtures/`. Fixtures are source evidence and are
excluded from automatic formatting so documentation line receipts stay stable. For a checker
change, test the specific false positive or missed finding it addresses.
