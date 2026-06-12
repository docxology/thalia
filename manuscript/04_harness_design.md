# Auto-Harness Design {#sec:harness_design}

ATLAS is organised around {{CONFIG_NUM_STAGES}} functional stages. Four are
runtime stages composed by `AutoHarness` (`src/harness.py`); the fifth, the
Compiler, operates on the harness offline. Each stage is a
`src.module.Module` with a declarative `src.signatures.Signature` contract. The
end-to-end flow:

```text
session history + query
  ─► Stage 0  Inspector    RLM-style context narrowing  (peek → grep → windows)
  ─► Stage 1  Retriever    lexical-first hybrid + weighted RRF + budgeting
  ─► Stage 2  Reasoner     typed reasoning; CoT or ReAct; typed citations
  ─► Stage 3  MemoryGate   always append raw episode; gated consolidation
  ─► HarnessOutput
  ╌► Stage 4  Compiler     (offline) MIPRO search + GEPA reflective evolution
```

The language model is abstracted behind a one-method protocol
(`src.module.LMClient.complete`), and the default `ExtractiveLM` returns the
evidence line with maximal lexical overlap with the question. Every stage below is
therefore deterministic and testable without a network.

The design is deliberately conservative about where judgment can enter. Stages
0–1 are retrieval and filtering functions; Stage 2 is the only possible
language-model boundary; Stage 3 is a storage and consolidation policy; Stage 4
is an offline optimizer. This separation lets the evaluation attribute failures:
an absent citation is a retrieval/Inspector problem, an unsupported answer is a
Reasoner problem, a spurious MEMORY.md change is a Memory Gate problem, and a
non-reproducible compiled configuration is a Compiler problem. The manuscript,
tests, and dashboard all report these same typed objects rather than post-hoc
natural-language summaries.

## Method contract {#sec:method-contract}

Each harness invocation obeys the following contract:

1. **Evidence before inference.** Session history is converted into addressable
   lines before the Reasoner sees anything. Evidence windows retain source
   indices and snippets, so an answer can cite raw text rather than a lossy
   summary.
2. **Rank before answer.** The Retriever exposes ranked evidence and delivery
   mode. Inline answers are produced only after fusion and budgeting, and
   file-based overflow is an explicit output state rather than a hidden failure.
3. **Answer before memory.** The Memory Gate receives a completed answer with
   citations and an explicit consolidation flag. It cannot invent a memory update
   from context alone.
4. **Append before summarize.** Raw episodes are written first. Consolidated
   MEMORY.md deltas are derived artifacts, never replacements for the source turn.
5. **Optimize bounded surfaces.** The Compiler searches `HarnessConfig` values and
   bounded skill artifacts. It does not mutate source code or rewrite the
   manuscript narrative.

This contract is the practical bridge between the cited research and runnable
code. It converts DSPy-style declarations, RLM-style external context handling,
lexical-first retrieval, and gated memory into enforceable interfaces.

## Stage 0 — Inspector (RLM-style context narrowing) {#sec:stage-inspector}

The Inspector treats session history as external state. It loads the transcript
into a `REPLEnvironment`, peeks at structure, greps for query-anchored patterns,
ranks matching records by query-token overlap, and emits at most `max_windows`
compact `EvidenceWindow` objects with auditable `InspectorMetadata`. If grep
returns nothing it falls back to ranking every record; if the query contributes no
content tokens it keeps records in order. The full context is never forwarded.

```python
class InspectorSignature(Signature):
    """Inspect session history as external state.
    Use code execution (peek / grep / partition) to filter evidence before
    forwarding. Never load the full context into the neural call."""
    session_history: str = InputField("Raw session transcript (arbitrarily long).")
    query: str = InputField("Current task or question.")
    evidence_windows: list = OutputField("Compact snippets filtered from history.")
    metadata: InspectorMetadata = OutputField("Grep patterns, indices, confidence.")
```

This is the harness's defence against context rot: downstream stages see only
query-relevant windows, and `metadata.confidence` records the fraction of query
tokens the selected windows cover.

