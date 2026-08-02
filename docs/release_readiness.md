# Public GitHub and Zenodo release record

_Release recorded 2026-08-02._ This record separates the completed public
software release from the manuscript and scientific-promotion decision.

## Completed release

THALIA `v0.1.0` is publicly released.

- GitHub repository: [docxology/thalia](https://github.com/docxology/thalia),
  public with default branch `main`.
- Release authority: annotated tag `v0.1.0`, commit
  `ab6543c1b139a6ac4ca0b8a091b588384997bcf9`.
- Zenodo record: [10.5281/zenodo.21763245](https://doi.org/10.5281/zenodo.21763245),
  published open access as software, version `0.1.0`, with MIT metadata.
- Uploaded files: exact tagged source archive, rendered PDF, and the curated
  artifact bundle containing the hydrated manuscript, HTML, figures, slides,
  derived data, and validation receipts.
- Checksums and the release boundary: [`release_receipt.md`](release_receipt.md).

The manuscript itself is conditionally suitable for a narrowly scoped methods
submission, subject to the separate evidence boundaries in
[`PUBLICATION_READINESS.md`](../PUBLICATION_READINESS.md). P0 integrity,
expert-rater quality, and production acceptance remain unpromoted. Those open
scientific gates are independent of making the code repository public.

## Post-release controls

- **Rights boundary:** MIT applies to THALIA's authored source code. It does
  not override rights for benchmark-derived data, model weights, raw answers,
  private-volume artifacts, or third-party figures and metadata. The v0.1.0
  upload excludes those private or unverified materials.
- **Source-current regeneration:** future versions must regenerate the PDF,
  HTML, figures, dashboard, variables, manifests, test reports, and coverage
  from a new exact candidate commit before tagging.
- **Immutable authority:** do not move `v0.1.0` or repurpose its DOI. A
  substantive change requires a new version tag and a Zenodo new-version
  record.
- **Scientific scope:** no public release note or DOI citation should imply a
  promoted model-quality, integrity-advantage, or production-readiness result.

## What the MIT decision covers

The source-controlled [`LICENSE`](../LICENSE) grants the standard MIT rights
for THALIA's authored source code. The decision does not certify that all files
in a future release bundle are authored by the project or legally redistributable.
Before publication, inventory the exact files included in the GitHub release
and Zenodo archive, record their provenance, and exclude or separately license
anything whose rights are not established. In particular, do not publish raw
answers, annotations, credentials, private external-volume data, or model
weights merely because the code is MIT-licensed.

## Completed release sequence

1. The strict suite, typing, lint, build, artifact, manuscript-injection, and
   external PDF/HTML gates passed for the candidate.
2. The rendered PDF was visually inspected, including the DOI-bearing cover,
   reproducibility page, formalism, evaluation, and validation pages.
3. The exact candidate was pushed as `ab6543c1b139a6ac4ca0b8a091b588384997bcf9`,
   tagged `v0.1.0`, and made public on GitHub.
4. Zenodo was populated from that release boundary, published, and verified
   through the public API and DOI redirect.
5. The DOI, tag, checksums, validation receipts, and excluded-materials
   boundary were recorded in [`release_receipt.md`](release_receipt.md).

No public release should imply a promoted model-quality, integrity-advantage,
or production-readiness result. The release notes should preserve the negative
controls and the current conditional wording.
