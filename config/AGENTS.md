# AGENTS.md — thalia/config

`harness.yaml` — THALIA harness configuration, loaded by
`src/config.py::load_config`; every field maps to `HarnessConfig`; any
field can be overridden at runtime with a `THALIA_<FIELD>` env var
(e.g. `THALIA_TOP_K=4`). Lane weights are both-or-neither (both set, or
both null to use per-task-category defaults in the retriever stage).