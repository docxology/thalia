# Supplement: Canonical Notation and Statistical Contracts {#sec:supplemental-notation}

This section is the notation single source of truth for the formal definitions
in [@sec:harness-formalism-added-methods]. Subscripts identify the construct or
unit; each canonical symbol has one meaning. In particular,
$S_{\mathrm{MMR}}$ is the selected set, $S_{\mathrm{eff}}$ is the efficiency
scale, and $G_{\mathrm{sup}}$ is the citation-support proxy. The hashing lane is
the deterministic sub-word surrogate; learned dense representation is a separate
optional lane.

## Canonical Symbols and Object Types

| Symbol | Meaning and scope |
|---|---|
| $T(x)$ | Ordered lowercase alphanumeric token sequence for text $x$. |
| $U(x)$ | Set of distinct tokens in $T(x)$. |
| $\mathcal H$ | Raw session transcript supplied to the Inspector. |
| $\mathcal M$ | Frozen memory snapshot supplied to one invocation. |
| $\theta$ | Immutable `HarnessConfig` governing one invocation. |
| $W_I$ | Evidence-window sequence emitted by the Inspector. |
| $\mu_I$ | Inspector metadata, including patterns, indices, and coverage. |
| $W_R$ | Ranked evidence sequence emitted by the Retriever. |
| $\delta_R$ | Retriever delivery decision: inline or file-based. |
| $\hat y$ | Generated answer for the current query. |
| $\tau_N$ | Reasoner routing and evidence-use trace. |
| $e$ | Episodic append result produced by the Memory Gate. |
| $\Delta_{\mathcal M}$ | Optional derived memory delta. |
| $I_\theta$ | Inspector stage function. |
| $R_\theta$ | Retriever stage function. |
| $N_\theta$ | Reasoner stage function. |
| $G_\theta$ | Memory Gate stage function. |
| $q$ | Current query text; $T(q)$ supplies the token sequence used by retrieval. |
| $c_q$ | Task category classified from query $q$. |
| $t$ | Turn identifier used by the append-only episodic store. |
| $s$ | Session-ending indicator supplied to the Memory Gate. |
| $b_N$ | Reasoner gate payload $(r_N,x_N)$: consolidation flag and explicit memory-request indicator. |
| $r_N$ | Reasoner's consolidation-request flag. |
| $x_N$ | Explicit memory-request indicator derived from the query. |
| $\Sigma_G$ | Memory Gate state containing the episodic store and current derived-memory text. |
| $\Theta$ | Candidate configuration surface searched by the Compiler. |
| $\mathcal D$ | Declared finite evaluation set supplied to a Compiler run. |
| $\hat\theta$ | First configuration attaining the maximum finite-set composite under the stable candidate order. |
| $\mathcal T_C$ | Complete Compiler candidate-and-trace ledger for one search. |
| $\bar M$ | Mean per-example composite score for a configuration on $\mathcal D$. |
| $\prec_\Theta$ | Stable candidate order used to resolve equal Compiler scores. |
| $d$ | Candidate document/window token sequence in BM25. |
| $R$ | Ranked evidence collection used by the efficiency proxy. |
| $A$ | Answer token-F1 component in the composite metric. |
| $H$ | Indicator for at least one expected source index being cited. |
| $r_\ell(c)$ | Zero-based rank of candidate $c$ in retrieval lane $\ell$. |
| $B_b$ | Consecutive Inspector partition block with index $b$. |
| $B$ | Evidence token budget used by the delivery decision. |
| $Q_I$ | Distinct query-token set used by Inspector relevance. |
| $S_{\mathrm{MMR}}$ | Candidates already selected by greedy MMR. |
| $C_{\mathrm{cite}}$ | Source indices cited by a generated answer. |
| $E_{\mathrm{cite}}$ | Joined excerpts attached to $C_{\mathrm{cite}}$. |
| $G_{\mathrm{gold}}$ | Expected source-index set supplied by a finite evaluation example. |
| $G_{\mathrm{sup}}$ | Citation-support proxy: lexical overlap plus optional expected-source hit. |
| $P_{\mathrm{cite}}$ | Source-index citation precision: expected cited sources divided by all cited sources. |
| $R_{\mathrm{src}}$ | Source-index citation recall: expected sources represented in the citation set. |
| $S_{\mathrm{eff}}$ | Evidence-window scale used by the structural efficiency proxy. |
| $E_{\mathrm{eff}}$ | Structural efficiency score derived from ranked-window count. |
| $M$ | Per-example composite score, a declared weighted sum of $A$, $G_{\mathrm{sup}}$, and $E_{\mathrm{eff}}$. |
| $Y_q$ | A scalar outcome for analysis unit $q$, as declared by the analysis. |
| $\Delta_q$ | Paired outcome difference for unit $q$, left method minus right method. |
| $p_{\mathrm{Holm}}$ | Holm-adjusted paired-test p-value within the explicitly named comparison family; the current integrity screen's family is exploratory. |
| $n_{\mathrm{obs}}$ | Number of observed rows retained in a declared denominator, including failures when required. |
| $n_{\mathrm{cluster}}$ | Number of resampling or paired-randomization clusters. |
| $Z_{e,m,q}$ | Binary endpoint for method $m$, comparison endpoint $e$, and matched unit $q$. |
| $d_e$ | Direction code for endpoint $e$: $+1$ when higher is better and $-1$ when lower is better. |
| $\Delta^{\mathrm{adv}}_{e,q}$ | Direction-normalized paired effect: $d_e(Y_{e,L,q}-Y_{e,R,q})$, where positive values favor the left method. |
| $\widehat{\Delta}^{\mathrm{adv}}_e$ | Mean direction-normalized paired effect for endpoint $e$. |
| $\widehat p_{e,m}$ | Binary success rate for method $m$ on endpoint $e$. |
| $\mathrm{CI}^{\mathrm{pair}}_e$ | Paired percentile-bootstrap interval for a binary risk difference or continuous paired effect. |
| $\mathcal F_{\mathrm{int}}$ | Current exploratory integrity-screen family receiving one Holm step-down adjustment; a future P0 family is predeclared only after protocol freeze. |
| $\mathcal Q_{\mathrm{audit}}$ | Matched legacy injection probes used for the lexical cited-excerpt/source-exposure proxy. |

