# `data/` — Agent contract

## claim_ledger.yaml

Each entry registers a numeric claim that is *intentionally* sourced from code or a
generated artifact rather than a `{{TOKEN}}`:

```yaml
- claim_id: <kebab-id>
  kind: number
  value: <the literal value>
  source: <description of where it comes from>
  source_tier: project_source | generated_metric | manuscript_claim
  freshness: active
  artifact_path: <path that backs the value>
```

## Rules

- When you add a hard-coded numeric to the manuscript that is not a generated
  token, register it here with its backing artifact, or convert it to a token in
  `src/manuscript_variables.py`.
- `value` must match the cited source; if the source changes, update the ledger.
- Do not register secrets or per-run volatile values; generated metrics that drift
  should be tokens, not ledger entries.
