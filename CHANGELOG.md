# Changelog

All notable changes to THALIA are documented here. Version `0.2.0` is a GitHub
software release; no new Zenodo DOI is assigned. The immutable `0.1.0` archive
remains at [10.5281/zenodo.21763245](https://doi.org/10.5281/zenodo.21763245).

## [0.2.0] - 2026-11-08

### Added

- A composable common-harness benchmark for extractive, local Ollama, and
  explicitly opted-in OpenRouter clients, with matched seeded examples, prompt
  fingerprints, per-example failures, model provenance, observed latency, and
  validated atomic complete-only output.
- Accessible backend observations in the offline dashboard and generated
  manuscript table, with explicit missing/incomplete states and separate
  historical DSPy/cloud evidence.
- Installed `thalia` query and `thalia-benchmark` console commands, including
  SDK-free offline benchmarking outside a source checkout.

### Changed

- Replaced the deprecated `dspy-ai` alias with the canonical `dspy` package in
  the `dev` and `neural` extras (the alias stub only re-declared `dspy`), and
  re-locked; `uv lock --check` stays green.
- Corrected the project-name drift: `README.md`, `docs/glossary.md`, the
  `src` package docstring, the dashboard subtitle, the manuscript config
  comment, and the package description now use the published release title
  ("Typed Harness with Analytical Lexical-Integrated Architecture") instead of
  the three divergent taglines.
- Pinned the development interpreter to Python 3.13: the prior 3.15 pin could
  not build the dev dependency chain's PyO3 extension.
- Reject non-text, empty, and reported incomplete provider generations rather
  than scoring them as successful answers; use bare OpenRouter model slugs in
  the direct HTTP adapter.
- Removed import-time credential-file loading and successful error skips from
  the legacy cloud diagnostic. Live DSPy tests now require explicit opt-in;
  provenance tests use isolated files instead of an untracked benchmark download.
- Corrected retained category comparisons, extractive optimizer attribution,
  runtime-stage accounting, and reproduction/visualization claim boundaries.
- Emit the renderer's canonical `alt_text` figure-registry field so HTML and
  tagged-PDF rendering consume the authored accessibility descriptions.
- Kept tagged-PDF diagnostics enabled while replacing incompatible automatic
  code wrapping with explicit authored continuations in manuscript examples.
- Qualified Python 3.11–3.14 explicitly in CI instead of letting the development
  pin silently select one interpreter for every matrix job.
- Raised the core Python floor to 3.11 and removed obsolete Python 3.10 TOML
  backport branches and the unreachable direct dependency.
- Refreshed locked dependencies, including Pillow 13.0.0.
- Separated the current GitHub version from the historical version-specific
  Zenodo DOI in citation, archive, and manuscript metadata.
- Replaced literal-source command/prose pins with real token-aware link and
  manuscript integrity checks; valid Bash continuations are no longer rejected
  by a documentation substring test.

### Security

- Integrated Dependabot's `filelock` 4.2.1 repair for the reported local locking
  advisories; the compatible lock selects LiteLLM 1.103.10 with DSPy 3.2.1.
- Disabled persistent DSPy caching in THALIA-owned configurators, with real
  disk-to-memory transition regressions. The unpatched DiskCache pickle advisory
  remains explicitly documented in [the security policy](SECURITY.md); this is
  mitigation at the owned boundary, not a dependency fix or security certificate.

### Validation

- The authoritative local suite, static checks, deterministic artifact gates,
  and external PDF/HTML rendering remain the source-current validation path.
  Their observed values belong in the release receipt for the exact tagged
  commit; this changelog intentionally does not freeze a stale run summary.

## [0.1.0] - 2026-08-02

### Added

- MIT licensing for the source code, with matching declarations in
  `pyproject.toml`, `CITATION.cff`, and `.zenodo.json`.
- Source-controlled release metadata, contribution guidance, security contact,
  issue templates, and a release-oriented CI/package metadata check.
- A claim-ceiling evidence-tier visualization and corresponding manuscript
  traceability checks.

### Changed

- Tightened manuscript language so finite deterministic, neural, integrity, and
  production observations are not promoted beyond their evidence tiers.
- Improved the release checklist to distinguish code licensing from the
  redistribution rights of benchmark data, model weights, raw answers, and
  generated supplementary artifacts.

The immutable [release receipt](docs/release_receipt.md) records this version's
public source, DOI, assets, and observed validation.
