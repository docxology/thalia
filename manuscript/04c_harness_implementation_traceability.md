# Traceability: Formal Objects, Code, Tests, and Evidence {#sec:harness-implementation-traceability}

## Implementation Symbols Mapped to Methods {#sec:method-traceability}

The method names form an executable vocabulary. The publication ledger
requires every formal object to declare its equation, implementation symbol,
test anchor, unit, estimand, dependencies, invariants, invariant-to-code/test
anchors, and manuscript section. The validator resolves Python symbols with the
AST, confirms test and section paths, checks equation labels, resolves every
invariant anchor, and validates the composition edges. A passing status means
that the declared references are resolvable. Scientific assumptions and population
validity require additional evidence.

The generated registry currently reports {{RESULT_FORMALISM_COUNT}} formal objects,
{{RESULT_TRACEABILITY_EDGE_COUNT}} composition edges, and {{RESULT_CLAIM_COUNT}}
audited claims (status: `{{RESULT_TRACEABILITY_STATUS}}`). The table is injected
from `data/paper_audit.yaml` and serialized as
`output/reports/formalism_traceability.json`; it is therefore regenerated with the
same command that hydrates all manuscript variables.

{{FORMALISM_TRACEABILITY_TABLE}}

## Composition Edges and Dataflow Semantics {#sec:formalism-composition}

The graph makes three different relations explicit. First, the Inspector's
lexical relevance and coarse partitioning define the candidate corpus presented to
BM25 and the hashing-cosine lane. Second, ranked candidates are fused, optionally
recency-adjusted and diversity-reranked, then passed through the evidence budget
contract. Third, answer token-F1, citation-support, and evidence-count efficiency
compose into the fixed per-example metric. These are dataflow dependencies. A
downstream score can support a causal claim only when a separately designed
intervention identifies the upstream component.

## From Code and Evidence to Source-Bound Prose {#sec:traceability-evidence}

`src/signatures/` defines typed payloads; `src/stages/` and `src/retrieval/`
implement the stage functions; `src/compiler/metrics.py` defines score components;
`src/evaluation/` constructs datasets, ledgers, and statistical summaries;
`src/figures/` renders figures from validated aggregates; and
`src/manuscript_variables.py` emits the quantitative tokens. The project scripts
remain thin orchestrators. Generated JSON, JSONL, figures, captions, and PDF are
downstream evidence artifacts, while the registry is the bridge that makes the
formalism-to-code relationship inspectable before rendering.

The evidence boundary remains explicit: deterministic contracts are tested locally;
synthetic evaluations describe the declared finite generated set; external
benchmark rows identify their input by size and SHA-256; and neural rows retain
model digests and generation options. A resolved anchor is necessary for
scholarship. Semantic validity, causal identification, and generalization require
their own evidence.