Two fallback paths are load-bearing. If grep returns no match, the Inspector ranks
all records by overlap rather than emitting an empty evidence set; this keeps the
Reasoner from treating retrieval absence as proof of absence. If the query has no
usable content tokens, the Inspector preserves transcript order; this is safer
than manufacturing a relevance signal from stop words. Both behaviours are
deterministic and tested.

## Stage 1 — Retriever (lexical-first hybrid, RRF fusion) {#sec:stage-retriever}

The Retriever ranks Inspector windows with two lanes and fuses them. The lexical
lane is Okapi BM25 (`src/retrieval/lexical.py`); the semantic lane is a
deterministic hashing-embedding cosine (`src/retrieval/semantic.py`). Ranked lists
merge by weighted Reciprocal Rank Fusion [@cormack2009rrf] — contribution
$w/(k+r+1)$ for a chunk at 0-based rank $r$ in a lane of weight $w$, with defaults
$k = {{CONFIG_RRF_K}}$, lexical weight {{CONFIG_LEXICAL_WEIGHT}}, semantic weight {{CONFIG_SEMANTIC_WEIGHT}}. Lane weights are
**harness-conditioned**: temporal/single-session queries weight lexical higher,
preference/knowledge-update queries lean more on the semantic lane. Sparse context
budgeting sets `delivery_mode` to `INLINE` when the selected evidence fits
`context_budget_tokens` and `FILE_BASED` otherwise.

The Retriever therefore exposes both *what* was selected and *why that selection
fits the delivery path*. This matters because the agentic-search literature shows
that inline and programmatic/file-based delivery are different regimes
[@sen2026grep]. ATLAS does not collapse them into one hidden prompt-building step:
the delivery mode becomes part of the typed output, and downstream diagnostics can
separate a retrieval miss from a budget overflow.

```python
class RetrieverSignature(Signature):
    """Rank evidence using hybrid lexical + semantic search.
    Prefer lexical anchors for literal witnesses; semantic fallback for
    paraphrases. Apply weighted RRF and sparse context budgeting."""
    evidence_windows: list = InputField("Windows emitted by the Inspector.")
    query: str = InputField("Current task or question.")
    task_category: TaskCategory = InputField("Detected task category.")
    context_budget_tokens: int = InputField("Max tokens for inline injection.")
    ranked_evidence: list = OutputField("Top-k evidence after RRF fusion.")
    delivery_mode: DeliveryMode = OutputField("inline if within budget, else file_based.")
```

## Stage 2 — Reasoner (typed declarative reasoning) {#sec:stage-reasoner}

The Reasoner produces a grounded, typed answer. Deterministic code classifies the
task (`src.routing.classify_task`), routes multi-hop/code/knowledge-update tasks through a
ReAct-style read→integrate loop and everything else through chain-of-thought, and
builds `EvidenceCitation`s from the windows whose text overlaps the answer. The
`evidence_citations` output is what lets the Memory Gate audit answer-vs-evidence
grounding, and what grounds any later consolidation in verifiable raw text.
`requires_consolidation` is set only for knowledge-update tasks or explicit
"remember" cues.

The Reasoner is also where optional grounding verification occurs. When
`verify=True`, the stage computes answer-token support against the cited excerpts.
If support falls below `grounding_threshold`, it re-answers over the full ranked
evidence set and records the before/after scores in the trace. Verification is
off by default because the deterministic local evaluation already exercises the
baseline path; it is available as an operational guardrail when a real LM adapter
is inserted.

```python
class ReasonerSignature(Signature):
    """Reason over pre-filtered evidence to produce a structured answer.
    Deterministic code handles selection and routing; the model handles only
    judgment. Typed outputs prevent downstream parsing failures."""
    query: str = InputField("Current task or question.")
    ranked_evidence: list = InputField("Ranked evidence from the Retriever.")
    task_category: TaskCategory = InputField("Detected task category.")
    memory_context: MemorySnapshot = InputField("Frozen MEMORY/USER snapshot (read-only).")
    reasoning_trace: str = OutputField("Chain of thought grounded in evidence.")
    answer: str = OutputField("Final answer or action.")
    evidence_citations: list = OutputField("Raw source windows cited.")
    requires_consolidation: bool = OutputField("True only on novel class / explicit update.")
```

