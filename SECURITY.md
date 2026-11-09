# Security policy

THALIA is a research package, not a hosted service. It can nevertheless be
used with local language models, session histories, SQLite stores, external
retrievers, and user-provided prompts. Please report security-sensitive issues
responsibly rather than publishing exploit details first.

## Reporting a vulnerability

Email **daniel@activeinference.institute** with:

- the affected commit or package version;
- a concise description of the impact;
- reproducible steps or a minimal test case;
- whether the issue requires a live LM, external data, or a particular
  configuration; and
- any suggested mitigation.

Do not include credentials, private benchmark data, raw user transcripts, or
confidential model outputs in a report. Redact them or use synthetic fixtures.

The project does not promise a fixed response-time SLA or security-support
window. Reports are triaged as the maintainer's capacity permits, and a fix
may be accompanied by a test, documentation change, or release note.

## In-scope concerns

Examples include unintended disclosure from context selection or memory
consolidation, unsafe path or SQLite handling, dependency/build compromise,
prompt-injection or context-poisoning bypasses, and insecure use of optional
live-model integrations. The MIT license does not grant rights to redistribute
third-party data, model weights, credentials, or private research artifacts.

## Optional SDK cache boundary

[CVE-2025-69872 / GHSA-w8v5-vhqr-4h9v](https://github.com/advisories/GHSA-w8v5-vhqr-4h9v)
reports unsafe pickle deserialization in `diskcache` through version 5.6.3.
GitHub reports no patched version. This dependency remains in the optional
DSPy stack; it is not part of THALIA's base installation. A dependency alert
remaining open is not a security certificate or a reason to dismiss the alert.

THALIA's `configure`, `configure_ollama`, and `configure_openrouter` helpers
disable DSPy's persistent disk cache before configuring a backend. In-memory
caching remains available. This prevents these helpers from replaying persisted
SDK entries; it does not patch DiskCache, authenticate old cache files, or
protect callers that independently re-enable persistent caching.

For direct DSPy use outside those helpers, disable its disk cache before model
calls:

```python
import dspy
dspy.configure_cache(enable_disk_cache=False)
```

Never load shared, downloaded, or otherwise untrusted pickle caches. Protect
any deliberately enabled cache with owner-only filesystem permissions; do not
share model/user data through it. The SDK-free `thalia` and `thalia-benchmark`
commands, including their direct Ollama/OpenRouter clients, neither import
DSPy nor use its cache.

The current `dev` and `neural` extras require `filelock>=4.2.1`, and the lock
integrates Dependabot's repair for the reported local filesystem/locking
advisories. The resolver selects compatible LiteLLM 1.103.10; DSPy remains
3.2.1. This is a bounded dependency repair, not a claim that all dependencies
or configurations are vulnerability-free.
