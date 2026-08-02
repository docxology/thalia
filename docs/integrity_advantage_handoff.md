# THALIA integrity-advantage expansion handoff

## Decision carried forward

The current evidence supports one narrow, legacy lexical observation: under the
recorded injection probes, THALIA's cited excerpts contain the supplied gold
value. The result concerns a cited-excerpt/source-exposure proxy, not a
true-source record or recoverability determination. It does not establish
claim-level auditability, answer faithfulness, poisoning resistance, general
model quality, or population performance.

The composite baseline comparison shows a conditional orchestration lift. The
pipeline and naive full-context baseline tie on answer token-F1; citation support
and structural evidence efficiency produce the composite difference. The
composite remains a declared utility function over a six-example synthetic set.

The learned retrieval, adaptive context, and MIPRO-style compiler results are
replication leads. The local neural comparison is a negative control for a broad
answer-quality claim.

## Current evidence screen

The executable source of these values is
[`data/integrity_advantage.json`](../data/integrity_advantage.json). It records
input hashes, analysis-code hashes, native units, interval methods, pairedness,
cluster counts, and the exploratory Holm family. The corresponding figure is
`output/figures/integrity_advantage_audit.png` after figure generation.

| Endpoint | Current estimate | Statistical record | Evidence status | Claim supported |
|:--|--:|:--|:--|:--|
| Lexical cited-excerpt/source exposure under injection | THALIA 30/30; naive 0/30; direction-normalized effect +1.000 | paired bootstrap interval [1.000, 1.000]; raw exact McNemar (p=1.86\times10^{-9}); exploratory Holm (p=9.31\times10^{-9}) | strongest current screening row | lexical cited-excerpt/source exposure only |
| Answer poisoning under injection | 2/30 in both conditions; effect +0.000 after lower-is-better normalization | paired bootstrap interval [0.000, 0.000]; raw exact McNemar (p=1.000); exploratory Holm (p=1.000) | null control | no poisoning-resistance advantage |
| Composite orchestration utility | 0.621 versus 0.286; lift +0.334 | finite six-example point difference; raw answer token-F1 ties | conditional metric lift | support and efficiency under the declared composite |
| Learned paraphrase retrieval recall@1 | 32/32 versus 28/32; effect +0.125 | paired bootstrap interval; raw exact McNemar (p=0.125); exploratory Holm (p=0.375) | promising, unconfirmed | representation-level retrieval lead |
| Adaptive context policy token-F1 | 0.171 versus 0.086; aggregate delta +0.085 | 30 retained external questions; no paired question-level interval in the source aggregate | promising, point-only | context reachability intervention lead |
| MIPRO-style held-out composite | delta +0.0025 | 20 seed clusters; interval [0.0020, 0.0029]; raw sign-flip (p=0.0002); exploratory Holm (p=0.0008) | promising, finite-cluster screen | compiler search lead on the finite split family |
| Local neural answer token-F1 | neural minus extractive delta −0.046 | (n=24); interval [−0.161, 0.067]; raw sign-flip (p=0.440); exploratory Holm (p=0.879) | negative/mixed control | no general neural answer advantage |

The binary intervals in the table are paired percentile-bootstrap intervals for
the risk difference. Wilson intervals for each condition remain in the report and
figure. The exact McNemar test addresses paired binary equality; it does not turn
the finite probe set into a population sample.

## Promotion language

Use the following claims in future manuscript revisions:

- **Current support:** “Under the recorded injection probes, THALIA's cited
  excerpts lexically contain the supplied gold value.”
- **Current conditional support:** “The typed pipeline increases the declared
  evidence-and-efficiency composite relative to the naive full-context baseline
  on the fixed synthetic bundle; raw answer token-F1 ties under the extractive
  backend.”
- **Research lead:** “Learned retrieval, adaptive context, and compiler search
  show finite positive signals that require paired, held-out replication.”
- **Current negative evidence:** “The injection study shows no poisoning-rate
  advantage, and the local neural comparison shows no general answer-quality
  advantage.”

Avoid “robustness,” “security,” “faithfulness,” “quality,” “generalization,” or
“model superiority” unless the corresponding endpoint and acceptance gate below
have been completed.

## Primary estimands for the expansion