## Stage 3 — Memory Gate (episodic-first, gated consolidation) {#sec:stage-memory}

The Memory Gate enforces the consolidation-fault safeguard [@zhang2026memory] in
three steps: (1) **always** append the raw episode to the append-only
`EpisodicStore`; (2) compute explicit criteria — session end, novel task class, or
explicit user request; (3) **only** consolidate a derived MEMORY.md delta when the
Reasoner requested it *and* a criterion holds. Raw episodes are never overwritten;
the delta cites its source turn so consolidated facts remain traceable.

The gate is intentionally asymmetric: every turn can become evidence, but only a
small subset can become durable summary. That asymmetry prevents two common
failures. First, conversational noise does not automatically become long-lived
memory. Second, a compressed memory line never becomes the only surviving source
for a future answer. The append-only store plus source-cited delta preserve both
recall and auditability.

```python
class MemoryGateSignature(Signature):
    """Episodic-first memory management.
    ALWAYS write the raw episode. ONLY consolidate when requires_consolidation is
    True AND a criterion holds (novel task, session end, explicit request).
    NEVER overwrite raw episodes — summaries are derived artifacts."""
    query: str = InputField("Current task or question.")
    answer: str = InputField("The produced answer.")
    evidence_citations: list = InputField("Citations from the Reasoner.")
    requires_consolidation: bool = InputField("Reasoner's consolidation flag.")
    session_episode_count: int = InputField("Episodes recorded this session.")
    episodic_entry: EpisodicEntry = OutputField("Raw turn record to append.")
    consolidation_action: str = OutputField("none | append_memory | update_memory.")
    memory_delta: str = OutputField("Delta to MEMORY.md if consolidating, else ''.")
```

## Stage 4 — Compiler (MIPRO search + GEPA evolution) {#sec:stage-compiler}

The Compiler closes a bounded feedback loop over the `HarnessConfig` parameter
vector (retriever depth, evidence cap, RRF constant, lane weights, window cap,
token budget). The MIPRO-style compiler (`MIPROCompiler.compile`) evaluates each
candidate configuration against the harness metric and returns the best with a
full trace; an `auto` budget tier truncates the search space. The GEPA-style
optimizer (`GEPAOptimizer.evolve`) reflects on the weakest component of an
evaluation report (accuracy / grounding / efficiency) and applies a targeted,
bounded mutation — deepen retrieval when grounding is weak, emphasise lexical
matching when accuracy is weak, tighten depth when efficiency is weak — recording
every candidate. Evolved skill artifacts must pass `check_skill_constraints`
(≤ 15 KB, non-empty), mirroring the Hermes self-evolution gates.

Because evaluation builds a *fresh* harness per example (`build_run_fn`), the
search is order-independent and reproducible: identical inputs yield the identical
winning configuration and trace.

The compiler trace is part of the method, not a logging nicety. It records the
candidate configuration, component scores, selected mutation, and resulting
configuration so a reader can tell whether an apparent improvement came from
accuracy, grounding, or efficiency. On the current compact dataset the candidates
tie structurally; the trace still proves that the search surface was exercised and
that the reported optimum is a deterministic tie-break rather than a hidden
performance gain.

## Formalism {#sec:formalism}

The retrieval lanes and fusion are exact, parameterised functions.

**BM25 (lexical lane)** [@robertson2009bm25]**.** For query $q$ and document $d$ with term frequency
$f(t,d)$, document length $|d|$, mean length $\overline{d}$, and corpus size $N$:

\begin{equation}
\label{eq:bm25}
\mathrm{BM25}(q,d) = \sum_{t \in q} \mathrm{idf}(t)\,
\frac{f(t,d)\,(k_1+1)}{f(t,d) + k_1\!\left(1 - b + b\,\tfrac{|d|}{\overline{d}}\right)},
\quad
\mathrm{idf}(t) = \ln\!\left(1 + \frac{N - n_t + 0.5}{n_t + 0.5}\right)
\end{equation}

with defaults $k_1={{CONFIG_BM25_K1}}$, $b={{CONFIG_BM25_B}}$, and $n_t$ the number of documents containing
$t$. The $+1$ inside the logarithm keeps $\mathrm{idf}(t) \ge 0$ (an invariant
checked at runtime, [@sec:validation]).

