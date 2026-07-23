# Harness Design: Formal Semantics of Retrieval, Evidence, and Evaluation {#sec:harness-formalism-added-methods}

## Formal objects and their executable status {#sec:formalism}

The retrieval, evidence, and evaluation lanes are specified as executable
functions rather than informal labels. The code-paper registry contains
{{RESULT_FORMALISM_COUNT}} formal objects and {{RESULT_TRACEABILITY_EDGE_COUNT}}
composition edges, with {{RESULT_CLAIM_COUNT}} audited claims; its generated table
appears in [@sec:method-traceability]. The equations below state the exact
estimands and units used by the implementation. They do not turn finite synthetic
measurements into population estimates.

**Shared tokenizer.** Let $T(x)$ be the ordered sequence returned by
`src.module.tokenize`: lowercase matches of the alphanumeric regular expression.
The sequence is shared by retrieval and scoring; punctuation is not retained.

\begin{equation}
\label{eq:tokenizer}
T(x) = \operatorname{findall}(\texttt{[A--Za--z0--9]+},\operatorname{lower}(x))
\end{equation}

**Answer token-F1.** The headline answer component is set-based, not a multiset
metric. Let $U(x)$ be the set of distinct tokens in $T(x)$, $I = U(\hat y)\cap
U(y)$, and $p,r$ be precision and recall. The observation unit is one evaluation
example. This is lexical overlap: it is not semantic correctness, entailment,
factuality, or human annotation.

\begin{equation}
\label{eq:token-f1}
p=\frac{\lvert I\rvert}{|U(\hat y)|},\qquad r=\frac{\lvert I\rvert}{|U(y)|},\qquad
F_1=\frac{2pr}{p+r}
\end{equation}

When both sets are empty the implementation returns $1$; when exactly one is
empty it returns $0$. Repeated occurrences therefore do not increase overlap.

**BM25 (lexical lane)** [@robertson2009bm25]**.** For query $q$ treated as the
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

**Hashing-cosine semantic surrogate.** For character-trigram multiset $G_3(x)$,
the implementation hashes each trigram with SHA-1 into one of $D$ buckets and
uses the fifth digest byte for a signed contribution. Let $h(u)$ be its bucket
and $s(u)\in\{-1,+1\}$ its sign. The zero vector is returned for empty input;
otherwise the vector is L2-normalized before cosine comparison.

\begin{equation}
\label{eq:hash-cosine}
v_j(x)=\sum_{u\in G_3(x)}s(u)\,\mathbf 1[h(u)=j],\qquad
e(x)=\frac{v(x)}{\|v(x)\|_2},\qquad
\operatorname{sim}(x,z)=\begin{cases}e(x)\cdot e(z),&\|v(x)\|_2\|v(z)\|_2>0\\0,&\text{otherwise.}\end{cases}
\end{equation}

This is a deterministic sub-word surrogate, not a learned dense embedder and not
a semantic correctness oracle. Positive similarities are retained for ranking;
ties are broken by ascending document index after fixed-precision comparison.

**Weighted Reciprocal Rank Fusion.** For a candidate chunk $c$ at zero-based rank
$r_\ell(c)$ in lane $\ell$ of weight $w_\ell$ (lexical
$ {{CONFIG_LEXICAL_WEIGHT}}$, semantic ${{CONFIG_SEMANTIC_WEIGHT}}$):

\begin{equation}
\label{eq:rrf}
\mathrm{RRF}(c)=\sum_\ell\frac{w_\ell}{k+r_\ell(c)+1},\qquad k={{CONFIG_RRF_K}}.
\end{equation}

Each lane is de-duplicated by retaining its first occurrence before scoring;
absent lanes contribute nothing. The fusion score is a ranking device, not a
calibrated probability. The reported summed float is preserved, but the ordering
key rounds to twelve decimal places before the ascending-id tie-break so
sub-floating-point platform noise cannot reorder an otherwise equal candidate.

**Maximal Marginal Relevance.** Given fused scores $s_i$, the implementation
min--max normalizes relevance as $\operatorname{rel}_i=(s_i-s_{\min})/(s_{\max}-s_{\min})$;
when all scores are equal it assigns relevance one. With selected set $S$ and
hashing-cosine similarity:

\begin{equation}
\label{eq:mmr}
\operatorname{MMR}(i\mid S)=\lambda\operatorname{rel}_i-(1-\lambda)\max_{j\in S}\operatorname{sim}(i,j).
\end{equation}

The first item is the maximum-relevance item; subsequent items are greedy.
Ties use relevance and then ascending candidate index. Thus $\lambda=1$ gives
the relevance order, while smaller values trade relevance for novelty. This is a
selection heuristic, not evidence that diversity improves answer truth.

