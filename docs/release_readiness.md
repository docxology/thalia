# Versioned GitHub release controls

_Updated 2026-11-08 for v0.2.0._ Software availability remains separate from
scientific claim promotion.

## Current release identity

- Version: `0.2.0`; release date in source metadata: `2026-11-08`.
- GitHub release target: [v0.2.0](https://github.com/docxology/thalia/releases/tag/v0.2.0).
- Canonical repository: [docxology/thalia](https://github.com/docxology/thalia).
- Changes and scope: [v0.2.0 release notes](releases/v0.2.0.md).
- Current metadata declares no DOI. No Zenodo publication or new DOI is
  authorized for this version. The historical DOI is recorded only as an
  `isNewVersionOf` relation, not as v0.2.0's identity.

The versioned URL is the intended release identity, not proof of remote
publication. The publisher must verify the published tag, exact commit, assets,
and candidate checks before recording release completion. Earlier local test
results or the pre-version-change manuscript render do not certify v0.2.0.

## Current-candidate publication gates

1. Finish all source, metadata, citation, documentation, and entry-point changes.
2. Run the strict test/coverage, typing, lint, locked-dependency, and package-build
   gates on the completed candidate. Exercise installed `thalia` and
   `thalia-benchmark` outside the checkout; benchmark output belongs under the
   caller's working directory, never in the installed package.
3. Regenerate deterministic evidence, fingerprint-bound screens, figures,
   variables, manuscript injection, dashboard, and manifests in dependency order.
   Retained model-dependent aggregates need no new network inference; live
   observations remain separately scoped.
4. Validate exact source-to-render substitution and render the completed
   manuscript. Inspect the cover's current GitHub version versus historical DOI
   wording, benchmark limitations, tagged-PDF structure, HTML, and slides.
   Record actual page counts and checks rather than carrying them forward.
5. Inventory redistributable assets, record sizes/checksums and the exact
   candidate commit, then publish the distinct `v0.2.0` GitHub tag/release.
   Verify remote publication and attached assets before announcing completion.

These are release requirements, not a claim that the checks have already run.
No new neural evaluation or scientific acceptance is implied by completing them.

## Immutable historical archive

The completed `v0.1.0` GitHub/Zenodo release remains documented in
[`release_receipt.md`](release_receipt.md), including commit
`ab6543c1b139a6ac4ca0b8a091b588384997bcf9`, asset checksums, and its dated checks.
Its archive DOI is
[10.5281/zenodo.21763245](https://doi.org/10.5281/zenodo.21763245).
Do not move that tag, overwrite its assets, repurpose its DOI, or claim that its
manuscript is the regenerated v0.2.0 manuscript. The historical receipt remains
unchanged.

## Rights and scientific scope

MIT applies to THALIA's authored source code. It does not establish redistribution
rights for benchmark-derived data, model weights, raw answers, annotations,
private-volume artifacts, credentials, or third-party figures and metadata.
Inventory every asset and exclude material whose rights are not established.

The optional common-backend benchmark is a finite synthetic diagnostic with
complete/failure accounting, not a general model ranking. Automatic support
metrics are not entailment, faithfulness, or expert answer-quality labels.
Latency is observed harness/client overhead under the recorded host/provider
conditions, not a production guarantee. The extractive generation ceiling and
hashing-embedding surrogate remain explicit limitations. Independent P0 integrity,
expert-rater quality, and production acceptance remain separate gates; neither
GitHub publication nor the historical DOI promotes those claims. See
[`PUBLICATION_READINESS.md`](../PUBLICATION_READINESS.md).
