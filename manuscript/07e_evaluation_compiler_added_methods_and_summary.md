# Evaluation: Compiler, Added Methods, and Summary {#sec:evaluation-compiler-added-methods-summary}

## Compiler {#sec:eval-compiler}

[@fig:compiler_convergence] shows the MIPRO-style search over
{{RESULT_NUM_CANDIDATES}} candidate configurations. On this dataset **every
candidate ties to full floating-point precision** — not merely to display
rounding: composite {{RESULT_COMPILED_SCORE}}, and the accuracy, grounding, and
efficiency components are bit-identical across all candidates. The tie is
*structural*, not a numerical coincidence: every config retrieves the same gold
spans (so accuracy and grounding are unchanged) and the dataset only ever yields a
couple of evidence windows, far below any candidate's `max_evidence` cap (so the
efficiency reward is the same too). With all three components pinned, no retrieval
depth can separate the configurations. The
reported optimum at top-k {{RESULT_COMPILED_TOP_K}} and max-evidence
{{RESULT_COMPILED_MAX_EVIDENCE}} is therefore a **tie-break** (the search returns
the first config achieving the shared maximum, which happens to be a tighter
budget), not a measured win — we report the exact tie rather than narrating a
nonexistent gain. The GEPA-style optimizer reaches the same plateau by reflective
mutation; its trace is recorded for audit. A perfectly flat convergence curve is
the honest outcome for a dataset whose gold evidence is trivially retrievable: the
search machinery is exercised end-to-end, and on a harder distribution — where
retrieval depth changes which spans survive — the same loop has room to move (see
the ablation and MMR sweep above, where a tight budget does separate the methods).

Two further diagnostics close the section. The RRF lane-weight sweep
([@fig:rrf_sensitivity]) confirms that under a *tight* budget the fusion does have a
shape — a non-monotonic dip at the balanced midpoint — even where every weight ties
under the slack default. And the consolidation curves ([@fig:consolidation])
illustrate, **schematically rather than empirically**, the memory-fault mechanism of
@zhang2026memory that the episodic-first Memory Gate is built to avoid: forced
per-turn consolidation degrades below the no-memory baseline while the gated regime
does not.

