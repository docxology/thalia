# `docs/` — Agent contract

This folder is documentation only; no code executes here. When you change
behaviour in `src/`, update the matching doc:

| You changed… | Update… |
| --- | --- |
| A stage's algorithm or a formula | [`methods.md`](methods.md) + `manuscript/04_harness_design.md` |
| A `HarnessConfig` field, env var, or CLI flag | [`configuration.md`](configuration.md) + `config/harness.yaml` + `manuscript/10_operability.md` |
| The stage set or data flow | [`architecture.md`](architecture.md) + `manuscript/08_reference_architecture.md` |
| Test policy or an invariant | [`testing_philosophy.md`](testing_philosophy.md) + `manuscript/11_validation.md` |
| A new domain term | [`glossary.md`](glossary.md) |

Keep docs consistent with the code: every claim here must be checkable against
`src/` or a test. Do not introduce numbers here that are not generated tokens or
ledger-registered claims (see `data/claim_ledger.yaml`).
