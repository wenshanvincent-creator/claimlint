# Changelog

## 0.1.1 — October 23, 2026

- Recognize configured Markdown attribute IDs, MyST cross-reference targets and MkDocs
  page routes; report generated API/template anchors as skipped coverage.
- Skip uncertain environment names instead of inferring staleness from a shared prefix;
  search prose, supplemental RST and root changelogs for environment documentation mentions.
- Emit UTF-8 output on Windows even when redirected streams use a legacy code page.

## 0.1.0 — October 23, 2026

- Deterministic source, example, CLI, link, settings and agent-instruction checks.
- Text, JSON and GitHub annotations, coverage reporting, baselines and inline suppression.
- Explicit opt-in for runtime CLI help and Python example execution.
- Optional Codex patch transport with document-only static validation and dry-run default.
- Composite action, CI, fixtures and local distribution builds.

Releases run the Linux and Windows CI matrix before publishing through PyPI Trusted Publishing.