![MIPRO-style compiler search: candidate composite scores and the best-so-far curve. Every candidate ties exactly on this easy dataset, so the curve is intentionally flat and the optimum is a tie-break rather than a measured improvement. The inset decomposes the composite into its weighted accuracy/grounding/efficiency components, each constant across candidates — the flatness is a proven structural tie, not a rendering accident.](../output/figures/compiler_convergence.png){#fig:compiler_convergence width=70%}

The GEPA-style optimizer, by contrast, *can* move on a harder distribution because
it reflects on the weakest component and mutates accordingly. [@fig:gepa_trajectory]
shows one such reflective run: each iteration plots accuracy, grounding, efficiency,
and the composite, and the open halo marks the component the optimizer identified as
weakest at that step (the target of the next bounded mutation). On the easy set the
composite still plateaus, but the trajectory is no longer a single flat line — it
exposes *which* component the search would push first, and records the full trace so
a reader can audit the mutation strategy on real data rather than trust a prose
summary.

![GEPA component trajectory: per-iteration accuracy, grounding, efficiency, and composite (dashed) over a reflective evolution run. The open halo marks the weakest component at each step — the target of the next bounded mutation — so the reader can audit which component GEPA would push first on harder data.](../output/figures/gepa_trajectory.png){#fig:gepa_trajectory width=70%}

![RRF lane-weight sensitivity under a tight retrieval budget: composite as the lexical weight sweeps from 0 to 1 (semantic = 1 − weight). On this clean set the sub-word semantic surrogate ranks the gold line marginally better than BM25, so semantic-heavy fusion (lexical weight $\le 0.4$) scores highest; the curve then steps down non-monotonically — with a single dip at the balanced midpoint (lexical weight 0.5, where neither lane's ranking dominates) before settling onto a slightly lower lexical-heavy plateau. Under the loose default budget every weight ties — the tight budget is what surfaces the tradeoff.](../output/figures/rrf_sensitivity.png){#fig:rrf_sensitivity width=70%}

![Schematic memory-utility curves: forced per-turn consolidation rises then degrades below the no-memory baseline, while the episodic-first gated regime rises and never falls below it. Illustrative of the mechanism in @zhang2026memory, not an empirical measurement.](../output/figures/consolidation_curve.png){#fig:consolidation width=70%}

## Added-method diagnostics {#sec:eval-added}

Four further figures characterise the pipeline and the added methods. The
**evidence funnel** ([@fig:evidence_funnel]) quantifies the narrowing from raw
session lines through Inspector windows and ranked evidence down to cited sources —
the context-rot defence made visible. The **per-category breakdown**
([@fig:category_breakdown]) shows where the harness is strong and weak across the
six task classes. The **noise-scaling** curves ([@fig:noise_scaling]) plot each
lane's composite as distractor lines accumulate; under the default RRF weights the
hybrid lane tracks the lexical lane *exactly* (it is drawn dashed so it stays
visible over the solid lexical line), a direct, honest read-out of the scope
boundary that the sub-word semantic surrogate contributes nothing the lexical
signal does not already capture. The **MMR tradeoff** ([@fig:mmr_tradeoff]) sweeps
$\lambda$ in [@eq:mmr] from pure diversity to pure relevance under the same tight
retrieval budget (`top_k=2`, `max_evidence=2`) as the ablation and noise study:
pure diversity ($\lambda=0$) scores measurably lower because maximizing
dissimilarity can evict the discriminative span from the two-slot budget, and the
curve steps up to its plateau as soon as relevance is weighted at all ($\lambda \ge 0.1$).
Under the loose default budget the sweep would be flat by construction; the tight
budget surfaces the real diversity penalty without tuning the dataset.

![Evidence narrowing funnel: mean counts per query from raw session lines through Inspector windows, ranked evidence, and cited sources. The in-figure retention rates make the design tradeoff explicit: the Inspector narrows early, while the Reasoner cites selectively. Counts come from `src.evaluation.evidence_funnel` on the fixed six-example dataset; the figure measures context narrowing, not answer quality by itself.](../output/figures/evidence_funnel.png){#fig:evidence_funnel width=70%}

The funnel is a mean view; [@fig:pipeline_flow] makes the per-example narrowing
concrete by plotting, for each of the six demo examples (one per task category),
the evidence count at each pipeline stage — Inspector windows → Retriever ranked
→ Reasoner cited. The gaps between the three bars are exactly the drops the funnel
averages: an example that enters with two windows and cites both shows the
harness lost nothing in transit, while an example whose cited count falls below its
ranked count is a concrete grounding-failure case to inspect.

![Per-example evidence path across pipeline stages: Inspector windows (lexical blue), Retriever ranked (hybrid green), and Reasoner cited (accent pink) for each of the six demo examples (one per task category). The annotation reports the overall citation retention and marks each concrete ranked-to-cited gap, turning the visual into a diagnostic for where grounding is lost rather than a generic count chart.](../output/figures/pipeline_flow.png){#fig:pipeline_flow width=70%}

![Composite metric per task category on the fixed deterministic dataset. Each bar averages the same token-F1, grounding, and efficiency metric used for the headline results; the categories are diagnostic slices, not population estimates.](../output/figures/category_breakdown.png){#fig:category_breakdown width=70%}

The composite hides the components that produced it. [@fig:category_components]
decomposes each category's composite into its weighted accuracy/grounding/efficiency
contributions (the same 0.6/0.3/0.1 weights behind [@eq:composite]); the two weak
category bars in [@fig:category_breakdown] read, on inspection, as accuracy-bounded
(code, multi-session) rather than grounding or efficiency failures — consistent with
the LM-bounded-accuracy story in [@sec:eval-neural].

![Per-category weighted component breakdown: each bar stacks 0.6·accuracy (blue), 0.3·grounding (green), and 0.1·efficiency (pink) to its composite. The two weakest categories are accuracy-bounded (the extractive LM cannot synthesise the answer), not retrieval- or efficiency-bounded.](../output/figures/category_components.png){#fig:category_components width=70%}

![Composite metric per retrieval lane as lexical false-friend distractors are appended under the tight budget (`top_k=2`, `max_evidence=2`). The semantic line is the deterministic hashing surrogate, so the measured ordering is local to this surrogate and does not reproduce learned dense retrieval.](../output/figures/noise_scaling.png){#fig:noise_scaling width=70%}

![MMR relevance/diversity tradeoff under the same tight retrieval budget: composite as $\lambda$ sweeps from 0 (max diversity) to 1 (pure relevance). The sweep shows a two-slot selection penalty for pure diversity on this compact set; under the loose default budget it would be flat.](../output/figures/mmr_tradeoff.png){#fig:mmr_tradeoff width=70%}

## Added-method ablation {#sec:eval-ablation}

[@fig:method_ablation] reports the composite for the base pipeline and each added
retrieval method (query expansion, recency weighting, MMR), plus all combined, on
the single-turn dataset. The ablation runs under the same *tight* retrieval budget
(`top_k=2`, `max_evidence=2`) as the MMR sweep and noise study: under the loose
default budget every gold span is retrieved regardless of method, so the ablation
is null *by construction* — every condition is byte-identical, which measures the
budget, not the methods. A tight budget instead forces a genuine selection contest,
where each method can change which evidence survives. We do not tune the dataset to
manufacture a gap; we use a realistic budget under which the methods can operate at
all. Under that budget recency weighting is the clear winner — reordering by
recency promotes the discriminative span into the surviving evidence — while query
expansion is mildly negative (the extra terms dilute a query that was already
precise) and MMR is neutral on a set this small. **Memory recall is excluded from
this single-turn ablation** because it requires a populated episodic store; it is
exercised directly in the recall and harness tests, where a fact held only in the
episodic store (absent from the immediate session history) is recalled and surfaces
in the answer's citations.

![Added-method ablation under a tight retrieval budget: composite for base, each retrieval method, and all combined. Recency weighting is the clear winner; expansion is mildly negative; MMR is neutral on a set this small.](../output/figures/method_ablation.png){#fig:method_ablation width=70%}

## Summary {#sec:eval-summary}

The harness is correct, deterministic, and fully exercised: {{RESULT_NUM_EXAMPLES}}
examples across all task categories, high grounding and efficiency, a retrieval
lane comparison, a noise-scaling probe, and a compiler that searches and reports an
optimum. The two honest boundaries — extractive-LM accuracy and the hashing
semantic surrogate — are exactly the two designed plug-in points (a real LM, a real
embedder), neither of which perturbs the rest of the architecture.

The result is therefore not "THALIA beats another agent." The result is that a
typed, lexical-anchored, episodic-first, compiler-optimized harness can be implemented
as deterministic code, measured with auditable citations, regenerated through the
template pipeline, and extended at precisely identified model and embedding
boundaries.
