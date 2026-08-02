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
