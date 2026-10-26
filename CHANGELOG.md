# Changelog

All notable changes to THALIA are documented here. Version `0.1.0` is publicly
released and archived at
[10.5281/zenodo.21763245](https://doi.org/10.5281/zenodo.21763245); the entries
below are release-candidate notes for work after that boundary, not a new
release or DOI.

## [Unreleased]

### Added

- MIT licensing for the source code, with matching declarations in
  `pyproject.toml`, `CITATION.cff`, and `.zenodo.json`.
- Source-controlled release metadata, contribution guidance, security contact,
  issue templates, and a release-oriented CI/package metadata check.
- A claim-ceiling evidence-tier visualization and corresponding manuscript
  traceability checks.

### Changed

- Replaced the deprecated `dspy-ai` alias with the canonical `dspy` package in
  the `dev` and `neural` extras (the alias stub only re-declared `dspy`), and
  re-locked; `uv lock --check` stays green.
- Corrected the project-name drift: `README.md`, `docs/glossary.md`, the
  `src` package docstring, the dashboard subtitle, the manuscript config
  comment, and the package description now use the published release title
  ("Typed Harness with Analytical Lexical-Integrated Architecture") instead of
  the three divergent taglines.
- Tightened manuscript language so finite deterministic, neural, integrity, and
  production observations are not promoted beyond their evidence tiers.
- Improved the release checklist to distinguish code licensing from the
  redistribution rights of benchmark data, model weights, raw answers, and
  generated supplementary artifacts.

### Validation

- The authoritative local suite, static checks, deterministic artifact gates,
  and external PDF/HTML rendering remain the source-current validation path.
  Their observed values belong in the release receipt for the exact tagged
  commit; this changelog intentionally does not freeze a stale run summary.
