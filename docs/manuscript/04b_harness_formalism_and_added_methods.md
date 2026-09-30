# Formal Specification: Retrieval, Evidence, Metrics, and Evaluation {#sec:harness-formalism-added-methods}

## Formal Objects and Their Executable Status {#sec:formalism}

The retrieval, evidence, and evaluation lanes are specified as executable
functions with explicit inputs, outputs, units, and invariants. The code-paper registry contains
{{RESULT_FORMALISM_COUNT}} formal objects and {{RESULT_TRACEABILITY_EDGE_COUNT}}
composition edges, with {{RESULT_CLAIM_COUNT}} audited claims; its generated table
appears in [@sec:method-traceability]. The equations below state the exact
estimands and units used by the implementation. Their scope is operational: each
proxy measures the code-defined quantity named in its unit and estimand fields.
Relevance, factuality, efficiency, and model quality require separate construct
validity evidence. Finite synthetic measurements remain finite-set observations.
The canonical symbol crosswalk and statistical contracts are collected in
[@sec:supplemental-notation].

## Typed Stage Composition and Dataflow {#sec:typed-stage-composition}

Let $\mathcal H$ denote the raw session transcript, $q$ the current query text,
$c_q$ its classified task category, $\theta$ the immutable `HarnessConfig`, and
$\mathcal M$ the frozen memory snapshot supplied to one invocation. Let $t$ be
the turn identifier, $s$ the session-ending indicator, and
$b_N=(r_N,x_N)$ the Reasoner's runtime gate payload, where $r_N$ is the
consolidation flag and $x_N$ records an explicit memory request. The stage
composition is:

