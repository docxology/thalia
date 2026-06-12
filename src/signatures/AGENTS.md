# `src/signatures/` — Agent contract

Barrel package: `from src.signatures import TaskCategory, HarnessOutput, …`

| Module | Contents |
|--------|----------|
| [`framework.py`](framework.py) | `Field`, `Signature`, `InputField`, `OutputField` |
| [`payloads.py`](payloads.py) | `TaskCategory`, `EvidenceWindow`, `HarnessOutput`, … |
| [`stages.py`](stages.py) | `InspectorSignature`, `RetrieverSignature`, `ReasonerSignature`, `MemoryGateSignature` |

Stage signature list fields use concrete types (`list[EvidenceWindow]`, etc.).
Validation remains presence-only via `Signature.validate_inputs`.
