# `src/signatures/` — THALIA signature framework

Typed input/output contracts for the harness stages: the lightweight `Signature`
framework, the shared payload types, and the per-stage signatures. Barrel
package — import from the package root: `from src.signatures import TaskCategory,
HarnessOutput, …`.

## Modules

| Module | Purpose |
|--------|---------|
| [`framework.py`](framework.py) | `Field`, `Signature`, `InputField`, `OutputField` |
| [`payloads.py`](payloads.py) | `TaskCategory`, `EvidenceWindow`, `HarnessOutput`, … |
| [`stages.py`](stages.py) | `InspectorSignature`, `RetrieverSignature`, `ReasonerSignature`, `MemoryGateSignature` |

Stage signature list fields use concrete element types
(`list[EvidenceWindow]`, …); validation remains presence-only via
`Signature.validate_inputs`.

## See Also

- [`AGENTS.md`](AGENTS.md) — agent contract for this package
- [`../README.md`](../README.md) — `src/` implementation overview
- [`../../docs/README.md`](../../docs/README.md) — project docs
