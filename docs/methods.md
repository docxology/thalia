# Methods

Every method below is deterministic and unit-tested. Formal equations appear in
`manuscript/04_harness_design.md` (§Formalism); this is the implementer's view.

## Method contract

ATLAS treats a harness run as a typed dataflow rather than a prompt call. The
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

## Lexical lane — BM25 (`src/retrieval/lexical.py`)

Okapi BM25 with `k1=1.5`, `b=0.75`. idf uses the `+1`-inside-log form so values
stay non-negative (`invariants.check_bm25_idf_nonnegative`). `grep(docs, patterns)`
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

`rrf_fuse(lex, sem, k=60, lexical_weight=0.65, semantic_weight=0.35)` sums
`w / (k + rank + 1)` per lane. Ties break on ascending id (deterministic).

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

`src.routing.classify_task` routes multi-hop/code/knowledge-update tasks through a ReAct
read→integrate loop and others through chain-of-thought. With `verify=True`, the
Reasoner measures answer-in-evidence support and re-answers over the full evidence
set if it falls below `grounding_threshold`.

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
combined (visualised by `figures.plot_method_ablation`).

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

The protocol is intentionally small and deterministic. It validates composition,
path hygiene, and reproducibility; it does not claim population-level performance
or reproduce learned-dense-retrieval results.
