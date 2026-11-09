# Changelog

All notable changes to THALIA are documented here. Versioned GitHub software
releases do not themselves assign a new Zenodo DOI. The immutable `0.1.0` archive
remains at [10.5281/zenodo.21763245](https://doi.org/10.5281/zenodo.21763245).

## [0.3.0] - 2026-11-08

### Added

- Composable full-context, harness, lexical-only, and adaptive context methods
  with a shared typed prompt renderer and exactly one submitted completion per
  backend/method/example cell.
- Matched multi-seed cohorts, rotating method order, prompt character accounting,
  portable producer-source inventories, observed dependency versions, and
  per-method/category/stratum summaries.
- Within-model paired contrasts averaged equally across seed means, with
  seed-cluster descriptive bootstrap intervals, explicit small-cluster warnings,
  and suppression of estimates for incomplete pairs or intervals for one seed.
- Method-aware accessible dashboard/manuscript tables and a source-owned
  experimental-design flow diagram.
- Realized prompt-exposure diagnostics: distinguish unique example IDs from
  repeated inputs, compare recorded prompt pairs, and group exact per-example
  prompt vectors without inferring equivalence from missing observations.
- Repeatable method/seed CLI selection, explicit base configuration loading,
  Ollama requested context control, and selectable manuscript benchmark input.

### Changed

- Clean report schema-2 cutover: backend metadata no longer carries mixed-method
  aggregates. Historical schema-1 reports require their versioned reader or a
  genuine new run, not fabricated migration fields.
- Move base harness configuration to `build_benchmark_methods(config=...)`;
  `run_backend_benchmark` takes `methods` and plural `seeds` instead of the
  former singular `config`/`seed` arguments.
- Skip zero-weight retrieval scoring lanes and exclude their candidates/ranks
  from fusion. Independently enabled query expansion and MMR retain their
  configured behavior.
- Separate finite local method diagnostics from historical cloud/DSPy data,
  expert quality, P0 confirmation, and production acceptance throughout use
  guidance and the manuscript.
- Reject malformed configuration YAML as argparse status 2 without exposing
  its contents, and preserve argument isolation when the manuscript generator
  is called as an imported orchestrator.
- Remove duplicated token/default-count and presentation-wording pins from
  manuscript tests; retain typed fail-closed boundaries and exact hydration
  checks against real generated artifacts.

### Validation

- Qualify the exact source through real installed CLI/API use, the strict
  software/artifact gates, matched local-model execution, native manuscript
  rendering, and browser inspection. Observed results belong in this version's
  release notes and manifest rather than inherited counts from an older tag.
- No new cloud execution, model download, Zenodo DOI, expert-quality assessment,
  or scientific claim promotion follows from this software release.

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
