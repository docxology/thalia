# Stage Contracts: From Transcript to Auditable Evidence {#sec:harness-method-contract-stage-flow}

## Method Contract and Typed I/O {#sec:method-contract}

Each harness invocation obeys the following contract:

1. **Evidence before inference.** Session history is converted into addressable
   lines before the Reasoner sees anything. Evidence windows retain source
   indices and snippets, so an answer can cite raw text with source-level
   provenance.
2. **Rank before answer.** The Retriever exposes ranked evidence and delivery
   mode. Inline answers are produced only after fusion and budgeting, and
   file-based overflow is an explicit output state recorded in the handoff.
3. **Answer before memory.** The Memory Gate receives a completed answer with
   citations and an explicit consolidation flag. The flag and the declared
   criterion jointly determine whether a memory update is eligible.
4. **Append before summarize.** Raw episodes are written first. Consolidated
   MEMORY.md deltas are derived artifacts; the source turn remains in the store.
5. **Optimize bounded surfaces.** The Compiler searches `HarnessConfig` values and
   bounded skill artifacts. Source code and manuscript narrative remain outside
   the search surface.

This contract is the practical bridge between the cited research and runnable
code. It converts DSPy-style declarations, RLM-style external context handling,
lexical-first retrieval, and gated memory into enforceable interfaces. It also
separates the variables that a model-quality study must keep distinct: evidence
reachability, evidence selection, answer generation, citation support, and memory
mutation. A passing handoff is a precondition for a useful answer. Answer quality
remains a separate outcome.

## Stage 0 — Inspector: RLM-Style Context Narrowing {#sec:stage-inspector}

The Inspector treats session history as external state. It loads the transcript
into a `REPLEnvironment`, peeks at structure, greps for query-anchored patterns,
ranks matching records by query-token overlap, and emits at most `max_windows`
compact `EvidenceWindow` objects with auditable `InspectorMetadata`. If grep
returns nothing it falls back to ranking every record; if the query contributes no
content tokens it keeps records in order. The full transcript remains external
state; only selected windows are eligible for a model call.

```python
class InspectorSignature(Signature):
    """Inspect session history as external state.
    Use code execution (peek / grep / partition) to filter evidence before
    forwarding selected windows to the Reasoner."""
    session_history: str = InputField("Raw session transcript (arbitrarily long).")
    query: str = InputField("Current task or question.")
    evidence_windows: list = OutputField("Compact snippets filtered from history.")
    metadata: InspectorMetadata = OutputField("Grep patterns, indices, confidence.")
```

This is the harness's defence against context rot: downstream stages see only
query-relevant windows, and `metadata.confidence` records the fraction of query
tokens the selected windows cover.

Two fallback paths are load-bearing. If grep returns no match, the Inspector ranks
all records by overlap and preserves a usable evidence set. If the query has no
usable content tokens, the Inspector preserves transcript order and avoids a
stop-word relevance signal. Both behaviours are
deterministic and tested.

## Stage 1 — Retriever: Lexical-First Hybrid Fusion {#sec:stage-retriever}

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
[@sen2026grep]. THALIA records delivery mode as part of the typed output, so
downstream diagnostics can separate a retrieval miss from a budget overflow.

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

## Stage 2 — Reasoner: Typed Answer Generation {#sec:stage-reasoner}

The Reasoner produces a typed answer with auditable citation support. Deterministic
code classifies the task (`src.routing.classify_task`), routes
multi-hop/code/knowledge-update tasks through a deterministic ReAct-style
read→integrate selection path, and uses one model completion for both routes. It
emits an auditable routing and evidence-use trace. It builds `EvidenceCitation`s from the
windows whose text overlaps the answer. The `evidence_citations` output is what
lets the Memory Gate audit answer-vs-evidence support, and what grounds any later
consolidation in verifiable raw text.
`requires_consolidation` is set only for knowledge-update tasks or explicit
"remember" cues.

The Reasoner is also where optional grounding verification occurs. When
`verify=True`, the stage computes a set-based answer-token support proxy against
the cited excerpts. This is a citation-support diagnostic. Atomic factual precision
requires the separate evaluation described by FActScore [@min2023factscore].
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
    reasoning_trace: str = OutputField("Auditable routing and evidence-use trace; hidden reasoning is excluded.")
    answer: str = OutputField("Final answer or action.")
    evidence_citations: list = OutputField("Raw source windows cited.")
    requires_consolidation: bool = OutputField("True for knowledge-update tasks or explicit memory cues.")
```

## Stage 3 — Memory Gate: Episodic-First Consolidation {#sec:stage-memory}

The Memory Gate enforces the consolidation-fault safeguard [@zhang2026memory] in
three steps: (1) **always** append the raw episode to the append-only
`EpisodicStore`; (2) compute explicit criteria — session end, novel task class, or
explicit user request; (3) consolidate a derived MEMORY.md delta when the
Reasoner requested it *and* a criterion holds. The source episode remains
available, and the delta cites its source turn so consolidated facts remain
traceable.

The gate is intentionally asymmetric: every turn can become evidence, while a
small subset can become a durable summary. This policy keeps conversational noise
out of long-lived memory and preserves the raw source for future recall. The
append-only store plus source-cited delta preserve both recall and auditability.

```python
class MemoryGateSignature(Signature):
    """Episodic-first memory management.
    Always write the raw episode. Consolidation requires requires_consolidation
    plus a criterion (novel task, session end, explicit request).
    Summaries are derived artifacts; raw episodes remain intact."""
    query: str = InputField("Current task or question.")
    answer: str = InputField("The produced answer.")
    evidence_citations: list = InputField("Citations from the Reasoner.")
    requires_consolidation: bool = InputField("Reasoner's consolidation flag.")
    session_episode_count: int = InputField("Episodes currently recorded in the store.")
    episodic_entry: EpisodicEntry = OutputField("Raw turn record to append.")
    consolidation_action: str = OutputField("none | append_memory | update_memory.")
    memory_delta: str = OutputField("Delta to MEMORY.md if consolidating, else ''.")
```

## Stage 4 — Compiler: Bounded Search and Evolution {#sec:stage-compiler}

The Compiler closes a bounded feedback loop over the `HarnessConfig` parameter
vector (retriever depth, evidence cap, RRF constant, lane weights, window cap,
token budget). The MIPRO-style compiler (`MIPROCompiler.compile`) evaluates each
candidate configuration against the harness metric and returns the best with a
full trace; an `auto` budget tier truncates the search space. The GEPA-style
optimizer (`GEPAOptimizer.evolve`) reflects on the weakest component of an
evaluation report (answer token-F1 / citation-support / efficiency) and applies a targeted,
bounded mutation — deepen retrieval when citation support is weak, emphasise lexical
matching when answer token-F1 is weak, tighten depth when efficiency is weak — recording
every candidate. Evolved skill artifacts must pass `check_skill_constraints`
(≤ 15 KB, non-empty), mirroring the Hermes self-evolution gates.

Because evaluation builds a *fresh* harness per example (`build_run_fn`), the
search is order-independent and reproducible: identical inputs yield the identical
winning configuration and trace.

The compiler trace is part of the method. It records the
candidate configuration, component scores, selected mutation, and resulting
configuration so a reader can tell whether an apparent improvement came from
answer token-F1, citation-support, or efficiency. On the current compact dataset the candidates
tie structurally; the trace documents that the declared search surface was
executed and that the reported optimum follows a deterministic tie rule. A
performance gain requires a dataset on which the candidate configurations separate.