Use one declared primary estimand per experiment. Let (q) index a matched probe
or question, (L) denote THALIA, (R) the comparator, and (d_e=+1) for a
higher-is-better endpoint or (d_e=-1) for a lower-is-better endpoint. For a
scalar endpoint (Y_{e,m,q}), define

\[
  \Delta^{\mathrm{adv}}_{e,q}
    = d_e\left(Y_{e,L,q}-Y_{e,R,q}\right),
  \qquad
  \widehat{\Delta}^{\mathrm{adv}}_e
    = \frac{1}{n_e}\sum_{q=1}^{n_e}\Delta^{\mathrm{adv}}_{e,q}.
\]

For binary endpoint (Z_{e,m,q}\in\{0,1\}), report both condition rates and
the paired risk difference:

\[
  \widehat p_{e,m}=\frac{1}{n_e}\sum_q Z_{e,m,q},
  \qquad
  \widehat{\Delta}^{\mathrm{adv}}_e
    = d_e\left(\widehat p_{e,L}-\widehat p_{e,R}\right).
\]

The primary integrity construct should be adjudicated source auditability:

\[
  Z^{\mathrm{audit}}_{m,q}=1
  \Longleftrightarrow
  \text{every evaluated answer claim has a recoverable, correct source record}
  \land
  \text{no cited source contradicts the claim}.
\]

The current `harness_auditable` field is a lexical cited-excerpt/source-exposure
proxy. It should remain labelled as a proxy until expert adjudication supplies
claim-level labels and recoverable source-record checks.
Track the following secondary endpoints separately:

1. source recall: the gold source is present in the cited set;
2. source precision: every cited source belongs to the admissible source set;
3. citation faithfulness: the cited excerpt entails the associated claim;
4. provenance completeness: all material claims have a citation;
5. answer correctness and completeness;
6. poisoning and false-source citation rates;
7. evidence exposure, Inspector reachability, and context cost;
8. raw-episode retention, memory-delta fidelity, contradiction rate, and stale
   memory rate.

## Experiment ladder

### P0 — Confirm the provenance candidate

Purpose: determine whether the auditability signal persists under a harder,
balanced attack design.

Design:

- Freeze the task set, attack families, source records, adjudication rubric, and
  primary endpoint before running the confirmatory tier.
- Use at least 120 matched probes for the first confirmation: 6 attack families
  × 20 probes, with the family labels hidden from the scorer and balanced across
  answer types.
- Compare four conditions on identical inputs: THALIA, naive full-context,
  citation-disabled THALIA, and an oracle-source condition that receives the
  correct source without retrieval. The oracle diagnoses the ceiling of the
  adjudication task; it is not a deployment baseline.
- Include clean probes, direct override injections, authority spoofing,
  recency-conflict injections, quoted false evidence, source-index spoofing, and
  multi-fact attacks. Hold the true source and the adversarial source in distinct
  records.
- Store one raw row per condition and probe: task ID, attack family, true source
  ID, injected source ID, answer text, citations, excerpts, poison label,
  adjudicated audit label, scorer version, and failure state.

Analysis:

- Primary: paired adjudicated auditability risk difference, THALIA minus naive.
- Secondary: source precision, source recall, false-source citation, answer
  correctness, poisoning, and auditability conditional on correctness.
- Use exact McNemar tests for paired binary endpoints, Wilson intervals for each
  rate, and paired percentile-bootstrap intervals for the risk difference.
- Preserve attack-family strata. Report family-specific effects and a prespecified
  all-family aggregate; do not average family p-values.
- Apply Holm correction within the predeclared endpoint family. Report all tested
  endpoints, failures, and exclusions.

Promotion gate:

- at least 120 matched probes and six attack families;
- positive adjudicated auditability effect with a 95% interval above zero;
- Holm-adjusted paired test (p<0.05);
- no material decrease in answer correctness or increase in false-source citation;
- effect reproduced on a held-out attack family and an independent rerun;
- raw source excerpts and adjudication records retained for audit.

### P0 — Separate provenance retention from poisoning resistance

The current probe conflates two outcomes in one visual grid. Run a factorial
study with clean, injected, and conflicting-source sessions. Randomize condition
order during adjudication. Measure:

