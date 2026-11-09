# THALIA docs

Agent- and reader-facing documentation hub. Start with [`quickstart.md`](quickstart.md).

| Doc | Purpose |
| --- | --- |
| [`quickstart.md`](quickstart.md) | Install, test, run a query, regenerate artifacts |
| [`architecture.md`](architecture.md) | The five stages, data flow, module boundaries |
| [`methods.md`](methods.md) | Algorithms and formulae (BM25, RRF, MMR, verification, recursion) |
| [`configuration.md`](configuration.md) | `HarnessConfig`, files, `THALIA_*` env, CLI precedence |
| [`backend_benchmark.md`](backend_benchmark.md) | Schema-2 backend/method CLI/API, migration, paired analysis and inference boundaries |
| [`local_method_study.md`](local_method_study.md) | Declared finite local plan, preserved original execution receipt and bounded statistical review |
| [`testing_philosophy.md`](testing_philosophy.md) | Zero-Mock policy, invariants, golden regression |
| [`glossary.md`](glossary.md) | Terms used across code and manuscript |
| [`provenance_p0.md`](provenance_p0.md) | Frozen, adjudicated provenance-confirmation protocol and promotion boundary |
| [`release_artifacts.md`](release_artifacts.md) | Exact staged inputs, consumer receipts, frozen archive assembly and download checks |
| [`release_readiness.md`](release_readiness.md) | Current version identity, publication gates and scientific non-promotion boundaries |

The full design rationale lives in [`manuscript/`](manuscript/); the
runnable, tested implementation lives in [`../src/`](../src).

## Task and evidence ownership

[`../tasks.yaml`](../tasks.yaml) is the canonical project/task-and-Gantt source,
managed by its native taskboard owner. Its declared statuses are `todo`,
`in_progress`, `blocked` and `done`; dates and progress accompany task identity,
dependencies and notes. [`../TODO.md`](../TODO.md) is a separate ergonomics
findings log, not a duplicate backlog or another task schema.

The generated THALIA dashboard is a research/verification view, not a taskboard.
Software release completion must not mark open expert-quality, integrity or
production-evidence tasks complete. External operator integrations must preserve
these native meanings through their owning contract rather than mass-rewriting
backlogs or treating Markdown checkboxes as equivalent release evidence.
