# Usefulness assessment

Evaluated October 23, 2026 using upstream package metadata and project documentation.

The problem is useful: Markdown examples and agent command recipes can drift independently
of code tests. A deterministic gate can catch exact, attributable mismatches without a model
subscription. This is a useful maintainer tool and portfolio artifact; customer demand and
willingness to pay have not been established by this build.

The original positioning is too broad. Existing tools already do deterministic checking:

- [docproof](https://pypi.org/project/docproof/) 0.2.4 is published, with a composite action
  and checks for paths, argparse options, installation metadata, and documented imports.
  Its upstream is [melbinjp/docproof](https://github.com/melbinjp/docproof).
- [pytest-examples](https://github.com/pydantic/pytest-examples) tests Python code examples
  in Markdown and docstrings.
- [docsig](https://pypi.org/project/docsig/) checks parameters in function/method docstrings.

claimlint's useful focus is the combination of Python example argument binding, settings/env
references, and agent-file recipes with source evidence and a shared CI interface. This
combination is a hypothesis about adoption, rather than a claim that every feature is novel.

PyPI's JSON endpoint returned HTTP 404 for claimlint during the assessment. That is a name
collision check at that time, not a reservation or trademark clearance. docproof's endpoint
returned version 0.2.4 and the existing project's README; its name cannot be reused.

## Changes from the supplied spec

- Static argparse analysis is the default. Help subprocesses require --introspect-cli.
- A temporary cwd is described accurately as process separation, not an OS sandbox.
- Bare names and third-party names are not enough evidence to call a symbol dead.
- Missing documentation is a note; it is different from code contradicting a documented claim.
- Dynamic surfaces report skipped coverage, rather than pretending to be fully checked.
- DP006 checks explicit Markdown links; loose file paths are checked only in agent files,
  where repository instructions make ownership clearer.
- The action emits annotations and a job summary. Automated PR comments and suggestion PRs
  would add write permissions and are deferred.
- Releases run hosted CI and build distributions from a version tag, then use a scoped
  PyPI Trusted Publisher. Private local evaluation receipts are excluded from public history.

The next useful product test is to use this on maintained repositories, manually classify
findings, and ask maintainers whether the check prevented a real broken instruction. Passing
fixtures demonstrates implementation behavior, not market demand or broad precision.
