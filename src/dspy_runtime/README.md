# dspy_runtime

DSPy integration: a real DSPy LM adapter over the deterministic extractive
LM, prompt/parse adapters, and live evaluation.

THALIA's configurators use memory-only SDK caching. They do not replay persisted
pickle-backed entries; direct DSPy callers that re-enable disk caching own that
trust decision. See the [security boundary](../../SECURITY.md) for the unresolved
optional DiskCache advisory. The base query/common-benchmark commands need no SDK.