# Validation and Invariants {#sec:validation}

THALIA treats correctness as a build-time property, not a hope. Three layers
enforce it: a Zero-Mock test suite, a set of executable invariants, and golden
regression tests — all deterministic.

The validation design follows the same typed boundaries as the method. Unit tests
exercise individual functions, stage tests exercise payload handoffs, regression
tests pin published metrics, and script smoke tests prove that the command surface
can regenerate the artifacts named in the manuscript. This is why the manuscript
can discuss Inspector windows, retrieval modes, Memory Gate actions, compiler
traces, and dashboard rows as the same objects that appear in code rather than as
parallel explanatory vocabulary.

## Executable invariants {#sec:val-invariants}

`src/invariants.py` encodes structural properties the harness must always satisfy
as runnable checks (each returns an :class:`InvariantResult`). The test suite
asserts every one passes, and the dashboard ([@sec:val-dashboard]) surfaces them:

- **bm25_idf_nonnegative** — every corpus term's idf is $\ge 0$ ([@eq:bm25]).
- **rrf_monotonic_in_rank** — within a lane, the fused score is non-increasing in
  rank ([@eq:rrf]).
- **rrf_agreement_boost** — a chunk top-ranked in both lanes outranks single-lane
  chunks.
- **embedding_determinism** — identical text embeds identically.
- **mmr_lambda1_is_relevance** — MMR with $\lambda=1$ reproduces the fusion order
  ([@eq:mmr]).
- **episode_append_only** — the episodic store rejects overwriting a turn id.
- **consolidation_gate_strict** — consolidation never fires on a flag alone or a
  criterion alone (both required).
- **harness_determinism** — the same query+history yields the same answer across
  fresh harnesses.
- **answer_grounded** — an answer cites at least one source window when evidence
  exists.

These invariants are not decorative. They are the executable minimum for the
architecture: BM25 must preserve non-negative idf; RRF must respect rank order and
agreement; MMR must reduce to relevance when requested; memory must remain
append-only; and answers must carry citations when evidence exists. If any of
those fail, the manuscript's methodological claims are no longer true.

## Zero-Mock test suite {#sec:val-tests}

Every test uses real computation — real BM25/embeddings, a real SQLite episodic
store, real temporary files, and a real in-process HTTP server for the Ollama
adapter (no `unittest.mock`, no `MagicMock`). Coverage on `src/` is gated at
{{CONFIG_COV_GATE}}% and the live suite runs well above it. Selecting a real fallback path (for example
toggling `fts_available` to exercise the `LIKE` search branch) is permitted because
it chooses a real branch; faking a call boundary is not.

The {{CONFIG_COV_GATE}}% gate covers the **deterministic core**. The optional real-DSPy and neural
paths (`src/dspy_runtime/`, the `dspy.Predict`/`BootstrapFewShot` glue, and the
real Gemma-via-Ollama backend) are exercised by genuine, `DSPY_AVAILABLE`- and
model-availability-gated tests (`tests/test_dspy_runtime.py::TestRealDspyRuntime`,
`TestRealNeuralDspy`) that run real dspy objects and a real model when present and
skip cleanly otherwise — so they sit *outside* the coverage gate by construction,
not for lack of testing. The gated figure shown in [@sec:eval-neural] is produced
from their recorded output.

The suite is intentionally organized by responsibility: retrieval files test
lexical, semantic, fusion, MMR, expansion, and recall; stage files test Inspector,
Retriever, Reasoner, Memory Gate, and harness orchestration; compiler files test
metrics, MIPRO-style search, and GEPA-style mutation; manuscript tests enforce
token coverage and stale-path hygiene. That organization keeps maintenance
pressure close to the method it protects.

## Golden regression {#sec:val-regression}

`tests/test_regression.py` pins the headline metrics (composite, grounding,
efficiency) and the published manuscript tokens to golden values within a tight
tolerance, and asserts that `run_full_eval()` and `generate_variables()` are
byte-identical across runs. It also pins the **noise-regime ordering** — under
session noise the hashing-surrogate semantic lane scores *above* the lexical and
hybrid lanes (composite {{RESULT_NOISE_SEMANTIC}} vs. {{RESULT_NOISE_LEXICAL}} at
{{RESULT_NOISE_MAX_DISTRACTORS}} distractors) — so the §evaluation prose that cites
that divergence cannot drift from the measured data. An unintended change to any
published number flips a golden assertion red before it can reach the manuscript.

