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
store, real temporary files, and real in-process HTTP servers for direct model
adapters (no `unittest.mock`, no `MagicMock`). Coverage on `src/` is gated at
{{CONFIG_COV_GATE}}%; current counts and outcomes belong in a completed run's
reports, not an undated readiness assertion. Selecting a real fallback path
(for example toggling `fts_available` to exercise the `LIKE` search branch)
is permitted because it exercises a real production branch.

The {{CONFIG_COV_GATE}}% gate covers the **deterministic core**. Optional real-DSPy
tests require the SDK and skip without it. `TestRealNeuralDspy` additionally
requires explicit opt-in through `THALIA_LIVE_TESTS`, model availability, and the local server;
dependency presence alone is not consent to generation. Neural calls do not run
during collection. These gated integration paths sit outside the deterministic
coverage envelope. The historical local figure in [@sec:eval-neural] reads a
retained DSPy full-context diagnostic, not a test-time run receipt.

The backend/method benchmark has a separate schema-two consistency boundary.
`validate_backend_benchmark` rebuilds all seeded cohorts and verifies the exact
backend-by-method-by-example matrix, execution schedule, method configurations,
prompt agreement within example/method across backends, finite metrics and
fingerprints. It recomputes token-F1, successful-only cell/category/stratum
summaries and within-backend paired seed-mean contrasts. Recorded portable
producer-inventory structure is validated without requiring it to equal the
reader's current source; checksums are not authenticity signatures.

Missing or duplicated cells, changed schedules, recomputed-score disagreement,
and altered summaries/paired statistics must fail validation. Honest failed rows
retain safe exception classes and null scores. Any incomplete planned contrast
suppresses both delta and interval; a single represented seed suppresses the
interval, while small-seed warnings remain visible for descriptive clustered
intervals. The reference absent from selected methods means not requested,
not zero effect. Schema-one artifacts are rejected, never silently migrated.
Historical cohorts remain intact.

Real loopback-server tests exercise request content and safe failures without
claiming live-provider quality. Offline consumers render incomplete reports as
diagnostics, preserve method identity and denominators, and distinguish prompt
characters from billed tokens and end-to-end timing from throughput/cost.
This validator is neither an execution receipt nor an expert-quality, power,
scientific-promotion, or production-readiness gate. The declared local study plan
requires a separate real execution receipt and statistical-validity review.

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

The v0.3.1 publication repair separates artifact-manifest ownership. THALIA's
required-output contract uses
`output/reports/thalia_artifact_manifest.json`; native rendering owns
`output/reports/artifact_manifest.json`. Previously the native generic output
scan overwrote the shared filename, omitted the required committed
`data/integrity_advantage.json`, and captured QA/preview entries that later
changed or were not packaged. A native working-tree pass therefore did not
establish that the published source-plus-supplement closure passed the project
gate.

The final publication sequence is now explicit: finish rendering, browser
inspection, QA reports, and preview selection; stage the exact release source
and only the supplemental allowlist at their original relative paths; write
THALIA's final inventory; run real native validation without rerendering; then
run `scripts/validate_artifacts.py` on that same stage. The adapter accepts
`--template-root PATH` for an explicitly provisioned template checkout and
`--validate-only` to invoke native validation without hydration or rendering.
It returns failure if THALIA's separate manifest fails, even when native checks
succeed. The project gate after native validation also checks claim,
traceability, integrity-screen, exact-injection, and bibliography contracts.
Executable runtime and staging instructions are in `docs/release_artifacts.md`.

No manifest-tracked QA or other output may change after final validation.
Package exactly the verified closure; a later render, verification-summary
refresh, QA edit, or allowlist change requires another final inventory and both
gates. Do not reseal measured study JSON. The retained `0.3.0` producer wheel,
unreleased `41da836` source, and original study fingerprint remain historical
producer evidence, not a v0.3.1 rerun. Exact patch observations belong in the
v0.3.1 release manifest rather than inherited test or validation counts.
The patch supersedes the v0.3.0 supplement defect without replacing its tag or
assets; it adds no DOI, cloud execution, expert/P0 confirmation, or production
acceptance.

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
THALIA's manifest must cover the required paths in `domain_profile.yaml`, and
every recorded size and hash must still match the current file. This catches
stale or mutated figures and JSON outside direct unit-test inspection. It is an
early check, not a substitute for the final staged-closure sequence after all
rendering and QA.
