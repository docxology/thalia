# Methods: Executable Contracts and Evidence Boundaries

Deterministic-core methods below are unit-tested and formally specified. Equations
appear in `manuscript/04b_harness_formalism_and_added_methods.md`; the machine-
checked registry at `data/paper_audit.yaml` is the implementer's view of the same
contracts.

## Method contract

THALIA treats a harness run as a typed dataflow rather than a prompt call. The
contract is:

1. preserve raw session evidence;
2. narrow context with line-addressed operations;
3. rank evidence with transparent lexical and surrogate-semantic scores;
4. answer with typed citations;
5. append the raw episode before any derived memory update; and
6. optimize only bounded configuration and skill artifacts.

The implementation mirrors that contract: `src/signatures/` defines payloads and
stage I/O, `src/stages/` implements runtime stages, `src/memory/` owns persistence,
`src/compiler/` owns offline optimization, and `src/evaluation/` owns the fixed
dataset plus diagnostics. Scripts call these modules; they do not contain method
logic.

## Formalism-to-code contract

`src/formalism_traceability.py` validates every registered formal object against
the Python AST, its test files, and its manuscript equation/section anchors. The
generated `output/reports/formalism_traceability.json` is required by the artifact
manifest, and the manuscript injects the same registry as a table. This gives each
equation a resolvable code symbol and each composition edge an explicit relation;
it does not elevate a finite synthetic result into a population claim.

## Visual evidence contract

Figures are part of the method surface, not decorative output. Architectural
figures use deterministic vector glyphs to make each stage's operation visible:
scan/narrow, rank/fuse, verify/answer, and append/gate. Quantitative diagnostics
derive their annotations from the same aggregate values as the bars or lines: the
evidence funnel reports retention at each boundary, and the pipeline-flow plot
marks every ranked-to-cited gap. This keeps visual emphasis tied to inspectable
evidence while preserving the two scope boundaries: extractive answer limits and
the hashing semantic surrogate are labelled where they matter.

## Lexical lane — BM25 (`src/retrieval/lexical.py`)

Okapi BM25 with the code constants `DEFAULT_K1` and `DEFAULT_B`. idf uses the
`+1`-inside-log form so values stay non-negative
(`invariants.check_bm25_idf_nonnegative`). `grep(docs, patterns)`
returns indices matching any regex; `extract_key_phrases(query)` drops stop-words
and short tokens to derive grep anchors.

The lexical lane is intentionally first-class because many agent-memory tasks ask
for literal witnesses: a password, a project path, an error string, or a quoted
preference. In these cases the right failure mode is a visible miss, not a
plausible paraphrase. BM25 produces a score vector over the Inspector windows,
while grep supplies a high-precision prefilter when query tokens are useful. Ties
are deterministic, and zero-score documents are excluded from top-k results.

## Semantic lane — hashing embedding (`src/retrieval/semantic.py`)

`embed(text)` hashes character 3-grams (SHA-1) into a fixed-dim L2-normalised
vector; `cosine` compares them. This is a **deterministic sub-word surrogate**, not
a learned dense retriever — swap in any embedder with the same `top_k(query, k)`
contract. The lexical-vs-dense magnitude of the agentic-search study is therefore
not reproduced locally (stated in the manuscript).

The surrogate exists for method isolation. It gives the Retriever a second ranking
lane, exercises fusion, budgeting, and ablation logic, and stays byte-stable across
runs. It should not be interpreted as semantic understanding. Learned embeddings
belong behind the same `SemanticIndex.top_k(query, k)` interface, where they can be
evaluated without changing the Inspector, Reasoner, Memory Gate, or Compiler.

## Fusion — weighted RRF (`src/retrieval/fusion.py`)

`rrf_fuse` sums `w / (k + rank + 1)` per lane. Ranks are zero-based, duplicate
IDs keep their first lane occurrence, and the ordering key is fixed-precision
rounded before ties break on ascending ID (deterministic).

The Retriever also applies harness-conditioned lane weights. Literal,
single-session, and temporal tasks favour lexical evidence; preference and
knowledge-update tasks give the surrogate-semantic lane more weight because
surface wording can drift across turns. The configured explicit weights still win
when supplied. This makes routing a transparent retrieval prior rather than a
hidden prompt instruction.

## Diversity — MMR (`src/retrieval/mmr.py`)

`mmr_rerank(ranked, lambda_, k)` greedily trades relevance against novelty.
`lambda_=1` recovers fusion order (`invariants.check_mmr_lambda1_preserves_relevance`);
lower values demote near-duplicates. Enabled by `rerank="mmr"`.

## Inspector recursion (`src/stages/inspector.py`)

For contexts above `partition_threshold` records, `_coarse_block_filter` partitions
into `partition_size` blocks, scores each by summed query overlap, and keeps the
top blocks before fine-grained grep+rank — the RLM "partition + map" step.