**Inspector relevance and partitioning.** The Inspector loads the complete
transcript into an external, line-addressable state object. Only selected windows
are eligible for the Reasoner prompt. For query-token set $Q$ and non-empty
record $L_i$, its relevance is:

\begin{equation}
\label{eq:inspector-relevance}
\rho_i=\frac{|Q\cap U(L_i)|}{\lvert Q\rvert},\qquad \rho_i=0\text{ when }\lvert Q\rvert=0.
\end{equation}

When the record count exceeds `partition_threshold`, consecutive blocks $B_b$ of
`partition_size` records are scored by $\sum_{i\in B_b}\rho_i$. The Inspector
keeps $m=\max(1,\lfloor\texttt{max\_windows}/\texttt{partition\_size}\rfloor+1)$
highest-scoring blocks and fine-ranks records inside their union:

\begin{equation}
\label{eq:inspector-partition}
\operatorname{score}(B_b)=\sum_{i\in B_b}\rho_i,\qquad
\mathcal A=\bigcup_{b\in\operatorname{Top}_m(B)}B_b.
\end{equation}

The emitted confidence is the fraction of distinct query tokens covered by the
selected windows. It is a lexical coverage diagnostic, not a probability of
answer correctness. A discarded block cannot be recovered by later ranking, which
is why the Inspector can be identified as a bottleneck in a retained diagnostic
slice without making a universal causal claim.

## Added methods and their exact boundaries {#sec:added-methods}

The following optional methods compose with the base pipeline. Their code anchors,
tests, units, estimands, and limitations are generated in [@sec:method-traceability].

**Query expansion — PRF.** With `query_expansion=True`, an initial BM25 pass
returns $R$ top windows. After removing stopwords, original query terms, and
terms of length at most two, the feedback count is $c(t)=\sum_{d\in R}
\mathbf 1[t\in T(d)]$. Terms are appended in descending $c(t)$, then
alphabetical order, capped at `top_terms`:

\begin{equation}
\label{eq:prf}
q'=q\mathbin{\|}\operatorname{Top}_{K}\{t:\;(-c(t),t)\text{ is lexicographically smallest}\}.
\end{equation}

This is RM3-inspired deterministic feedback, not learned query expansion.

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
Source position is a temporal-order proxy, not elapsed time or a causal effect.

**Evidence budget.** For selected window texts $W$ the structural token estimate is
the shared-tokenizer count. Delivery is inline exactly when it fits the configured
budget:

\begin{equation}
\label{eq:evidence-budget}
\widehat n(W)=\sum_{w\in W}|T(w)|,\qquad
\operatorname{delivery}(W)=\begin{cases}\text{INLINE},&\widehat n(W)\leq B\\
\text{FILE\_BASED},&\widehat n(W)>B.\end{cases}
\end{equation}

This is not latency, prompt-token billing, memory consumption, or monetary cost.

**Citation-support proxy.** Let $C$ be cited source indices, $E_C$ their joined
excerpts, and $G$ the expected source-index set. Let $H=1$ when $C\cap G\neq
\varnothing$ and zero otherwise. The implementation uses:

\begin{equation}
\label{eq:grounding}
\operatorname{support}=\begin{cases}
\tfrac12H+\tfrac12F_1(\hat y,E_C),&G\neq\varnothing\\
F_1(\hat y,E_C),&G=\varnothing.
\end{cases}
\end{equation}

The name `grounding` is retained for backward-compatible aggregate fields, but
the permitted interpretation is citation-support token overlap. It is not
entailment, factual attribution, or line-level evidence grounding.

**Structural efficiency and composite score.** With $n=|R|$ ranked evidence
windows and scale $S={{CONFIG_EFFICIENCY_SCALE}}$:

\begin{equation}
\label{eq:efficiency}
E(R)=\max\left(0,1-\frac{n}{S}\right).
\end{equation}

The per-example composite is a fixed convex sum:

\begin{equation}
\label{eq:composite}
M={{CONFIG_WEIGHT_ACC}}A+{{CONFIG_WEIGHT_GROUND}}G+{{CONFIG_WEIGHT_EFF}}E.
\end{equation}

Its estimand is the finite-set mean of per-example scores unless a section states a
different unit. All observed failures remain in requested denominators in the
research ledger; optional model failures are separated from completed rows.

**Analysis connection.** The statistical layer uses explicit strata and seed
clusters. Its intervals are descriptive resampling diagnostics, with the small
cluster warning retained for the {{RESULT_AUDIT_SEED_COUNT}} seed clusters; they
are not ordinary population-coverage guarantees. This distinction applies to
every figure and caption that reports these quantities.
