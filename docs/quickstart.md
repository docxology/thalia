# Quickstart

All commands run from the repository root and point `uv` at the thalia project
environment.

## Install & verify

```bash
uv sync --project working/thalia
uv run --project working/thalia python working/thalia/scripts/00_preflight.py
uv run --project working/thalia pytest working/thalia/tests/ \
  --cov=working/thalia/src --cov-fail-under=90
```

## Run a query

```bash
uv run --project working/thalia python working/thalia/scripts/run_query.py \
  --query "What is the wifi password?" \
  --session-history "User: my wifi password is bluefish42" --json
```

Configure via a file, environment, or flags (lowest to highest precedence):

```bash
THALIA_TOP_K=4 uv run --project working/thalia python working/thalia/scripts/run_query.py \
  --query "..." --config working/thalia/config/harness.yaml --rerank mmr --verify \
  --adaptive-windows --adaptive-window-ratio 5
```

## Multi-turn session (Python)

```python
# Run from the thalia dir (`cd working/thalia`) so `src` is importable.
from src.session import Session
with Session(db_path="episodes.db", memory_path="MEMORY.md") as s:
    s.ask("My wifi password is bluefish42")
    print(s.ask("What is the wifi password?").answer)
    print("turns:", s.turn_count)
# Session.close() is called automatically on __exit__
```

`Session` (and `EpisodicStore`) implement the context-manager protocol so the
SQLite connection is always closed, even on exception.

## Regenerate artifacts

```bash
uv run --project working/thalia python working/thalia/scripts/run_harness_eval.py
uv run --project working/thalia python working/thalia/scripts/run_compiler.py
uv run --project working/thalia python working/thalia/scripts/generate_figures.py
uv run --project working/thalia python working/thalia/scripts/build_dashboard.py
uv run --project working/thalia python working/thalia/scripts/z_generate_manuscript_variables.py
uv run --project working/thalia python working/thalia/scripts/run_demo.py
uv run --project working/thalia python working/thalia/scripts/run_pipeline.py
```
