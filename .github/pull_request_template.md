## Summary

<!-- What changed, and why? Keep scientific claims bounded by the evidence. -->

## Validation

- [ ] `pytest` with the 90% `src/` coverage gate
- [ ] `mypy src`
- [ ] `ruff check src tests scripts`
- [ ] `compileall`, `uv lock --check`, and `uv build`
- [ ] Artifact/manuscript/render checks, if applicable

## Release and data hygiene

- [ ] No secrets, private raw answers, credentials, or unrelated worktree files
- [ ] Generated outputs are regenerated from source or intentionally omitted
- [ ] New claims include provenance, estimand, uncertainty, and limitations
- [ ] Negative controls and failed gates are preserved