\begin{equation}
\label{eq:typed-composition}
\begin{aligned}
I_\theta(q,\mathcal H)&=(W_I,\mu_I),\\
R_\theta(q,W_I,c_q)&=(W_R,\delta_R),\\
N_\theta(q,W_R,c_q,\mathcal M)&=(\hat y,C_{\mathrm{cite}},\tau_N,b_N),\\
G_\theta(q,\hat y,C_{\mathrm{cite}},b_N,c_q,t,s;\Sigma_G)&=
    (e,\Delta_{\mathcal M},\Sigma_G').
\end{aligned}
\end{equation}

$W_I$ is the Inspector window sequence, $\mu_I$ is Inspector metadata,
$W_R$ is the ranked evidence sequence, $\delta_R$ is the delivery decision,
$\hat y$ is the answer, $C_{\mathrm{cite}}$ is the cited source-index set,
$\tau_N$ is the Reasoner trace, $e$ is the episodic append result,
$\Delta_{\mathcal M}$ is an optional derived memory delta, and $\Sigma_G$ is
the Memory Gate state containing the append-only store and current derived-memory
text. The composition enforces the evidence boundary: $N_\theta$ receives
$W_R$ and the frozen snapshot, while $G_\theta$ receives the completed answer,
citations, gate flags, task category, turn state, and gate state. The transition
$\Sigma_G\to\Sigma_G'$ appends the raw episode before any derived memory write.
The optional Compiler searches a bounded subset of $\theta$ and records its trace;
the stage functions remain fixed during each run.

For a finite evaluation set $\mathcal D$ and candidate configuration surface
$\Theta$, the deterministic Compiler selects:

\begin{equation}
\label{eq:compiler-selection}
\hat\theta=\operatorname{first}_{\prec_\Theta}
\arg\max_{\theta\in\Theta}\bar M(\theta;\mathcal D),
\qquad
\mathcal T_C=\{(\theta,\bar M(\theta;\mathcal D),\text{trace}_\theta):\theta\in\Theta\}.
\end{equation}

Here $\bar M$ is the declared mean of per-example composite scores and
$\prec_\Theta$ is the stable candidate order. The first-achieving rule makes a
tie an explicit selection outcome. Equal scores remain equal; a performance
difference requires score separation.

The observation unit is explicit at every evaluation boundary. Per-example
metrics use one generated or retained question as the unit; category summaries
aggregate those rows; seed-cluster summaries resample the declared seed unit;
planned quality and production lanes use their own declared rows. A number is
interpretable only with its unit, denominator, evidence tier, and interval or
test construction.

**Shared tokenizer.** Let $T(x)$ be the ordered sequence returned by
`src.module.tokenize`: lowercase matches of the alphanumeric regular expression.
The sequence is shared by retrieval and scoring; the tokenizer retains lowercase
alphanumeric matches and drops punctuation.

\begin{equation}
\label{eq:tokenizer}
T(x) = \operatorname{findall}(\texttt{[A-Za-z0-9]+},\operatorname{lower}(x))
\end{equation}

**Answer token-F1.** The headline answer component uses distinct-token sets. Let
$U(x)$ be the set of distinct tokens in $T(x)$ and
$I = U(\hat y)\cap U(y)$. The observation unit is one evaluation
example. The score measures lexical overlap. Semantic correctness, entailment,
factuality, and answer-level annotation require separate measurements.

\begin{equation}
\label{eq:token-f1}
F_1(\hat y,y)=
\begin{cases}
1,&|U(\hat y)|=|U(y)|=0\\
0,&|U(\hat y)|=0\ \text{xor}\ |U(y)|=0\\
\displaystyle\frac{2|I|}{|U(\hat y)|+|U(y)|},&\text{otherwise.}
\end{cases}
\end{equation}

The implementation returns $1$ when both sets are empty and $0$ when exactly one
set is empty. Repeated occurrences have no effect because the score uses distinct
token sets.

**BM25 (lexical lane)** [@robertson2009bm25]. For query $q$ treated as the
token multiset produced by $T$, document $d$ with term frequency $f(t,d)$,
document length $|d|$, mean length $\overline d$, and corpus size $N$:


\begin{equation}
\label{eq:bm25}
\mathrm{BM25}(q,d) = \sum_{t \in q} \mathrm{idf}(t)
\frac{f(t,d)(k_1+1)}{f(t,d)+k_1(1-b+b|d|/\overline d)},\qquad
\mathrm{idf}(t)=\ln\left(1+\frac{N-n_t+0.5}{n_t+0.5}\right)
\end{equation}

The sum is over query-token occurrences: repeated query tokens contribute
repeatedly, while repeated document tokens affect $f(t,d)$. Defaults are
$k_1={{CONFIG_BM25_K1}}$ and $b={{CONFIG_BM25_B}}$. Terms absent from the corpus
have zero contribution; documents with a zero total score are excluded from
`top_k`; ties use ascending document index. The $+1$ inside the logarithm keeps
$\mathrm{idf}(t)\geq 0$ (an executable invariant, [@sec:validation]).

**Hashing-cosine semantic surrogate.** The implementation first lowercases text,
collapses whitespace, and pads the non-empty result with two spaces on each side.
Let $G_3(x)$ be the resulting ordered character-trigram list, retaining repeated
trigrams. Each trigram is hashed with SHA-1 into one of $D$ buckets and uses the
fifth digest byte for a signed contribution. Let $h(u)$ be its bucket and
$s(u)\in\{-1,+1\}$ its sign. The zero vector is returned for empty input;
otherwise the vector is L2-normalized before cosine comparison.

\begin{equation}
\label{eq:hash-cosine}
v_j(x)=\sum_{u\in G_3(x)}s(u)\,\mathbf 1[h(u)=j],\qquad
e(x)=\frac{v(x)}{\|v(x)\|_2},\qquad
\operatorname{sim}(x,z)=\begin{cases}e(x)\cdot e(z),&\|v(x)\|_2\|v(z)\|_2>0\\0,&\text{otherwise.}\end{cases}
\end{equation}

The lane is a deterministic sub-word surrogate. Learned dense embeddings and
semantic correctness are separate evidence lanes. Positive similarities are retained for ranking;
ties are broken by ascending document index after fixed-precision comparison.

**Weighted Reciprocal Rank Fusion.** For a candidate chunk $c$ at zero-based rank
$r_\ell(c)$ in lane $\ell$ of weight $w_\ell$ (lexical
$ {{CONFIG_LEXICAL_WEIGHT}}$, semantic ${{CONFIG_SEMANTIC_WEIGHT}}$):

\begin{equation}
\label{eq:rrf}
\mathrm{RRF}(c)=\sum_\ell\frac{w_\ell}{k+r_\ell(c)+1},\qquad k={{CONFIG_RRF_K}}.
\end{equation}

Each lane is de-duplicated by retaining its first occurrence before scoring;
absent lanes contribute nothing. The fused score defines candidate ordering. It
has no calibrated-probability interpretation. The reported summed float is
preserved. The ordering key rounds to twelve decimal places before the ascending-id
tie-break, which stabilizes equal candidates across platform floating-point
variation.

**Maximal Marginal Relevance.** Given fused scores $s_i$, the implementation
min--max normalizes relevance as $\operatorname{rel}_i=(s_i-s_{\min})/(s_{\max}-s_{\min})$;
when all scores are equal it assigns relevance one. With selected set
$S_{\mathrm{MMR}}$ and hashing-cosine similarity, the empty-set maximum is
defined as zero:

\begin{equation}
\label{eq:mmr}
\operatorname{MMR}(i\mid S_{\mathrm{MMR}})=\lambda\operatorname{rel}_i-(1-\lambda)
\max\left(\{\operatorname{sim}(i,j):j\in S_{\mathrm{MMR}}\}\cup\{0\}\right).
\end{equation}

The first item is the maximum-relevance item; subsequent items are greedy.
Ties use relevance and then ascending candidate index. Thus $\lambda=1$ gives
the relevance order, while smaller values trade relevance for novelty. The method
is a selection heuristic. Evidence that diversity improves answer truth requires
an answer-level intervention and adjudication study.

**Inspector relevance and partitioning.** The Inspector loads the complete
transcript into an external, line-addressable state object. Only selected windows
are eligible for the Reasoner prompt. For query-token set $Q_I$ and non-empty
record $L_i$, its relevance is:

\begin{equation}
\label{eq:inspector-relevance}
\rho_i=\frac{|Q_I\cap U(L_i)|}{\lvert Q_I\rvert},\qquad \rho_i=0\text{ when }\lvert Q_I\rvert=0.
\end{equation}

When the record count exceeds `partition_threshold`, consecutive blocks $B_b$ of
`partition_size` records are scored by $\sum_{i\in B_b}\rho_i$. The Inspector
keeps $m=\max(1,\lfloor\texttt{max\_windows}/\texttt{partition\_size}\rfloor+1)$
highest-scoring blocks and fine-ranks records inside their union. Equal block
scores are ordered by ascending block index:

\begin{equation}
\label{eq:inspector-partition}
\operatorname{score}(B_b)=\sum_{i\in B_b}\rho_i,\qquad
\mathcal A=\bigcup_{b\in\operatorname{Top}_m(B)}B_b.
\end{equation}

The emitted confidence is the fraction of distinct query tokens covered by the
selected windows. It is a lexical coverage diagnostic. Probability calibration
and answer correctness require separate labels and outcomes. A later ranking stage
has no access to a discarded block; this mechanism explains why Inspector recall can
be isolated as a bottleneck in a retained diagnostic slice. Causal claims require
an intervention design.

## Added Methods: Retrieval, Memory, and Compiler Extensions {#sec:added-methods}

The following optional methods compose with the base pipeline. Their code anchors,
tests, units, estimands, and limitations are generated in [@sec:method-traceability].

**Query expansion — PRF.** With `query_expansion=True`, an initial BM25 pass
returns $R$ top windows. After removing stopwords, original query terms, and
terms of length at most two, the feedback count is $c(t)=\sum_{d\in R}
\mathbf 1[t\in T(d)]$. Terms are appended in descending $c(t)$, then
alphabetical order, capped at `top_terms`:

\begin{equation}
\label{eq:prf}
q'=q\mathbin{\|}\operatorname{first}_{K}\left(\operatorname{sort}_{(-c(t),t)}\{t:c(t)>0\}\right).
\end{equation}

This is RM3-inspired deterministic feedback. Learned query expansion remains a
separate optional method.

**Recency weighting.** For eligible non-negative transcript index $i$, let
$i_{\max}$ be the largest eligible index and $s_{\max}$ the largest fused score.
With $\rho\in[0,1]$:

\begin{equation}
\label{eq:recency}
s'_i=\operatorname{round}_8\left(s_i+\rho s_{\max}\frac{i}{i_{\max}}\right),
\quad i\geq0,\ i_{\max}>0;
\qquad s'_i=s_i\text{ for recalled }i<0\text{ or }i_{\max}\leq0.
\end{equation}

The result is sorted by descending adjusted score and ascending source index.
Source position is a temporal-order proxy. Elapsed time and causal effects
require timestamped data and a corresponding design.

**Evidence budget.** For selected window texts $W$ the structural token estimate is
the shared-tokenizer count. Delivery is inline exactly when it fits the configured
budget:

\begin{equation}
\label{eq:evidence-budget}
\widehat n(W)=\sum_{w\in W}|T(w)|,\qquad
\operatorname{delivery}(W)=\begin{cases}\text{INLINE},&\widehat n(W)\leq B\\
\text{FILE\_BASED},&\widehat n(W)>B.\end{cases}
\end{equation}

The quantity is a structural context-size proxy. Latency, prompt-token billing,
memory consumption, monetary cost, and user experience require operational
measurements.

**Citation-support proxy.** Let $C_{\mathrm{cite}}$ be cited source indices,
$E_{\mathrm{cite}}$ their joined excerpts, and $G_{\mathrm{gold}}$ the expected
source-index set. Let $H=1$ when $C_{\mathrm{cite}}\cap G_{\mathrm{gold}}\neq
\varnothing$ and zero otherwise. The implementation uses:

\begin{equation}
\label{eq:grounding}
G_{\mathrm{sup}}=\begin{cases}
\tfrac12H+\tfrac12F_1(\hat y,E_{\mathrm{cite}}),&G_{\mathrm{gold}}\neq\varnothing\\
F_1(\hat y,E_{\mathrm{cite}}),&G_{\mathrm{gold}}=\varnothing.
\end{cases}
\end{equation}

The aggregate field `grounding` denotes citation-support token overlap. Entailment,
factual attribution, line-level evidence grounding, and the fine-grained
factuality assessment proposed by FActScore [@min2023factscore] require separate
annotations.

**Citation-set diagnostics.** The live campaign also records two source-index
diagnostics that decompose the citation set. Let $C_{mathrm{cite}}$ be the
distinct cited indices and $G_{mathrm{gold}}$ the declared expected indices:

\begin{equation}
\label{eq:citation-precision}
P_{\mathrm{cite}}=
\begin{cases}
0,&|C_{\mathrm{cite}}|=0\\
1,&|C_{\mathrm{cite}}|>0\ \land\ |G_{\mathrm{gold}}|=0\\
\displaystyle\frac{|C_{\mathrm{cite}}\cap G_{\mathrm{gold}}|}{|C_{\mathrm{cite}}|},&\text{otherwise.}
\end{cases}
\end{equation}

\begin{equation}
\label{eq:source-recall}
R_{\mathrm{src}}=
\begin{cases}
1,&|G_{\mathrm{gold}}|=0\ \land\ |C_{\mathrm{cite}}|>0\\
0,&|G_{\mathrm{gold}}|=0\ \land\ |C_{\mathrm{cite}}|=0\\
\displaystyle\frac{|C_{\mathrm{cite}}\cap G_{\mathrm{gold}}|}{|G_{\mathrm{gold}}|},&\text{otherwise.}
\end{cases}
\end{equation}

$P_{\mathrm{cite}}$ exposes extraneous cited indices and $R_{\mathrm{src}}$
exposes missing declared sources. Both operate at the adapter's source-index
granularity. ALCE separates citation recall and precision through statement-level
entailment [@gao2023alce], and ARES separates context relevance, answer
faithfulness, and answer relevance [@saadfalcon2024ares]. THALIA's two
source-index diagnostics therefore strengthen the audit of its lexical support
proxy while remaining below sentence-level entailment. [@fig:metric_construct_audit]
shows the finite demo decomposition by task category.

![Metric construct audit for the fixed {{RESULT_NUM_EXAMPLES}}-example synthetic demo. Rows are task categories and columns are answer token-F1, the blended citation-support proxy, source-index citation precision, source-index recall, session reachability, and evidence-count efficiency. Cell values are finite category means on a unit interval; the figure is a construct audit with no uncertainty interval or model-quality estimand.](../output/figures/metric_construct_audit.png){#fig:metric_construct_audit width=100%}

**Structural efficiency and composite score.** With $n=|R|$ ranked evidence
windows and scale $S_{\mathrm{eff}}={{CONFIG_EFFICIENCY_SCALE}}$:

\begin{equation}
\label{eq:efficiency}
E_{\mathrm{eff}}(R)=\max\left(0,1-\frac{n}{S_{\mathrm{eff}}}\right).
\end{equation}

The per-example composite is a fixed convex sum:

\begin{equation}
\label{eq:composite}
M={{CONFIG_WEIGHT_ACC}}A+{{CONFIG_WEIGHT_GROUND}}G_{\mathrm{sup}}+{{CONFIG_WEIGHT_EFF}}E_{\mathrm{eff}}.
\end{equation}

Its estimand is the finite-set mean of per-example scores unless a section states a
different unit. The research ledger retains observed failures in requested
denominators when the protocol declares that denominator. Optional model failures
remain separate from completed rows.

**Analysis connection.** The statistical layer uses explicit strata and seed
clusters. Continuous-score intervals are descriptive percentile or cluster-
resampling intervals. Their interpretation follows the declared resampling unit
and estimand. Paired continuous-score
comparisons use a sign-flip randomization diagnostic under a paired-difference
exchangeability assumption; exhaustive enumeration is used only for small paired
samples, while larger samples use seeded Monte Carlo with a plus-one correction.
Binary paired outcomes use the exact conditional McNemar test, and the complete
family of comparison p-values is adjusted with Holm's step-down procedure. The
The audit records {{RESULT_AUDIT_SEED_COUNT}} seed clusters; {{RESULT_AUDIT_CLUSTER_WARNING}}.
Ordinary population coverage requires an independent sampling design. These
interpretations apply to every figure and caption that reports the quantities.
