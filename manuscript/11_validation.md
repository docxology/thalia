# Validation: Invariants, Negative Controls, and Integrity Gates {#sec:validation}

THALIA treats tested contracts as a build-time property grounded in evidence.
Three layers check them: a Zero-Mock test suite, executable invariants, and golden
regression tests for the deterministic core. Optional live-model adapters use
separate model-dependent gates.

The validation design follows the same typed boundaries as the method. Unit tests
exercise individual functions, stage tests exercise payload handoffs, regression
tests pin published metrics, and script smoke tests demonstrate that the command
surface can regenerate the artifacts named in the manuscript. This is why the
manuscript can discuss Inspector windows, retrieval modes, Memory Gate actions,
compiler traces, and dashboard rows as the same objects that appear in code rather
than as parallel explanatory vocabulary. It validates the measurement
instrument. Lexical overlap remains the declared answer proxy; factuality and model
quality require their own outcomes.

The model-quality lane adds a separate fail-closed contract: deterministic pilot
and held-out partitioning, typed ordinal and binary annotations, blinded model and
condition packets, paired condition completeness, answer and provenance digests,
independent double rating, adjudication, calibration, question-clustered paired
statistics, and certificate-digest validation before promotion. The completed v2
campaign remains operational/provenance evidence; its answer hashes and automated
metrics retain that evidence tier. Production
readiness is tested by a separate operational acceptance gate.

## Executable Invariants and Property Checks {#sec:val-invariants}

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
- **consolidation_gate_strict** — consolidation fires only when the Reasoner flag
  and an explicit criterion are both present.
- **harness_determinism** — the same query+history yields the same answer across
  fresh harnesses.
- **answer_grounded** — an answer cites at least one source window when evidence
  exists.
- **query_expansion_superset** — pseudo-relevance feedback retains every original
  query token when adding terms.
- **recall_readonly** — episodic recall is read-only and leaves the append-only
  store unchanged.
- **recency_zero_noop** — the default zero recency weight preserves retriever
  order exactly; a non-zero weight is separately tested as an active branch.
- **static_determinism_guard** — deterministic-core source has no forbidden
  network, clock, model-SDK, or mock-framework boundary violations.

These invariants form the executable minimum for the
architecture: BM25 must preserve non-negative idf; RRF must respect rank order and
agreement; MMR must reduce to relevance when requested; memory must remain
append-only; and answers must carry citations when evidence exists. If any of
those fail, the manuscript's methodological claims are no longer true.

## Zero-Mock Test Suite {#sec:val-tests}

Every test uses real computation — real BM25/embeddings, a real SQLite episodic
store, real temporary files, and a real in-process HTTP server for the Ollama
adapter (no `unittest.mock`, no `MagicMock`). Coverage on `src/` is gated at
{{CONFIG_COV_GATE}}% and the live suite runs well above it. Selecting a real fallback path (for example
toggling `fts_available` to exercise the `LIKE` search branch) is permitted because
it chooses a real branch, so the test exercises the production boundary.

The {{CONFIG_COV_GATE}}% gate covers the **deterministic core**. The optional real-DSPy and neural
paths (`src/dspy_runtime/`, the `dspy.Predict`/`BootstrapFewShot` glue, and the
real Gemma-via-Ollama backend) are exercised by genuine, `DSPY_AVAILABLE`- and
model-availability-gated tests (`tests/test_dspy_runtime.py::TestRealDspyRuntime`,
`TestRealNeuralDspy`) that run real dspy objects and a real model when present and
skip cleanly otherwise — so they sit *outside* the coverage gate by construction;
their real tests run when the dependencies are available. The gated figure shown in [@sec:eval-neural] is produced
from their recorded output.

The suite is intentionally organized by responsibility: retrieval files test
lexical, semantic, fusion, MMR, expansion, and recall; stage files test Inspector,
Retriever, Reasoner, Memory Gate, and harness orchestration; compiler files test
metrics, MIPRO-style search, and GEPA-style mutation; manuscript tests enforce
token coverage and stale-path hygiene. That organization keeps maintenance
pressure close to the method it protects.

## Golden Regression and Determinism {#sec:val-regression}

`tests/test_regression.py` pins the headline metrics (composite, citation-support
proxy, efficiency) and the published manuscript tokens to golden values within a tight
tolerance, and asserts that `run_full_eval()` and `generate_variables()` are
byte-identical across runs. It also pins the **noise-regime ordering** — under
session noise the hashing-surrogate semantic lane scores *above* the lexical and
hybrid lanes (composite {{RESULT_NOISE_SEMANTIC}} vs. {{RESULT_NOISE_LEXICAL}} at
{{RESULT_NOISE_MAX_DISTRACTORS}} distractors) — so the §evaluation prose that cites
that divergence remains pinned to the measured data. An unintended change to any
published number flips a golden assertion red before it can reach the manuscript.

