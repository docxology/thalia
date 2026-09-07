# AGENTS.md — thalia/src/dspy_runtime

Real DSPy runtime integration. `runtime.py` — DSPy program builders and
`ExtractiveDSPyLM` (a real `dspy.BaseLM` backed by the project's
deterministic ExtractiveLM). `adapters.py` — prompt rendering, field
parsing, completion formatting, qa_metric; default endpoints for local
Ollama and OpenRouter (`ENV_OPENROUTER_KEY` for the key). `live_eval.py`
— live evaluation harness. Stage metrics come from `compiler.metrics`
(e.g. token_f1).