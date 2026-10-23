# Releasing

1. Update the project and module versions together, changelog, README version examples,
   and the corresponding release notes under `.github/release-notes/`.
2. Run pytest, Ruff, self-checks and python build as in the CI workflow. Review the final diff
   and distribution contents. Keep private evaluation receipts outside the public history.
3. Push main to `wenshanvincent-creator/claimlint` and wait for the exact commit's CI to pass.
4. For initial setup, register a PyPI pending Trusted Publisher for project `claimlint`, owner
   `wenshanvincent-creator`, repository `claimlint`, workflow `release.yml`, environment `pypi`.
   No long-lived PyPI token belongs in the repository.
5. Tag the verified commit with its version, such as `v0.1.0`, then push that tag. The Release
   workflow repeats CI on the tag, builds and checks distributions in a separate job,
   and uploads those artifacts through the trusted publishing job.
6. The final job installs the actual PyPI package, smoke-checks the clean fixture, and
   creates the GitHub release with artifacts and checksums. Verify the workflow result,
   package URL, and artifact hashes before reporting completion.
