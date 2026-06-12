# Configuration

The tunable parameter vector is `HarnessConfig` (`src/config.py`). It is frozen,
hashable, validated on construction, and serialisable.

## Fields

| Field | Default | Meaning |
| --- | --- | --- |
| `max_windows` | 15 | Inspector cap on emitted windows |
| `top_k` | 8 | Retriever cap on ranked evidence |
| `rrf_k` | 60 | RRF damping constant |
| `lexical_weight` / `semantic_weight` | null/null | Lane weights (both-or-neither; null → per-category defaults) |
| `context_budget_tokens` | 2048 | Inline-delivery token budget |
| `max_evidence` | 5 | Reasoner cap on evidence considered |
| `rerank` | `rrf` | Re-ranking strategy: `rrf` or `mmr` |
| `mmr_lambda` | 0.7 | MMR relevance/diversity tradeoff [0,1] |
| `verify` | false | Reasoner grounding-verification pass |
| `grounding_threshold` | 0.3 | Min answer-in-evidence support before re-answering |
| `partition_threshold` | 40 | Inspector record count above which recursion runs |
| `partition_size` | 10 | Block size for recursive partitioning |
| `query_expansion` | false | Pseudo-relevance-feedback query expansion |
| `expansion_terms` | 5 | Feedback terms appended when expanding |
| `recency_weight` | 0.0 | Recency bonus in [0,1] favouring later turns |
| `recall_memory` | false | Consult episodic store + MEMORY.md for evidence |
| `recall_limit` | 3 | Maximum recalled evidence windows |
| `adaptive_windows` | false | Scale the Inspector window budget with context size (no-op on compact contexts) |
| `adaptive_window_ratio` | 5 | When adaptive: keep ~one window per this many session lines |

## Sources and precedence

Lowest to highest: **built-in defaults → YAML file → `ATLAS_*` environment →
explicit CLI flags**.

- **File:** `load_config(path)` reads `config/harness.yaml` (flat, or under a
  `harness:` key). `save_config(config, path)` writes YAML.
- **Environment:** every field maps to `ATLAS_<FIELD>` (e.g. `ATLAS_TOP_K=4`,
  `ATLAS_RERANK=mmr`, `ATLAS_VERIFY=true`). Booleans accept `1/true/yes/on` and
  `0/false/no/off`. Lane weights stay both-or-neither.
- **CLI:** `--top-k`, `--max-windows`, `--max-evidence`, `--rrf-k`,
  `--context-budget`, `--rerank`, `--mmr-lambda`, `--verify`, `--query-expansion`,
  `--recency-weight`, `--recall-memory`, `--adaptive-windows`,
  `--adaptive-window-ratio`, plus `--config`.

## Programmatic

```python
from src.config import load_config, default_config
cfg = load_config("config/harness.yaml").with_(top_k=4, rerank="mmr")
cfg2 = default_config().with_(verify=True, grounding_threshold=0.5)
```

`with_(**changes)` returns a validated copy; `to_dict`/`from_dict` round-trip a
config (unknown keys ignored).