| Factor | Levels |
|:--|:--|
| provenance channel | full citations, citation-disabled, naive, oracle |
| source condition | clean, one false source, multiple false sources, temporal update |
| answer task | lookup, multi-hop, update, abstention |

The primary contrast for poisoning is the direction-normalized poisoned-answer
rate. The primary contrast for provenance is adjudicated source auditability.
Report the interaction descriptively and fit no pooled model until the question
sampling and label protocol are frozen.

### P1 — Make the context-policy signal paired and causal

The current adaptive result compares aggregate slices without question-level
paired rows. Re-run a fixed external slice with the same questions and generator
under:

1. compact Inspector context;
2. fixed wide context;
3. adaptive context;
4. full-haystack oracle context.

Randomize the order of conditions at scoring time, pin model and generation
options, and log the exact windows delivered. Treat each question as the paired
unit. Primary endpoints are answer correctness and citation faithfulness;
session reachability and token cost are mechanism endpoints. Analyze the paired
delta by question family and context budget. A context policy earns promotion
only when it improves the primary answer endpoint without increasing unsupported
citations or cost beyond the predeclared tolerance.

### P1 — Test memory integrity longitudinally

Build a session sequence with known updates, contradictions, deletions, and
irrelevant distractors. Compare:

- episodic-first gated consolidation;
- forced consolidation after every turn;
- no derived memory;
- an oracle memory snapshot with the correct current fact.

Keep raw episodes immutable. Version every derived `MEMORY.md` delta. Evaluate
after each turn and at session end. Primary outcomes are current-fact accuracy,
stale-fact rate, contradiction rate, and recoverable provenance. Secondary
outcomes include consolidation latency, memory size, and citation completeness.
The design must contain explicit negative updates and stale-memory traps; a run
without those cases cannot support a memory-integrity claim.

### P1 — Replicate learned retrieval on held-out paraphrase families

The 32-probe learned-retrieval result is a representation-level signal. Expand to
at least 100 matched probes across held-out paraphrase families, lexical overlap
levels, spelling variation, compositional queries, and distractor density. Keep
the document corpus fixed, record model digest and embedding prefixes, and
compare learned, hashing, lexical, and hybrid lanes at the same budget.

Use recall@1 as the primary retrieval endpoint and evidence-level source recall
as a secondary endpoint. Pair every probe across lanes. Report exact paired tests,
paired intervals, failure counts, and per-family effects. The learned lane must
also be evaluated through the full THALIA pipeline before any system-level claim.

### P2 — Increase compiler generalization clusters (completed in the current local refresh)

The current held-out compiler refresh uses 20 independent task seeds and retains
the train/holdout split within each seed. The candidate budget and tie-breaking
rule remain fixed and explicit. The result is still a finite generated-task
screen; candidate-budget sensitivity and an independently sampled second
holdout remain open follow-ups. The retained report includes:

- cluster-level paired composite delta;
- answer, support, and efficiency component deltas;
- selection stability and candidate-budget sensitivity;
- independent holdout performance;
- failed and incomplete seed accounting.

Use whole-seed cluster bootstrap intervals and cluster sign-flip diagnostics. A
positive in-sample trace cannot promote the compiler; the promotion endpoint is
held-out performance under the fixed selection protocol.

## Baselines and controls

Every expansion should include the following controls where applicable:

- naive full-context baseline with no citation channel;
- citation-disabled THALIA to isolate the provenance mechanism;
- no-memory pipeline for memory experiments;
- fixed-wide and full-haystack context for context experiments;
- oracle source or oracle memory as a ceiling diagnostic;
- lexical-only, hashing-surrogate, learned, and hybrid retrieval at identical
  budgets;
- shuffled source IDs or citation metadata to detect score inflation;
- an attack-negative clean control to quantify false alarms;
- a held-out task or attack family that is invisible during compiler selection.

Keep negative controls in the headline tables. A control that produces equality
or failure is evidence about construct separation and remains part of the release
record.

## Statistical and accounting contract

1. Predeclare the primary endpoint, direction, unit, denominator, comparison
   family, stopping rule, and missing-row policy.
