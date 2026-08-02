# Public GitHub and Zenodo release readiness

_Review refreshed 2026-08-02._ This checklist separates a manuscript submission
decision from the authority required to publish a public software release.

## Decision at this checkout

The project is **not yet ready for a public GitHub or Zenodo release**.

The current GitHub repository is private and has no release tag. MIT is now the
selected source-code license and is declared in [`LICENSE`](../LICENSE),
[`pyproject.toml`](../pyproject.toml), [`CITATION.cff`](../CITATION.cff), and
[`.zenodo.json`](../.zenodo.json). Generated `output/` artifacts are intentionally
ignored, so a source checkout alone is not the source-current manuscript bundle.
No DOI record exists yet.

The manuscript itself is conditionally suitable for a narrowly scoped methods
submission, subject to the separate evidence boundaries in
[`PUBLICATION_READINESS.md`](../PUBLICATION_READINESS.md). P0 integrity,
expert-rater quality, and production acceptance remain unpromoted. Those open
scientific gates are independent of making the code repository public.

## Blocking decisions

- **Rights review:** confirm that the author/rights holder can redistribute all
  code and every bundled or archived artifact. MIT applies to THALIA code; it
  does not override rights for benchmark-derived data, model weights, raw
  answers, private-volume artifacts, or third-party figures and metadata.
- **Release authority:** select one exact commit as the release source, create an
  annotated version tag, and record the tag, commit digest, package version, and
  manuscript source digest in the release receipt.
- **Release bundle:** regenerate the source-current PDF/HTML, figures, dashboard,
  variables, manifests, test reports, coverage report, and clean-clone receipt.
  Do not upload private raw answers, annotations, credentials, or data whose
  redistribution rights have not been checked.
- **Public repository state:** make GitHub public only after the license,
  README, citation metadata, contribution/security contact, and release bundle
  are complete. Configure the release description and topics after the exact
  release tag exists.
- **Zenodo record:** create the Zenodo version from the exact GitHub tag, verify
  authorship, license, access rights, source archive, supplementary files, and
  DOI metadata, then record the minted DOI back in `CITATION.cff` and the README
  in a source-controlled follow-up.

## What the MIT decision covers

The source-controlled [`LICENSE`](../LICENSE) grants the standard MIT rights
for THALIA's authored source code. The decision does not certify that all files
in a future release bundle are authored by the project or legally redistributable.
Before publication, inventory the exact files included in the GitHub release
and Zenodo archive, record their provenance, and exclude or separately license
anything whose rights are not established. In particular, do not publish raw
answers, annotations, credentials, private external-volume data, or model
weights merely because the code is MIT-licensed.

## Recommended release sequence

1. Complete the MIT-scope and data/model redistribution review.
2. Run the full local test, lint, typing, package, artifact, and manuscript
   injection gates from the exact candidate commit.
3. Rebuild the rendered PDF/HTML and visually inspect the cover, new
   claim-ceiling figure, dense statistical figures, tables, references, and
   browser layout.
4. Build a clean-clone release receipt. Confirm that every claimed artifact is
   regenerated from the tag and that ignored output is copied into the release
   bundle intentionally.
5. Create the annotated version tag and GitHub release. Make the repository
   public only after the preceding checks pass and the publication authority
   explicitly approves that visibility change.
6. Archive that tagged release in Zenodo and verify the DOI landing page and
   downloadable archive.
7. Add the DOI to `CITATION.cff`, README, manuscript metadata, and the final
   release receipt; rerun the source-current validation on the follow-up commit.

No public release should imply a promoted model-quality, integrity-advantage,
or production-readiness result. The release notes should preserve the negative
controls and the current conditional wording.
