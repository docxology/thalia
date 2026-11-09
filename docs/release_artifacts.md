# Versioned release artifacts

THALIA software releases use an immutable annotated Git tag and the corresponding
[GitHub release](https://github.com/docxology/thalia/releases). The package,
current citation, manuscript version, and tag must agree. The version-specific
Zenodo DOI in the historical [v0.1.0 receipt](release_receipt.md) identifies that
archive only; a new GitHub version does not reuse or mint that DOI.

## Assembly boundary

Release only a reviewed, clean source tree after its PR checks pass and its
ordinary merge reaches `main`. Bind the final commit and Git tree, the renderer
commit and clean/dirty state, the runtime, and the exercised checks in the
release manifest. A pre-merge test result covers merged source only when the
Git trees are identical; do not silently qualify a changed tree.

Publish these assets together:

- The exact tagged Git source archive, retaining repository documentation,
  scripts, declared skills, and source-controlled research evidence.
- The Python wheel and source distribution built from that source. Install the
  wheel outside the checkout without the optional neural extra, then exercise
  both `thalia` and `thalia-benchmark`; an import or archive filename is not a
  consumer smoke check.
- The combined manuscript PDF and a curated supplemental artifact archive.
- A machine-readable release manifest with source identity and per-asset size
  and SHA-256, plus `SHA256SUMS` covering the downloadable payloads and manifest.

Generated `output/` remains ignored in Git. Supplemental assembly uses an
explicit allowlist, never an indiscriminate archive of the worktree or `output/`:

| Included | Boundary |
| --- | --- |
| Hydrated manuscript and bibliography | The exact 22 numbered source sections and resolved publication input |
| Combined and section HTML, dashboard | Preserve their relative `output/web/`, `output/figures/`, and dashboard paths and local assets |
| Registered PNG figures and registry | Authored plots and accessibility descriptions; no unrelated image files |
| Slide PDFs | The 22 rendered decks, not temporary TeX/auxiliary/cache files |
| Derived evaluation JSON and benchmark observations | Synthetic source-owned cohorts, explicit model provenance, metrics, and accounted failures |
| Verification, coverage, test, composition, audit, and artifact reports | Observed software checks, not expert-quality or production certification |
| Third-party license notices | Exact notices for bundled web-font bodies and renderer-derived runtime code |

The common-backend report includes generated answers to THALIA's own seeded
synthetic examples. It is not a redistribution of private conversations or raw
LongMemEval answers. Its validator reconstructs the cohort and checks the full
example/backend/method matrix, cohort seeds, execution schedule, source inventory,
and paired summaries before inclusion. No live cloud run is implied by a provider
adapter or the old unmatched cloud aggregate. Reports from the immutable v0.2
release retain schema 1; current method-aware reports use schema 2.

Exclude credentials, `.env`, virtual environments, caches, Git internals, model
weights, downloaded LongMemEval source, external-volume records, expert-rater
answers/annotations/adjudications, and unrelated generated files. Synthetic
per-example ledgers may be included only as such; model-quality private records
must not be swept into a release because they also have a JSON extension.

## Manifest ownership and the final staged-closure gate

v0.3.1 repairs an ownership collision discovered during canonical handoff.
THALIA and the native renderer previously wrote the same
`output/reports/artifact_manifest.json`. The native generic output scan replaced
THALIA's inventory, omitted the required committed
`data/integrity_advantage.json` because it is outside `output/`, and captured
QA/preview entries that were later changed or excluded from the supplement.
A native pass on the working tree was therefore not proof that the downloadable
closure passed THALIA's required-artifact contract.

Ownership is now explicit:

- `output/reports/thalia_artifact_manifest.json` is THALIA-owned. Its paths are
  relative to the project root, including the committed integrity aggregate.
- `output/reports/artifact_manifest.json` is native-owned. Do not copy it over,
  rename it into, or use it to repair the THALIA manifest.
- The downloadable release manifest binds the source identity, validation
  observations, and asset digests; it is not either artifact inventory.

Finish rendering, browser inspection, QA reports, preview selection, and all
source/documentation edits before the final freeze. Create a clean Git checkout
or worktree at the exact release commit, named `thalia` to match the retained
`thalia_combined.pdf`, then add only the supplemental allowlist at its original
relative paths. Native provenance requires a containing Git worktree boundary;
extracting a source tarball alone does not satisfy that admission requirement.
Retain committed inputs, especially `data/integrity_advantage.json`; the
supplement alone is not the complete project. Do not validate a full worktree
and then prune it into a different archive.

Use already-provisioned runtimes outside the staging tree. Set `THALIA_STAGE`
to that clean Git project root, `THALIA_PYTHON` to an absolute interpreter path
with THALIA's development dependencies, and `TEMPLATE_ROOT` to the absolute,
recorded template checkout path. From a shell:

```bash
set -e
cd "${THALIA_STAGE:?Set the clean staged project root}"
: "${THALIA_PYTHON:?Set the provisioned THALIA interpreter}"
: "${TEMPLATE_ROOT:?Set the provisioned template checkout}"
"$THALIA_PYTHON" -c \
  'from src.provenance import write_artifact_manifest; print(write_artifact_manifest())'
uv run --no-sync --project "$TEMPLATE_ROOT" python \
  scripts/render_pdf_external.py --template-root "$TEMPLATE_ROOT" \
  --validate-only
"$THALIA_PYTHON" scripts/validate_artifacts.py
```

`--template-root PATH` selects the real renderer checkout explicitly rather than
depending on staging-directory adjacency. `--validate-only` invokes its real
native validation pipeline without hydration or rerendering; it also fails if
THALIA's separate manifest is invalid. The last command repeats the full project
gate **after** native validation, catching missing required source inputs and
any native-side invalidation of THALIA's frozen entries.

Record actual statuses and report details in the v0.3.1 release manifest; do not
inherit earlier release counts. If a gate fails, fix the cause and repeat the
final inventory/native/project sequence. Never reseal or rewrite measured study
JSON to make it pass. After the final sequence, do not change any manifest-tracked
QA, preview, manuscript, figure, or data bytes. Native-owned diagnostics may be
written by validation, but must not be substituted for frozen THALIA evidence.
Package the exact verified closure without another render, dashboard build,
verification-summary refresh, QA annotation, or allowlist change. An intentional
tracked change requires a fresh final sequence before packaging.

Publish this repair under v0.3.1; retain the v0.3.0 tag and assets unchanged.
The original `STUDY_PRODUCER/` capsule remains the unreleased `41da836` producer
with a `0.3.0` wheel, not a v0.3.1 producer. Preserve its names and measured
report fingerprint; the patch qualifies the reader and release closure, not a
new model execution.

## Bundled web typography and runtime notices

`output/web/assets/source-web-fonts.js` carries twelve unmodified Liberation
2.1.5 font bodies: regular, italic, bold, and bold italic for Liberation Mono,
Sans, and Serif. All twelve embedded SHA-256 values and lengths must match the
renderer-owned `infrastructure/rendering/assets/fonts/liberation/provenance.json`.
The font name tables identify Google/Red Hat copyright and SIL Open Font License
1.1. Include the full renderer-held `OFL.txt` and provenance JSON in the
supplement's `THIRD_PARTY_LICENSES/`; the short font metadata is not a substitute
for the license text. [Upstream license](https://github.com/liberationfonts/liberation-fonts/blob/2.1.5/LICENSE).

The JavaScript contains the LZMA decoder's Nathan Rugg MIT notice; preserve it
verbatim. Include the template renderer's Apache-2.0 license for the copied
runtime wrapper as well. These notices do not change THALIA's MIT source license
or grant rights to other external research materials.

## Download verification and inspection

Download all assets into one empty directory and verify their bytes before
installation or extraction:

```bash
gh release download v0.3.1 --repo docxology/thalia
shasum -a 256 -c SHA256SUMS
```

Inspect the manifest's source commit against the tag and the release asset
names, lengths, and digests against GitHub's API. Extract the supplement without
flattening its directory layout; serve the extracted root locally to view the
HTML and dashboard with their figures and font asset. Browser-loaded external
services such as MathJax still require their declared network access; the
presence of local figures/fonts is not an offline certification of every
manuscript feature.

The downloadable manifest describes the allowlisted archive contents and source
identity independently of the two artifact inventories. Required paths can span
the source archive and supplement, so validate their combined staged closure as
described above. Software validation, PDF tagging, accessibility descriptions,
scientific acceptance, and independent PDF/UA certification are distinct claims.
