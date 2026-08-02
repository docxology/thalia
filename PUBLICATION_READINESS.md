# THALIA — Publication-Readiness Assessment

_Review refreshed 2026-08-02. The local source, deterministic package, enlarged
finite-set audit, manuscript injection, generated artifacts, PDF, and HTML
render gates pass. Stronger claims about model quality, true-source recovery,
integrity, or production readiness remain unpromoted._

## Current evidence

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

## Publication decision

The checkout is conditionally ready for submission as a narrowly scoped typed
harness, methods, and reproducibility paper, provided the manuscript retains
its current evidence tiers and limitations. It is not ready for publication
as a broad model-quality, true-source-recovery, integrity-advantage, or
production-readiness result.

## GitHub and Zenodo release decision

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
5. **Post-release maintenance:** retain the tag/DOI/bundle as the immutable
   v0.1.0 authority. For any accepted scientific promotion or new version,
   regenerate the ledger, figures, dashboard, variables, PDF, and supplementary
   outputs, then repeat the full test, typing, lint, artifact, and rendering
   gates against a new exact tag. Reassess redistribution rights before adding
   any external benchmark, model, raw-answer, or annotation artifacts.

Until the independent P0, expert-quality, and production acceptance records
exist, the paper should describe those lanes as protocols and open validation
work, not as completed scientific or operational claims.
