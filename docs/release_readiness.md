# Versioned GitHub release controls

_Updated 2026-11-09 for v0.3.1._ Software availability remains separate from
scientific claim promotion.

## Current release identity

- Version: `0.3.1`; release date in source metadata: `2026-11-09`.
- GitHub release target: [v0.3.1](https://github.com/docxology/thalia/releases/tag/v0.3.1).
- Canonical repository: [docxology/thalia](https://github.com/docxology/thalia).
- Changes and scope: [v0.3.1 release notes](releases/v0.3.1.md).
- Current metadata declares no DOI. No Zenodo publication or new DOI is
  authorized for this version. The historical DOI is recorded only as an
  `isNewVersionOf` relation, not as v0.3.1's identity.

The versioned URL is the intended release identity, not proof of remote
publication. The publisher must verify the published tag, exact commit, assets,
and candidate checks before recording release completion. Earlier local test
results or an earlier manuscript render do not certify v0.3.1.

This patch corrects publication-manifest closure and supersedes the v0.3.0
supplement defect without changing the measured study. THALIA owns
`output/reports/thalia_artifact_manifest.json`; the native renderer owns
`output/reports/artifact_manifest.json`. Neither writer may overwrite the
other's manifest. The measured study remains the unreleased producer `41da836`,
with the original `0.3.0` wheel, fingerprint, and producer capsule names.

## Current-candidate publication gates

1. Finish all source, metadata, citation, documentation, entry-point, and QA
   changes. Retain measured JSON unchanged; do not reseal evidence or imply a
   study rerun, new cloud execution, or new scientific acceptance.
2. Finalize publication artifacts, figures, variables, manuscript injection,
   dashboard, and QA in dependency order. Inspect the cover's current version
   versus historical DOI wording, benchmark limitations, tagged-PDF structure,
   HTML, and slides. Record actual page counts and checks, not carried-forward
   observations, then freeze the outputs.
3. Stage clean source plus the allowlisted output closure. Use the external
   adapter's `--template-root PATH` and `--validate-only` mode to invoke real
   native validation without rerendering. Require THALIA manifest validation
   as well; a native pass alone does not certify the publication closure.
4. After native validation, run the project release gate, including strict
   test/coverage, typing, lint, locked-dependency, and package-build checks.
   Exercise installed `thalia` and `thalia-benchmark` outside the checkout;
   benchmark output belongs in the caller's working directory. Do not edit
   manifest-tracked QA after final validation; any closure change invalidates
   that validation and requires a newly frozen, validated closure.
5. Package the exact verified closure, inventory redistributable assets, and
   record sizes/checksums and the exact candidate commit. Publish the distinct
   `v0.3.1` GitHub tag/release, then verify remote publication and attached assets
   before announcing completion.

These are release requirements, not a claim that the checks have already run.
Model observations do not confer expert-quality or production acceptance.

## Immutable historical archive

The completed `v0.1.0` GitHub/Zenodo release remains documented in
[`release_receipt.md`](release_receipt.md), including commit
`ab6543c1b139a6ac4ca0b8a091b588384997bcf9`, asset checksums, and its dated checks.
Its archive DOI is
[10.5281/zenodo.21763245](https://doi.org/10.5281/zenodo.21763245).
Do not move that tag, overwrite its assets, repurpose its DOI, or claim that its
manuscript is the regenerated current manuscript. The historical receipt remains
unchanged. The separate [v0.2.0 release](releases/v0.2.0.md), tag, report schema,
and downloadable assets are likewise immutable; schema-2 consumers do not
silently reinterpret schema-1 data.

The [v0.3.0 release](releases/v0.3.0.md), tag, and assets also remain unchanged.
The v0.3.1 patch supersedes its supplement defect; it does not rewrite that
historical release or rename the original measured producer capsules.

## Rights and scientific scope

MIT applies to THALIA's authored source code. It does not establish redistribution
rights for benchmark-derived data, model weights, raw answers, annotations,
private-volume artifacts, credentials, or third-party figures and metadata.
Inventory every asset and exclude material whose rights are not established.

The backend/method study is a finite synthetic diagnostic with complete/failure
accounting, not a general model ranking. Its contrasts are within backend,
paired by example, and averaged equally across seed clusters. Missing pairs
suppress a contrast; a single represented seed suppresses its interval. Small
seed counts and observed end-to-end latency limit interpretation. Prompt
characters are not billed tokens; requested context is not proven context
retention. Automatic support metrics are not entailment, faithfulness, or
expert answer-quality labels. The extractive generation ceiling and
hashing-embedding surrogate remain explicit limitations. Independent P0 integrity,
expert-rater quality, and production acceptance remain separate gates; neither
GitHub publication nor the historical DOI promotes those claims. See
[`PUBLICATION_READINESS.md`](../PUBLICATION_READINESS.md).
