# Analysis limits

Every finding carries a claim and evidence. Evidence is bounded by the analysis that produced it.

- DP001 statically supports simple argparse construction, literal options and subcommands,
  parser parents, aliases, and option groups reachable from the declared entry point.
  Dynamic argument construction, parser-mutating helpers, and parse-known-args are incomplete.
  Click/Typer require opt-in help execution. Arbitrary shell programs are not interpreted.
  Short-option clusters and long-option abbreviations are left unjudged.
- DP002 resolves local imports and re-exports and namespace modules. Wildcard imports,
  conditional namespaces, module getattr, inherited names and external re-exports can be
  incomplete. Bare prose names are not interpreted as claims about this package.
- DP003 binds complete Python fences to plain function signatures. It checks required,
  keyword-only and positional-only parameters, variadic arguments and duplicate binding.
  Decorators, generated constructors, inherited signatures, instance inference and unpacked
  arguments are skipped. It does not type-check values or track dependencies between fences.
- DP004 executes each Python fence independently. Missing dependencies and undefined names
  can indicate an intentionally partial example. Use a skip comment for such blocks.
  Timeouts bound the direct subprocess, not an entire tree of descendants.
- DP005 recognizes literal reads through os.getenv and os.environ, plus top-level imported
  aliases and pydantic model annotations. Dynamically computed environment names, indirect
  wrappers, inherited settings, field aliases and environment prefixes are not inferred.
  A missing literal read is skipped, even when another project variable shares its prefix:
  dependencies may handle it. Coverage notes mean no mention was found in selected Markdown,
  matching supplemental RST files or root CHANGES/CHANGELOG/HISTORY files; private integration
  variables may need no public docs.
  Supplemental RST is searched for mentions only, not checked for other kinds of drift.
- DP006 resolves explicit relative Markdown links, reference links, images, Unicode heading
  IDs, duplicate headings and explicit HTML anchors. MkDocs configuration enables attribute
  IDs and maps rendered routes back to source pages; MyST labels are recognized when Sphinx
  enables myst_parser. Renderer configs are read as data and never executed. Missing anchors
  on pages containing active mkdocstrings directives or template content are skipped, not
  counted as verified: generated content cannot be checked without running the builder.
  External URLs, site-root URLs, arbitrary renderer routing, dynamic configuration, custom
  plugins and non-Markdown anchors are not verified. GitHub-style heading slugs may differ
  from a static-site generator's custom slug rules.
- DP007 recognizes common shell command forms, Python scripts, pytest paths, Make targets,
  and tool declarations in dependencies, extras and dependency groups. It does not execute
  shell commands or evaluate Make includes, shell expansions, generated files or full recipes.
  An undeclared tool can be provisioned externally, so this is only a note.

Only literal static facts are reproducible. Opt-in runtime help and examples can depend on
the installed environment and application behavior. Install the same dependencies in CI
and local execution if comparing those reports.

The baseline is an adoption aid, not a proof that previously accepted findings are fixed.
Inline ignores also reduce scope. Review both when changing documentation.