The Inspector records the selected grep patterns, selected indices, and confidence
metadata. Its fallback path is deliberately conservative: if no lexical anchor
matches, it ranks all records instead of returning an empty context. If the query
contains no useful content tokens, it preserves input order. These paths are tested
because they define how the harness behaves under ambiguous or underspecified
queries.

## Reasoner routing & verification (`src/stages/reasoner.py`)

`src.routing.classify_task` routes multi-hop/code/knowledge-update tasks through a
deterministic ReAct-style read→integrate selection path and uses one model
completion for both routes. With `verify=True`, the Reasoner measures a set-based
answer-in-evidence support proxy and re-answers over the current ranked evidence
set if it falls below `grounding_threshold`; this is not entailment or factuality.

The Reasoner is the only stage that can use an LM. By default it uses
`ExtractiveLM`, which selects the evidence line with maximal lexical overlap. Real
model adapters implement the same one-method protocol and are opt-in. The output
is still typed: answer, task category, reasoning trace, citations, and
`requires_consolidation`. Downstream stages never parse free-form prose to decide
whether memory should change.

## Memory gate (`src/memory/`)

`EpisodicStore` is append-only SQLite (+FTS5 when available). `decide_action`
consolidates a derived MEMORY.md delta only when the Reasoner flag **and** an
explicit criterion (session end, novel class, explicit request) both hold.

This is the operational response to consolidation faults. The raw episode is the
audit source; MEMORY.md is only a derived cache. A user can therefore inspect or
recompute a memory delta from the original turn instead of trusting a compressed
summary as the only surviving record.

## Compiler (`src/compiler/`)

`MIPROCompiler.compile` evaluates a candidate `HarnessConfig` grid against the
composite metric. `GEPAOptimizer.evolve` reflects on the weakest metric component
and applies a bounded mutation, recording every candidate. Evolved skill artifacts
must pass `check_skill_constraints` (≤ 15 KB, non-empty).

The compiler optimizes the harness surface, not the manuscript. MIPRO-style search
changes depth, evidence budget, lane weights, and related configuration. GEPA-style
evolution proposes bounded mutations based on metric components and records a
trace. Skill artifacts are checked for size and non-emptiness before they can be
treated as evolved capabilities.

## Adaptive retrieval & memory recall (off by default)

- **Query expansion — PRF (`src/retrieval/expansion.py`).** `query_expansion=True`
  runs an initial BM25 pass, mines the most frequent content terms from the top
  windows, and appends them to the query (RM3-style pseudo-relevance feedback).
  Deterministic; the expanded query is a superset of the original
  (`invariants.check_query_expansion_superset`).
- **Recency weighting (`src/stages/retriever.py::_apply_recency`).**
  `recency_weight ∈ (0,1]` adds a bonus to later session turns scaled by the top
  fused score, then re-sorts. `0` (default) is a strict no-op
  (`invariants.check_recency_zero_is_noop`); recalled (negative-index) windows are
  exempt.
- **Memory recall (`src/recall.py`).** `recall_memory=True` makes the harness search
  its append-only episodic store and the MEMORY.md snapshot for query-relevant
  content and inject it as evidence windows (negative source indices, so citations
  never collide with session indices). It is **read-only**
  (`invariants.check_recall_is_readonly`) and the only path that consults stored
  memory at inference — closing the loop between the Memory Gate and reasoning.

`evaluation.method_ablation` reports the composite for base + each method + all
combined (visualised by `figures.plot_method_ablation`). The research audit
evaluates lexical-only, surrogate-semantic-only, and hybrid retrieval on the same
examples across the sizes and fixed seeds declared in the generated
`output/data/eval_results.json` bundle. That accounting distinguishes unique
examples from method evaluations and records four balanced strata (literal
lexical, semantic/paraphrase, noisy long context, and multi-hop/update). Means use
within-stratum bootstrap intervals; seed
clusters are resampled separately for cluster-aware precision checks. Binary
outcomes use Wilson intervals and exact McNemar tests, and one named Holm family
spans every sample-size row plus its overall and stratum-level paired method tests.
Every estimate records its
estimand, unit, strata, cluster count, seed, and resample provenance. These are
uncertainty descriptions for a synthetic machinery benchmark, not population
claims.

The ledger is the accounting unit: each row has a global sequence number, stable
example ID, category/stratum, seed, method, metric components, status, error class,
and dataset/config fingerprints. The event stream repeats the fingerprints on
every sample event and contains only deterministic sequence fields; no wall-clock
values are used. The dashboard distinguishes unique examples from method
evaluations so paired method rows cannot be mistaken for additional independent
observations. Live neural and learned-retrieval plots add paired deltas, confidence
bands, Wilson intervals, model digests, generation options, and embedding prefixes
when the committed recorder aggregates provide them. Captions state whether a
visual is a deterministic regression, a synthetic diagnostic, or a model-dependent
probe.