## Isolated Memory-Recall Validation {#sec:val-memory}

The episodic-first thesis gets a direct ablation alongside unit tests. In
`src.evaluation.memory_recall_ablation`, a fact lives *only* in the append-only
episodic store — empty session history, empty MEMORY.md — and a natural-language
query recovers it ({{RESULT_MEMORY_RECALL_WINDOWS}} window) when the store is
present and recovers {{RESULT_MEMORY_NO_STORE_WINDOWS}} without it, isolating the
store as the load-bearing component for cross-context recall. This probe also
hardened a real defect: the store's FTS5 search passed the raw query to `MATCH`, so
an ordinary punctuated question ("What is the wifi password?") raised an
`fts5: syntax error`. Search now reduces queries to bare alphanumeric tokens (its
tokenizer's own alphabet), and a regression test exercises punctuation, hyphens, and
quotes so the recall path remains protected for natural-language input.

## Null Results, Fallbacks, and Robustness {#sec:val-negative}

A trustworthy evaluation records null results alongside positive findings. Three
follow-ups returned clear nulls. **(i) Recency weighting leaves the injection
outcome unchanged:** re-running the context-poisoning probes
([@sec:eval-injection]) with `recency_weight` swept across its configured range leaves the poisoned
answer unchanged — an overlap-dominated injection already wins across the tested
recency range, so the sweep supplies no defensive effect. **(ii) Retrieval depth
leaves answer token-F1 unchanged** on lexically clean tasks: sweeping `top_k`/`max_evidence`
leaves token-F1 flat (the gold line is recoverable at depth one) and only lowers the
efficiency term — exactly why the Compiler's optimum is an efficiency tie-break
under this metric. **(iii) The lexical-anchored hybrid ties a learned-embedding RAG:** a pure
neural-embedding retrieval baseline (`src.retrieval.learned.dense_rag_answer`,
`{{RESULT_EMBED_MODEL}}`) matches the harness's answer token-F1 on the seeded set. A tie on this
deliberately easy set is the *expected* outcome — [@sec:eval-real] shows the synthetic
the data produce a retrieval-method tie. The tie supplies local parity evidence;
general parity requires a harder task family. Consistent with the no-harness
baseline ([@sec:eval-baseline]), the measured harness value here is provenance and
bounded context.

Robustness is locked in by a property-based fuzz pass (`tests/test_fuzz.py`): hundreds
of adversarial inputs — random punctuation, SQL-like strings, injection markers,
field-delimiter tokens, empty and oversized sessions — run through the harness and the
FTS5-backed persistent session with **zero crashes** and no output-invariant
violations. That test is the standing regression guard for the class of edge-case bug
the earlier `fts5: syntax error` belonged to.

## Reproducibility and Artifact Integrity Gates {#sec:val-integrity}

`tests/test_manuscript_integrity.py` enforces two structural contracts that keep
the reproducibility story honest. **Path hygiene**: no manuscript section or
shipped doc may reference a project path that no longer exists — a stale path
makes a documented `pytest` command collect zero tests and exit green, a silent
false pass the gate now forbids. **Injection-independent token coverage**: the
manuscript-variable generator locates the template root robustly even when THALIA
is checked out as a symlink *outside* the template tree, and its token-coverage
reproducibility contract completes independently of the optional PDF-injection step
— the gate enforces every published number as a generated token and remains
independent of renderer plumbing.

## Static Dashboard and Visual Evidence {#sec:val-dashboard}

`src/dashboard.py` renders a self-contained HTML page (no JavaScript, no
third-party dependency) embedding the headline metrics, the per-category
breakdown, the invariant pass/fail table, and the generated figures. It is built
by `scripts/build_dashboard.py` into `output/dashboard.html`. The renderer is a
pure function of its inputs and HTML-escapes all dynamic content, so it is both
testable and safe.

The dashboard is a compact audit surface for the same analysis. It
shows the same metrics and figures used in this manuscript, alongside invariant
status, so a reviewer can move from prose to rendered diagnostic to JSON artifact
without needing to infer which run produced which number.

Before rendering, `scripts/validate_artifacts.py` adds a separate artifact gate:
the manifest must cover the required outputs in `domain_profile.yaml`, and every
recorded size and hash must still match the current file. This catches stale or
mutated figures and JSON outside direct unit-test inspection.
