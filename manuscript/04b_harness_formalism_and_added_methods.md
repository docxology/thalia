# Harness Design: Formalism and Added Methods {#sec:harness-formalism-added-methods}

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