## Provenance and artifact integrity (`src/provenance.py`)

Generators write a deterministic manifest over the current output data, figures,
dashboard, verification summary, evaluation accounting, event stream, and
per-example ledger. `validate_artifact_manifest` independently checks
relative-path safety, file size, SHA-256, and required artifact coverage from
`domain_profile.yaml`; malformed domain profiles fail closed. Model digests,
generation options, embedding prefixes, benchmark SHA-256/size, Python, and
platform are recorded as non-deterministic provenance metadata and are never used
as byte-identical neural regressions.

## Evaluation protocol (`src/evaluation/`)

`build_demo_dataset` defines a fixed LongMemEval-style dataset with one example
per task category. Each example includes session history, a query, a gold answer,
and expected source indices. `harness_metric` scores accuracy (token-F1),
grounding (expected source cited and answer supported by citations), and
efficiency (fewer evidence windows for the same answer). The evaluation bundle
then reports:

- default headline metrics;
- lexical / semantic / hybrid comparison under the slack default budget;
- tight-budget RRF, MMR, noise, and method-ablation diagnostics; and
- compiler search trace plus compiled configuration.

The six-example diagnostic remains intentionally small and deterministic. The
separate seeded scaling audit increases sample size while preserving reproducible
datasets and complete accounting of requested, evaluated, failed, category, and
seed counts. Together they validate composition, path hygiene, reproducibility,
dispersion, and paired method comparisons; they do not claim population-level
performance or reproduce learned-dense-retrieval results.

### Statistical estimands and uncertainty

The continuous estimand is the mean composite over the finite generated task
family. A unique example is the observation unit; the fixed seed is a design
cluster, not an additional independent replication. Marginal method summaries
resample within each declared difficulty stratum, retaining the observed stratum
sizes. Hybrid-versus-baseline comparisons are aligned on stable example IDs and
resample whole seed clusters, preserving within-seed pairing. The research figure
therefore displays paired delta intervals directly rather than subtracting two
marginal confidence limits. All randomized procedures receive explicit seeds and
serialize their resampling method, confidence level, unit, strata, cluster count,
and resample count. The bootstrap convention follows Efron's original
non-parametric formulation [@efron1979bootstrap].

Binary rates use Wilson score intervals [@wilson1927probable]. Paired binary
outcomes use the exact McNemar test [@mcnemar1947sampling], including the
zero-discordance case. The named Holm step-down family [@holm1979simple] is
assembled before adjustment and includes the overall and stratum-level paired
comparisons for every audited sample-size row. This protects the interpretation
of exploratory slices without pretending that a generated benchmark samples a
human population. The sample-size planner is a transparent precision heuristic,
not a prospective power calculation; the synthetic, external-benchmark, and
model-dependent evidence tiers remain separate.

## Composable Pipeline (`src/pipeline.py`)

`Pipeline` exposes the same four runtime stages as `AutoHarness` but as an
explicitly ordered, inspectable chain. Where `AutoHarness.forward` is a single
opaque call, a `Pipeline` is a list of `PipelineStep` objects executed in
insertion order. After `run()` returns, every intermediate context is available
via `pipeline.intermediates` — a list of `(step_name, PipelineContext)` snapshots,
one per step.

```python
from src.pipeline import Pipeline
from src.config import default_config

pipe = (
    Pipeline(default_config())
    .with_inspector()
    .with_retriever()
    .with_reasoner()
    .with_memory_gate()
)
result = pipe.run(query="What is the wifi password?", session_history="...")
print(result.answer)

# Inspect intermediates
for name, ctx in pipe.intermediates:
    print(name, len(ctx.evidence_windows))
```

### Relationship to `AutoHarness`

`Pipeline` reuses the exact same stage classes (`Inspector`, `Retriever`,
`Reasoner`, `MemoryGate`) and the same `HarnessConfig` defaults. Identical inputs
produce identical outputs in both paths — this is asserted by the invariant suite.
`AutoHarness` remains the recommended entry point for straightforward use; `Pipeline`
is for cases that need custom stage insertion, partial pipelines, or per-step
inspection.

### Builder methods

| Method | Effect |
| --- | --- |
| `with_inspector()` | Add Stage 0 (Inspector) |
| `with_retriever()` | Add Stage 1 (Retriever) |
| `with_reasoner()` | Add Stage 2 (Reasoner) |
| `with_memory_gate()` | Add Stage 3 (Memory Gate) |
| `with_all_stages()` | Shorthand for all four above |
| `add_step(name, fn)` | Insert a custom `PipelineContext → PipelineContext` step |

### `PipelineContext`

The mutable state bag threaded through the chain. Initial fields are `query` and
`session_history`; each stage enriches it (e.g. `evidence_windows`, `ranked_evidence`,
`answer`, `consolidation_action`). Custom steps may stash arbitrary data in
`ctx.extras` without interfering with built-in stage fields.
