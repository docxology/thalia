# THALIA — Publication-Readiness Assessment

_Release identity updated 2026-11-08 for v0.3.0. The current GitHub release target
is [v0.3.0](https://github.com/docxology/thalia/releases/tag/v0.3.0); no Zenodo
publication or DOI is assigned to this version. Historical checks below do not
certify the current candidate or assert that the GitHub target is published._

## Current software capability and release boundary

v0.3.0 adds composable full-context, harness, lexical-only, and adaptive methods
to the optional common-backend benchmark. It supports an offline extractive
baseline, caller-supplied clients, local Ollama models, and explicitly
selected/authorized OpenRouter models without requiring DSPy for this lane.
Matched multi-seed examples, rotating method order, recorded prompt sizes,
fresh state, failure accounting, and portable source inventories make runs
inspectable. Complete within-backend contrasts average equally across seed
means; missing pairs suppress estimates and one seed suppresses its interval.
Small seed-cluster warnings remain descriptive. None of these mechanisms
establishes a general model ranking, expert quality, or production readiness.

Installed commands are `thalia` (query) and `thalia-benchmark` (benchmark).
The benchmark's default output is `output/data/backend_benchmark.json` relative
to the caller's working directory, not the installed package. The source
scripts remain thin bootstraps. Retained DSPy/provider diagnostic cohorts are
not silently pooled with this lane.

The manuscript includes this capability and its limitations. Its regenerated
page count, tagged-PDF structure, HTML, slides, and exact source substitution
must be checked after the v0.3.0 metadata changes; older renders and earlier
test results are not source-current release receipts. The publisher must
record the current candidate checks, exact tag/commit, asset inventory, and
checksums before announcing release completion. See
[`docs/release_readiness.md`](docs/release_readiness.md) and
[`docs/releases/v0.3.0.md`](docs/releases/v0.3.0.md).

The v0.1.0 DOI and [`docs/release_receipt.md`](docs/release_receipt.md) remain
immutable historical authority only. The current citation identifies v0.3.0
on GitHub; the old DOI is retained as an `isNewVersionOf` relation.

## Historical evidence (2026-08-02, v0.1.0 boundary)

The recorded local source, deterministic package, enlarged finite-set audit,
manuscript injection, generated-artifact, PDF, and HTML gates passed at that
boundary. Stronger claims about model quality, true-source recovery, integrity,
or production readiness remained unpromoted.

- **Executable package:** the authoritative strict suite collected 854 tests,
  passed 847, skipped 7 optional live-model tests, and recorded 90.49% `src/`
  coverage against the 90% gate. Ruff, mypy, compileall, `uv lock --check`,
  and `uv build` pass. The aggregate gate is authoritative; some optional or
  defensive modules have lower local coverage and remain visible in the
  coverage report.
- **Artifact integrity:** the fail-closed validator reports `checked=47
  required=43 ok=True`. It also reports 22 numbered manuscript sections with
  exact source-to-injected substitution parity. The independent verifier
  rejects missing/extra files, unresolved tokens, and content drift.
- **Enlarged deterministic audit:** the publication-size synthetic audit uses
  6 categories, 4 difficulty strata, per-category sizes 25/50/100/250, 10
  seeded clusters, and 2,000 resamples. It contains 25,500 unique requested
  examples, 76,500 method evaluations, and zero failures. The 40-comparison
  Holm family is retained, but the intervals remain descriptive for finite
  seed clusters; this is not a population-power claim.
- **Held-out compiler audit:** the finite synthetic compiler generalization
  run uses 20 seeds and 13,720 evaluations with zero failures. The MIPRO-style
  mean held-out delta is +0.00246 with a descriptive interval of roughly
  [0.00197, 0.00293]; its raw and exploratory Holm p-values are below 0.001.
  This is a promising finite-cluster signal, not a promoted general advantage.
- **Metric and formalism audit:** the notation map includes source-index
  citation precision and recall, with formal objects and composition edges
  validated against code, tests, and manuscript anchors. The metric-construct
  figure decomposes the blended support proxy; it does not claim entailment,
  factuality, or true-source recovery.
- **Integrity boundary:** the legacy `harness_auditable` outcome records only
  lexical containment of the supplied gold value in joined cited excerpts.
  Equal poisoning rates and the no-citation baseline make it a finite
  cited-excerpt/source-exposure proxy, not claim-level auditability,
  faithfulness, or a confirmed integrity advantage. The source-bound integrity
  report remains `screen_only_unpromoted`; its P0 confirmation and poisoning
  separation studies are unexecuted.
- **External and neural evidence:** the retained v2 campaign is operational /
  provenance evidence only; automated metrics and answer hashes are not
  answer-quality labels. The quality-v3 and production-readiness lanes are
  implemented with fail-closed promotion paths, but no accepted expert-rater
  quality certificate or production certificate exists. The local LLM judge is
  exploratory only, and live-model tests were not promoted by the deterministic
  suite.
- **Rendered outputs:** the external template render completed all PDF,
  transmission, Markdown, output-structure, figure-registry, evidence,
  overlay, and artifact-manifest checks. The combined PDF is tagged, encrypted
  false, PDF 2.0, and structurally valid; page-level visual review found no
  clipping in the cover, formalism table, evaluation, quality, reproducibility,
  validation, or reference pages. The correctly rooted browser check loaded
  all 29 images with zero broken images and no horizontal overflow at a 1,280px
  viewport; only non-fatal MathJax CDN version warnings remained.

The generic template metadata remains separate from the THALIA-owned overlay;
`thalia_overlay.yaml` carries quality and production-readiness protocol fields
without widening the generic template schema. Generated `output/` artifacts
remain local/ignored and are not a public release by themselves.

## Scientific publication boundary

The methods-paper assessment remains conditional on preserving the evidence
tiers and limitations below. Software-release authorization does not authorize
a broad model-quality, true-source-recovery, integrity-advantage, or
production-readiness claim. A new benchmark interface and refreshed rendering
do not satisfy the independent scientific-promotion gates.

## Historical GitHub and Zenodo release decision (v0.1.0)

The public `v0.1.0` release is complete. The GitHub repository is public, the
annotated tag points to commit `ab6543c1b139a6ac4ca0b8a091b588384997bcf9`, and
Zenodo record [10.5281/zenodo.21763245](https://doi.org/10.5281/zenodo.21763245)
is published with open-access MIT metadata, the exact source archive, the
rendered PDF, and the derived artifact bundle. File sizes and SHA-256 values
are recorded in [`docs/release_receipt.md`](docs/release_receipt.md).

This release is a reproducibility and software-availability milestone, not a
promotion of model-quality, true-source-recovery, integrity-advantage, or
production-readiness claims. The manuscript's conditional decision and
evidence ceilings remain unchanged.

## Remaining work before stronger claims or future promoted releases

1. **P0 integrity confirmation:** freeze the protocol and adjudication rubric;
   collect matched, balanced attack families across the specified conditions;
   retain raw source and adjudication records; and pass paired, held-out, and
   replay promotion gates. See [`docs/integrity_advantage_handoff.md`](docs/integrity_advantage_handoff.md).
2. **Expert-rater quality study:** freeze the reviewed rubric, primary
   correctness estimand, thresholds, missing-data rules, safety criteria, and
   held-out IDs; run and adjudicate the pilot and confirmatory sets; then
   explicitly accept the fail-closed quality certificate. The local-LLM judge
   cannot substitute for independent expert raters.
3. **Independent production study:** execute and accept the operational
   certificate for latency, cost, failures/retries, privacy, model pinning,
   rollback, monitoring, drift, and red-team coverage. Quality acceptance
   cannot imply operational readiness.
4. **Live-transfer refresh:** if the submission foregrounds neural or external
   benchmark results, rerun those lanes on the declared host/model versions and
   preserve their independent run receipts; do not fold them into the
   deterministic headline.
5. **Versioned software release:** retain the tag/DOI/bundle as the immutable
   v0.1.0 authority. For v0.3.0, execute the declared local method study and
   regenerate the ledger, figures, dashboard,
   variables, PDF, and supplementary outputs, then repeat the full test,
   typing, lint, artifact, packaging, and rendering gates against the exact
   candidate before publishing its distinct GitHub tag. No Zenodo action or
   new DOI is authorized by this release. Reassess redistribution rights before adding
   any external benchmark, model, raw-answer, or annotation artifacts.

Until the independent P0, expert-quality, and production acceptance records
exist, the paper should describe those lanes as protocols and open validation
work, not as completed scientific or operational claims.
