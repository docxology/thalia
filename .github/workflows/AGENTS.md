# AGENTS.md — thalia/.github/workflows

`ci.yml` — "THALIA CI": runs on all pushes and PRs on ubuntu-latest, with
fail-fast disabled and contents: read only.

- Qualify Python 3.11, 3.12, 3.13, and 3.14. The matrix sets `UV_PYTHON` and
  asserts the actual runtime; do not let `.python-version` collapse the matrix.
  Python 3.15 is not qualified: optional development dependencies using PyO3
  cannot build there.
- Preserve reviewed immutable action commits and the external manuscript
  injection SDK commit. Its locked Python 3.14 runtime is independent of the
  THALIA matrix and uses explicit `--python 3.14`.
- Preserve the public LongMemEval download/validation, generated prerequisites,
  static gates, and `src/` coverage floor of 90%.
- Packaging runs after every matrix job and must exercise the installed wheel
  outside the checkout, without DSPy: `thalia-benchmark`, the benchmark Python
  API, and a real `thalia` query. Both benchmark paths account for six offline
  extractive observations, one per category, with validated report fingerprints,
  scores, prompts, and completion counts. Retain artifact regeneration/validation.
- Check names: `Python 3.11`, `Python 3.12`, `Python 3.13`, `Python 3.14`, and
  `Packaging and deterministic artifacts`. No aggregate status is configured.