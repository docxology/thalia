# Versioned GitHub release controls

_Updated 2026-11-08 for v0.3.0._ Software availability remains separate from
scientific claim promotion.

## Current release identity

- Version: `0.3.0`; release date in source metadata: `2026-11-08`.
- GitHub release target: [v0.3.0](https://github.com/docxology/thalia/releases/tag/v0.3.0).
- Canonical repository: [docxology/thalia](https://github.com/docxology/thalia).
- Changes and scope: [v0.3.0 release notes](releases/v0.3.0.md).
- Current metadata declares no DOI. No Zenodo publication or new DOI is
  authorized for this version. The historical DOI is recorded only as an
  `isNewVersionOf` relation, not as v0.3.0's identity.

The versioned URL is the intended release identity, not proof of remote
publication. The publisher must verify the published tag, exact commit, assets,
and candidate checks before recording release completion. Earlier local test
results or an earlier manuscript render do not certify v0.3.0.

## Current-candidate publication gates

1. Finish all source, metadata, citation, documentation, and entry-point changes.
2. Run the strict test/coverage, typing, lint, locked-dependency, and package-build
   gates on the completed candidate. Exercise installed `thalia` and
   `thalia-benchmark` outside the checkout; benchmark output belongs under the
   caller's working directory, never in the installed package.
3. Execute the declared local method study with the recorded seeds, methods,
   models, generation options, and failure accounting. Preserve incomplete
   diagnostics and do not silently replace a failed cohort with a smaller one.
   Regenerate deterministic evidence, fingerprint-bound screens, figures,
   variables, manuscript injection, dashboard, and manifests in dependency order.
   Historical DSPy/cloud aggregates remain distinct; no new cloud call is implied.
4. Validate exact source-to-render substitution and render the completed
   manuscript. Inspect the cover's current GitHub version versus historical DOI
   wording, benchmark limitations, tagged-PDF structure, HTML, and slides.
   Record actual page counts and checks rather than carrying them forward.
5. Inventory redistributable assets, record sizes/checksums and the exact
   candidate commit, then publish the distinct `v0.3.0` GitHub tag/release.
   Verify remote publication and attached assets before announcing completion.

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