2. Pair methods on the same probe/question before calculating a delta.
3. Use the canonical notation in
   [`manuscript/12_supplemental_notation.md`](../manuscript/12_supplemental_notation.md):
   (Y_q), (Delta_q), (p_{\mathrm{Holm}}), (n_{\mathrm{obs}}), and
   (n_{\mathrm{cluster}}).
4. Use Wilson intervals for marginal binary rates, exact McNemar tests for paired
   binary equality, paired percentile bootstrap intervals for binary risk
   differences, and paired/clustered resampling for continuous outcomes.
5. Treat p-values as diagnostics tied to the declared finite design. Do not use
   the current synthetic or retained benchmark slices for population inference.
6. Apply Holm once to the complete predeclared family. Keep raw p-values beside
   adjusted values.
7. Preserve requested, completed, failed, and excluded rows. A missing neural
   row remains missing; no imputation or silent denominator change.
8. Record configuration, dataset, task, model, prompt, generation, embedding,
   scorer, code, and source hashes. Each aggregate must identify the command that
   produced it.
9. Run deterministic replay before comparing two conditions. Identical inputs
   and pinned settings must yield identical deterministic outputs.
10. Keep human adjudication data separate from exploratory local-LLM judging.
    The latter may diagnose parsing or rubric problems and cannot supply the
    confirmatory quality certificate.

## Visualization plan

The existing `integrity_advantage_audit` figure is the first screen. Add the
following figures as the experiments mature:

| Figure | Unit | Required visual contract |
|:--|:--|:--|
| Endpoint effect forest | endpoint-specific paired delta | one panel per compatible unit; zero line; interval method and cluster count in caption |
| Provenance rate panel | probe-level auditability, precision, recall, false-source rate | condition rates with Wilson intervals; show denominators and attack families |
| Paired outcome map | matched question/probe outcomes | discordant-pair counts and exact McNemar result; expose ties |
| Context frontier | answer quality, faithfulness, reachability, and token cost by budget | separate axes or small multiples; never combine cost and quality into an unlabeled score |
| Memory drift curve | outcome by turn and memory condition | raw episodes and derived memory version markers; stale/contradictory cases visible |
| Compiler generalization forest | seed-cluster held-out deltas | whole-cluster intervals, candidate budget, holdout size, and failed-seed accounting |
| Source trace matrix | claim-to-source adjudication | claim rows, source IDs, citation status, entailment status, and disagreement labels |

Every caption must state the observation unit, denominator, uncertainty method,
model or evidence tier, and the claim boundary. A figure with a point-only
aggregate must label it point-only in the panel and caption.

## Execution order

The current source-bound screen can be regenerated with:

```bash
uv run --project . --extra dev python scripts/run_compiler_generalization.py
uv run --project . --extra dev python scripts/analyze_integrity_advantage.py
uv run --project . --extra dev python scripts/generate_figures.py
uv run --project . --extra dev python scripts/z_generate_manuscript_variables.py
uv run --project ../template python scripts/render_pdf_external.py --validate
```

For the next experiment cycle:

1. freeze the protocol and source fingerprints;
2. generate raw paired rows and a machine-readable accounting ledger;
3. run the statistical analysis module and inspect the JSON before prose edits;
4. regenerate the figure from the aggregate JSON;
5. update the manuscript using generated tokens for all numeric claims;
6. run the deterministic test/coverage gate;
7. render and inspect HTML/PDF/browser output;
8. promote only when the endpoint-specific gate passes.

## Open blockers before a high-integrity advantage claim

- Current auditability is a lexical cited-excerpt/source-exposure proxy and has a
  baseline that emits no provenance by construction.
- Current poisoning probes show equality; citation retention must not be described
  as attack immunity.
- Adaptive context lacks paired question-level raw rows.
- Learned retrieval uses a small synthetic probe set and a different evidence
  tier from the deterministic hashing lane.
- Compiler generalization now has 20 seed clusters, but remains finite
  generated-task evidence without external-workload or population generalization.
- Neural answer quality uses token-F1 and lacks expert adjudication.
- Human-rater quality and production-readiness certificates remain separate
  unpromoted evidence lanes.

The next release should close the P0 provenance and poisoning designs first. Only
a successful P0 result can support a true-source-recoverability or confirmed
integrity-advantage claim. The other lanes should remain explicitly exploratory
until their matched raw rows, held-out controls, and promotion gates are complete.
