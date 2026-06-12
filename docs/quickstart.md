# Quickstart

All commands run from the repository root and point `uv` at the atlas project
environment.

## Install & verify

```bash
uv sync --project working/atlas
uv run --project working/atlas python working/atlas/scripts/00_preflight.py
uv run --project working/atlas pytest working/atlas/tests/ \
  --cov=working/atlas/src --cov-fail-under=90
```

## Run a query

```bash
uv run --project working/atlas python working/atlas/scripts/run_query.py \
  --query "What is the wifi password?" \
  --session-history "User: my wifi password is bluefish42" --json
```

Configure via a file, environment, or flags (lowest to highest precedence):

```bash
ATLAS_TOP_K=4 uv run --project working/atlas python working/atlas/scripts/run_query.py \
  --query "..." --config working/atlas/config/harness.yaml --rerank mmr --verify \
  --adaptive-windows --adaptive-window-ratio 5
```

## Multi-turn session (Python)

```python
from src.session import Session
s = Session(db_path="episodes.db", memory_path="MEMORY.md")
s.ask("My wifi password is bluefish42")
print(s.ask("What is the wifi password?").answer)
s.close()
```

## Regenerate artifacts

```bash
uv run --project working/atlas python working/atlas/scripts/run_harness_eval.py
uv run --project working/atlas python working/atlas/scripts/run_compiler.py
uv run --project working/atlas python working/atlas/scripts/generate_figures.py
uv run --project working/atlas python working/atlas/scripts/build_dashboard.py
uv run --project working/atlas python working/atlas/scripts/z_generate_manuscript_variables.py
uv run --project working/atlas python working/atlas/scripts/run_demo.py
```
