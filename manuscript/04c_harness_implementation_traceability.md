# Harness Design: Implementation Traceability {#sec:harness-implementation-traceability}

## Implementation-to-method traceability {#sec:method-traceability}

The methods above are intentionally named the same way in code, tests, and
generated artifacts. `src/signatures/` defines the payloads; `src/stages/` and
`src/compiler/` implement the contract; `src/evaluation/` constructs the fixed
dataset and diagnostic bundle; `src/figures/` (plots, diagrams, manifest) renders the figures; and
`src/manuscript_variables.py` emits the manuscript numbers. The project-local
scripts are thin orchestrators around those modules. This traceability keeps the
paper from drifting into a design essay: every named method has a code path, a
test path, and, where applicable, a figure or generated token.
