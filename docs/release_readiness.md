# Public GitHub and Zenodo release readiness

_Review refreshed 2026-08-02._ This checklist separates a manuscript submission
decision from the authority required to publish a public software release.

## Decision at this checkout

The project is **not yet ready for a public GitHub or Zenodo release**.

The current GitHub repository is private, has no release tag, and has no selected
software license. Generated `output/` artifacts are intentionally ignored, so a
source checkout alone is not the source-current manuscript bundle. The repository
now carries a valid citation-metadata starting point in [`CITATION.cff`](../CITATION.cff),
but it must not be treated as a DOI or license declaration.

The manuscript itself is conditionally suitable for a narrowly scoped methods
submission, subject to the separate evidence boundaries in
[`PUBLICATION_READINESS.md`](../PUBLICATION_READINESS.md). P0 integrity,
expert-rater quality, and production acceptance remain unpromoted. Those open
scientific gates are independent of making the code repository public.

## Blocking decisions

- **License and rights:** choose a software license with the author/rights
  holder. Review the license and redistribution terms for bundled figures,
  benchmark-derived data, model metadata, and any external-volume artifacts.
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

## Recommended release sequence

1. Resolve the license and data/model redistribution review.
2. Run the full local test, lint, typing, package, artifact, and manuscript
   injection gates from the exact candidate commit.
3. Rebuild the rendered PDF/HTML and visually inspect the cover, new
   claim-ceiling figure, dense statistical figures, tables, references, and
   browser layout.
4. Build a clean-clone release receipt. Confirm that every claimed artifact is
   regenerated from the tag and that ignored output is copied into the release
   bundle intentionally.
5. Create the annotated version tag and GitHub release. Make the repository
   public only after the preceding checks pass.
6. Archive that tagged release in Zenodo and verify the DOI landing page and
   downloadable archive.
7. Add the DOI to `CITATION.cff`, README, manuscript metadata, and the final
   release receipt; rerun the source-current validation on the follow-up commit.

No public release should imply a promoted model-quality, integrity-advantage,
or production-readiness result. The release notes should preserve the negative
controls and the current conditional wording.