The remaining constants are local to a displayed equation: $k_1$ and $b$ are
BM25 parameters, $k$ is the RRF damping constant, $\lambda$ is the MMR relevance
weight, $\rho$ is the recency weight, $B$ is the evidence token budget, and $D$
is the hashing-vector dimension. $K$ is the PRF term cap and $n$ is the ranked
evidence count where the efficiency equation defines it. These names are local
constants and remain distinct from the canonical symbols above.

## Statistical Contracts and Interpretation Rules

The statistical layer reports finite-data summaries with explicit methods. A
nominal confidence level labels the interval construction. Synthetic examples,
finite seed-cluster counts, and finite local model probes remain finite-data evidence;
target-population estimation requires a separate sampling design.

**Continuous outcomes.** For a declared observation vector $Y_q$, the point
estimate is the arithmetic mean. Percentile bootstrap intervals resample rows
with replacement; stratified intervals preserve each observed stratum size; and
cluster intervals resample whole clusters while retaining their rows. The
reported interval is therefore a descriptive resampling interval. For a paired
comparison, resampling operates on paired differences $\Delta_q$; when the
declared unit is a cluster, the point estimate is the mean of cluster-level
means; this weighting keeps unequal cluster sizes from changing the declared
estimand.

**Binary outcomes.** A binary rate is reported with the Wilson score interval.
For paired binary outcomes, the exact two-sided McNemar p-value conditions on
the discordant-pair count and uses the exact binomial tail under equal paired
success probabilities. The continuous sign-flip diagnostic has a different
estimand and exchangeability assumption.

For an endpoint with direction code $d_e$, the paired binary effect is
$\widehat{\Delta}^{\mathrm{adv}}_e=d_e(\widehat p_{e,L}-\widehat p_{e,R})$.
The implementation reports a paired percentile-bootstrap interval for the
individual differences $d_e(Z_{e,L,q}-Z_{e,R,q})$ and Wilson intervals for the
two marginal rates. The two interval constructions answer different questions:
the paired interval describes the matched risk difference, while each Wilson
interval describes one condition's success probability.

**Paired continuous comparisons.** The sign-flip procedure tests the observed
mean absolute difference against sign assignments of $\Delta_q$. Exhaustive
enumeration is called exhaustive only when every assignment is enumerated. For
larger samples the implementation uses seeded Monte Carlo sign flips with the
plus-one correction. Both branches require the stated exchangeability/symmetry
assumption and are reported as randomization diagnostics.

**Multiplicity.** If a comparison family contains $m$ raw p-values, Holm's
step-down adjustment sorts them, multiplies the rank-$j$ value by $m-j+1$, and
applies the cumulative maximum, capped at one. The resulting values are
$p_{\mathrm{Holm}}$. FDR q-values use a different multiplicity procedure.

**Accounting.** Requested rows, completed rows, and failed rows are tracked
separately. A failed requested row remains in $n_{\mathrm{obs}}$ when the
protocol declares a requested-denominator estimand. Optional neural or external
rows retain their own evidence tier. A missing model-dependent lane is reported
as unrecorded; no value is imputed.