**Weighted Reciprocal Rank Fusion.** For a chunk $c$ at 0-based rank $r_\ell(c)$
in lane $\ell$ of weight $w_\ell$ (lexical ${{CONFIG_LEXICAL_WEIGHT}}$, semantic ${{CONFIG_SEMANTIC_WEIGHT}}$):

\begin{equation}
\label{eq:rrf}
\mathrm{RRF}(c) = \sum_{\ell} \frac{w_\ell}{k + r_\ell(c) + 1}, \qquad k = {{CONFIG_RRF_K}}.
\end{equation}

**Maximal Marginal Relevance (diversity re-ranking).** Given fused relevance
$\mathrm{rel}(\cdot)$ (min-max normalised) and embedding cosine similarity
$\mathrm{sim}(\cdot,\cdot)$, MMR greedily selects

\begin{equation}
\label{eq:mmr}
\mathrm{MMR}(i) = \lambda\,\mathrm{rel}(i) - (1-\lambda)\,\max_{j \in S}\mathrm{sim}(i,j),
\end{equation}

where $S$ is the set already selected. $\lambda = 1$ recovers the fusion order
([@sec:validation] checks this); $\lambda \to 0$ maximises novelty. ATLAS exposes
$\lambda$ as `mmr_lambda` and the strategy as `rerank` ([@sec:operability]).

## Added methods {#sec:added-methods}

Six methods extend the base pipeline, each off by default and configurable:

- **Recursive partitioning (Inspector).** For contexts exceeding
  `partition_threshold` records, the Inspector performs the RLM "partition + map"
  step: it chunks records into blocks of `partition_size`, scores each block by
  summed per-record query overlap, keeps the top blocks, and only then runs the
  fine-grained grep+rank within them. This is depth-1 recursion — a coarse pass
  over blocks followed by a fine pass over records.

- **MMR diversity re-ranking (Retriever).** With `rerank = "mmr"`, the top-$k$ is
  selected from the *full* fused pool by [@eq:mmr] rather than by truncating the
  fusion order, demoting near-duplicate windows so the evidence budget carries
  more distinct facts.

- **Grounding verification (Reasoner).** With `verify = True`, the Reasoner
  computes the fraction of answer tokens supported by the cited excerpts; if it
  falls below `grounding_threshold`, it re-answers over the full evidence set (the
  RLM "verify" step) and records both grounding scores in the trace.

- **Query expansion — PRF (Retriever).** With `query_expansion = True`, an initial
  BM25 pass mines the most frequent content terms $T$ from the top windows and
  augments the query, $q' = q \cup T$ (RM3-style pseudo-relevance feedback). The
  expanded query is always a superset of the original ([@sec:validation]).

- **Recency weighting (Retriever).** For task classes where newer turns dominate,
  `recency_weight` $\rho \in [0,1]$ adds a position bonus to the fused score,
  $s'(i) = s(i) + \rho\, s_{\max}\,\tfrac{\mathrm{pos}(i)}{\mathrm{pos}_{\max}}$ for
  session windows (recalled windows are exempt). $\rho = 0$ is a strict no-op.

- **Memory recall (harness).** With `recall_memory = True`, the harness searches its
  append-only episodic store and the MEMORY.md snapshot for query-relevant content
  and injects it as evidence windows (negative source indices). This is the only
  path that consults stored memory at inference, closing the loop between the
  Memory Gate ([@sec:stage-memory]) and reasoning; it is strictly read-only.

## Implementation-to-method traceability {#sec:method-traceability}

The methods above are intentionally named the same way in code, tests, and
generated artifacts. `src/signatures/` defines the payloads; `src/stages/` and
`src/compiler/` implement the contract; `src/evaluation/` constructs the fixed
dataset and diagnostic bundle; `src/figures.py` renders the figures; and
`src/manuscript_variables.py` emits the manuscript numbers. The project-local
scripts are thin orchestrators around those modules. This traceability keeps the
paper from drifting into a design essay: every named method has a code path, a
test path, and, where applicable, a figure or generated token.
