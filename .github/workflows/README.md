# workflows

`THALIA CI` runs on every push and pull request. Its test matrix qualifies
Python 3.11, 3.12, 3.13, and 3.14, with `UV_PYTHON` selecting each job's actual
runtime instead of the checkout's Python 3.13 default. Python 3.15 is not
qualified because optional development dependencies using PyO3 cannot build
there. The pinned external manuscript SDK separately runs on Python 3.14.

Each matrix job checks the lockfile, whitespace, compilation, types, lint, the
real public LongMemEval download/validation, generated test prerequisites, and
tests with at least 90% coverage of `src/`.

After the full matrix passes, packaging builds and inspects the wheel, installs
it into a fresh environment outside the checkout, and checks the actual installed
`thalia-benchmark` and `thalia` commands and Python APIs without DSPy. Both
benchmark paths must produce six complete offline extractive observations, one
per task category, with matching cohort/prompt identities and validated scores,
fingerprints, and requested/completed/failed accounting. The default benchmark
output must be relative to the caller's working directory. The query must
retrieve the supplied wifi password with citations. The job also regenerates
and validates the deterministic artifacts.

The exact check names to gate before merging or releasing are:

- `Python 3.11`
- `Python 3.12`
- `Python 3.13`
- `Python 3.14`
- `Packaging and deterministic artifacts`

There is no aggregate status job. Keep action and SDK revisions pinned to the
reviewed immutable commits; do not weaken coverage, benchmark, or artifact gates.