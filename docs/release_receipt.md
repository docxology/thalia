# THALIA v0.1.0 release receipt

This receipt records the public software release boundary independently of the
manuscript's scientific claim-promotion gates.

## Authority

- Version: `0.1.0`
- GitHub repository: <https://github.com/docxology/thalia>
- Annotated tag: `v0.1.0`
- Tagged commit: `ab6543c1b139a6ac4ca0b8a091b588384997bcf9`
- Zenodo DOI: [10.5281/zenodo.21763245](https://doi.org/10.5281/zenodo.21763245)
- Zenodo record: <https://zenodo.org/records/21763245>
- License for authored source code: [MIT](../LICENSE)

## Zenodo files

The three public files in the record were assembled from the tagged source and
the source-current generated outputs. Zenodo's MD5 checksums were independently
matched before publication; the SHA-256 values below provide a stronger local
receipt.

| File | Size (bytes) | SHA-256 |
| --- | ---: | --- |
| `thalia-0.1.0-source.tar.gz` | 842137 | `7bceffb89dca89cf7e28f4ea40bbe288094c07c4dd295a6b106dd549d8373753` |
| `thalia-0.1.0.pdf` | 5005902 | `063278d477bdfadf821e62f1719a0860ced187a458256e2e399b9a8e2715eede` |
| `thalia-0.1.0-artifacts.tar.gz` | 16736189 | `db25a4c61e43324d6d42bdb87a7d82324ff5498dce704581929d779dae483198` |

The artifact bundle contains the hydrated manuscript, combined HTML,
dashboard, figures and registry, slide PDFs, derived aggregate data, and
validation receipts. The source archive contains the exact tagged repository;
generated `output/` remains ignored in Git and is included only in the
intentional artifact bundle.

The release assembly excludes credentials and `.env` files, raw answers,
annotations, model weights, private external-volume records, and the raw
LongMemEval source file. MIT applies to the authored THALIA source and does not
grant third-party redistribution rights.

## Validation receipt

- Strict suite: 854 collected, 847 passed, 7 optional live-model skips.
- `src/` coverage: 90.49%, above the 90% gate.
- Artifact validator: `checked=47`, `required=43`, `ok=True`.
- Manuscript injection: 22 numbered sections, exact source-to-injected parity.
- Deterministic enlarged audit: 25,500 unique examples, 76,500 method
  evaluations, 10 seeded clusters, 2,000 resamples, zero failures.
- PDF: 72 pages, PDF 2.0, tagged, unencrypted; `qpdf --check` passed.
- DOI resolution: `https://doi.org/10.5281/zenodo.21763245` resolves to the
  public Zenodo record above.
- Clean public clone: cloning `v0.1.0` from GitHub resolved to the tagged
  commit, contained 261 tracked files, had zero worktree changes, and passed
  `uv lock --check`.

These checks establish software and reproducibility release integrity. They do
not promote model-quality, true-source-recovery, integrity-advantage, or
production-readiness claims; those remain conditional in
[`PUBLICATION_READINESS.md`](../PUBLICATION_READINESS.md).