## Memory recall, isolated {#sec:val-memory}

The episodic-first thesis gets a direct ablation rather than only unit tests. In
`src.evaluation.memory_recall_ablation`, a fact lives *only* in the append-only
episodic store — empty session history, empty MEMORY.md — and a natural-language
query recovers it ({{RESULT_MEMORY_RECALL_WINDOWS}} window) when the store is
present and recovers {{RESULT_MEMORY_NO_STORE_WINDOWS}} without it, isolating the
store as the load-bearing component for cross-context recall. This probe also
hardened a real defect: the store's FTS5 search passed the raw query to `MATCH`, so
an ordinary punctuated question ("What is the wifi password?") raised an
`fts5: syntax error`. Search now reduces queries to bare alphanumeric tokens (its
tokenizer's own alphabet), and a regression test exercises punctuation, hyphens, and
quotes so the recall path cannot silently break on natural-language input again.

## Negative results and robustness {#sec:val-negative}

A trustworthy evaluation reports what did *not* work as much as what did. Three
follow-ups returned honest nulls, stated plainly. **(i) Recency weighting does not
change the injection outcome:** re-running the context-poisoning probes
([@sec:eval-injection]) with `recency_weight` swept from 0 to 0.9 leaves the poisoned
answer unchanged — an overlap-dominated injection already wins regardless of recency,
so recency is neither a defence nor an added liability here. **(ii) Retrieval depth
does not change accuracy** on lexically clean tasks: sweeping `top_k`/`max_evidence`
leaves token-F1 flat (the gold line is recoverable at depth one) and only lowers the
efficiency term — exactly why the Compiler's optimum is an efficiency tie-break, not
an accuracy gain. **(iii) The lexical-anchored hybrid ties a real dense RAG:** a pure
neural-embedding retrieval baseline (`src.retrieval.learned.dense_rag_answer`,
nomic-embed-text) matches the harness's accuracy on the seeded set. A tie on this
deliberately easy set is the *expected* outcome — [@sec:eval-real] shows the synthetic
data cannot separate retrieval methods — so this is evidence of no regression, not of
general parity. Consistent with the no-harness baseline ([@sec:eval-baseline]), the
harness's value here is provenance and bounded context, not retrieval superiority.

Robustness is locked in by a property-based fuzz pass (`tests/test_fuzz.py`): hundreds
of adversarial inputs — random punctuation, SQL-like strings, injection markers,
field-delimiter tokens, empty and oversized sessions — run through the harness and the
FTS5-backed persistent session with **zero crashes** and no output-invariant
violations. That test is the standing regression guard for the class of edge-case bug
the earlier `fts5: syntax error` belonged to.

## Reproducibility integrity gates {#sec:val-integrity}

`tests/test_manuscript_integrity.py` enforces two structural contracts that keep
the reproducibility story honest. **Path hygiene**: no manuscript section or
shipped doc may reference a project path that no longer exists — a stale path
makes a documented `pytest` command collect zero tests and exit green, a silent
false pass the gate now forbids. **Injection-independent token coverage**: the
manuscript-variable generator locates the template root robustly even when THALIA
is checked out as a symlink *outside* the template tree, and its token-coverage
reproducibility contract completes whether or not the optional PDF-injection step
is reachable — the gate that guarantees every published number is a generated
token never depends on the renderer plumbing.

## Static visualization dashboard {#sec:val-dashboard}

`src/dashboard.py` renders a self-contained HTML page (no JavaScript, no
third-party dependency) embedding the headline metrics, the per-category
breakdown, the invariant pass/fail table, and the generated figures. It is built
by `scripts/build_dashboard.py` into `output/dashboard.html`. The renderer is a
pure function of its inputs and HTML-escapes all dynamic content, so it is both
testable and safe.

The dashboard is a compact audit surface rather than a separate analysis. It
shows the same metrics and figures used in this manuscript, alongside invariant
status, so a reviewer can move from prose to rendered diagnostic to JSON artifact
without needing to infer which run produced which number.

Before rendering, `scripts/validate_artifacts.py` adds a separate artifact gate:
the manifest must cover the required outputs in `domain_profile.yaml`, and every
recorded size and hash must still match the current file. This catches stale or
mutated figures and JSON that unit tests cannot see.
