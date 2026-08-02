# P0 adjudicated provenance confirmation

This is the execution contract for the P0 tier in
[`integrity_advantage_handoff.md`](integrity_advantage_handoff.md). It is a new
evidence lane. It neither reuses nor promotes the legacy 30-probe lexical
cited-excerpt/source-exposure proxy in `data/injection_eval.json`.

## What is frozen

`src/evaluation/provenance_p0.py` accepts a reviewed protocol draft and freezes
it with a canonical SHA-256 digest. The draft must include immutable source
records and their text hashes, claim text, execution and scorer-safe task
queries, source order, attack families, answer types, a frozen/re-hashed human
rubric and scorer version, four condition records, the complete Holm endpoint
family, safety margins, and an evidence-bound
admission record for both the held-out family and an independent rerun. The
scorer-safe query must not expose the task ID or attack-family label.

The P0 design uses 120 attacked matched probes: six named attack families with
20 probes each. It also requires 20 separate clean negative controls (five per
answer type), for 140 probes and 560 condition rows per run. This resolves the
handoff's `6 × 20` attack requirement without silently omitting its separate
clean-control requirement.

The four fixed conditions are THALIA, naive full context, citation-disabled
THALIA (an output-projection mechanism control), and an oracle true-source
ceiling control. The oracle is never a deployment baseline. Citation-disabled
THALIA must retain the same answer, delivered context, retrieved-source trace,
and model/config/code receipts as full THALIA; it only removes the emitted
citation channel from its outcome record.

The protocol refuses to freeze until the owner explicitly declares both margins
(`max_correctness_decrease` and `max_false_source_citation_increase`) and an
independent-rerun admission criterion with a retained digest. It also requires
a retained admission that names the held-out attack family and confirms that it
was not used for fixture-development decisions. Those values are not inferred
from the legacy screen.

## Evidence flow

Raw execution writes one immutable `P0RunRow` for every
run × probe × condition. Each row binds the canonical input, delivered-context,
delivered-source IDs, source records and excerpts, answer, claim-linked citation
source/index hashes, raw-record path/hash, and model/config/code digests. A
separate retained run receipt binds every row in each run to a real, distinct
execution artifact.
Each `raw_path` must name a distinct JSON document containing a matching
`p0_run_row` projection; opaque hash-only placeholders do not satisfy the gate.
Failed rows are retained rather than dropped.

The contract enforces the four conditions: naive full context receives all
frozen source records and no citation channel; citation-disabled THALIA is an
otherwise identical output projection with no citations; and the oracle receives
only the correct source record. Cited excerpts must be exact spans of delivered
frozen records and must name the claims they support. Source recall, precision,
and false-source citations are mechanically cross-checked against those records
as well as shown to the human scorer.

The packet-builder produces two files:

- an expert-facing packet JSONL with family/condition/task/source-role labels
  removed, only sources actually delivered to that condition, rekeyed source
  IDs, atomic claim text, per-claim citation traces, and packet order keyed by a
  secret salt; and
- an internal blind-key JSONL mapping those packets to raw rows and claim IDs.

It also produces a sealed blinding manifest that commits to the frozen protocol,
complete-row ledger, packet/key ledgers, randomized order, and a hash commitment
to the private salt. The analysis refuses a packet/key/manifest mismatch. This
is the required shuffled source-ID metadata control: it prevents raw source IDs
or deterministic condition order from inflating the human score; it is not a
separate answer-quality result.

The labels are family- and condition-name-blinded, rather than claiming perfect
condition blindness: citation presence or source-record count can remain
observable. Only a
`blinded_expert_human` adjudication is accepted. Local-LLM judging is rejected
by the P0 schema.

Claim-level adjudications derive the primary outcome: every evaluated claim must
have a recoverable correct source, an entailing/provenance-complete citation, and
no cited contradiction. Answer correctness, source recall/precision, false-source
citation, poisoned answer, citation faithfulness, and provenance completeness
remain separate endpoints. The conditioned auditability-on-correctness rate is
descriptive and retains its condition-specific denominator.

The report includes all probes (including clean controls) and a descriptive
source-condition × answer-type × provenance-channel table for clean, one-false,
multiple-false, and temporal-update sessions. Every attack family must cross the
three non-clean source conditions, while each family retains at least 20 probes
and each answer type at least five. It fits no pooled interaction model; this is
the explicit provenance-versus-poisoning separation record.

## Commands

All actual raw rows and human adjudication records belong outside committed
`data/`, for example in an access-controlled P0 evidence root. A fixture-only or
partial run is intentionally reported as `incomplete` or `complete_not_promoted`.

```bash
# Review a draft first. It needs source records, 140 probes, margins, and an
# independent-rerun admission record; freezing writes protocol_sha256.
uv run --project . --extra dev python scripts/freeze_provenance_p0.py \
  /secure/p0/protocol-draft.json /secure/p0/protocol.json

# Raw rows are produced by the real experimental runner, then packets are built.
# Keep the blind key internal and do not send it to adjudicators.
uv run --project . --extra dev python scripts/build_provenance_p0_packets.py \
  --protocol /secure/p0/protocol.json \
  --rows /secure/p0/rows.jsonl \
  --run-receipts /secure/p0/run-receipts.jsonl \
  --packets /secure/p0/blinded-packets.jsonl \
  --blind-key /secure/p0/internal-blind-key.jsonl \
  --blinding-manifest /secure/p0/blinding-manifest.json \
  --blind-salt "$THALIA_P0_BLIND_SALT"

# This validates all expected rows, hashes, human adjudications, paired
# strata-aware intervals, McNemar tests, and one declared Holm family.
uv run --project . --extra dev python scripts/analyze_provenance_p0.py \
  --protocol /secure/p0/protocol.json \
  --rows /secure/p0/rows.jsonl \
  --packets /secure/p0/blinded-packets.jsonl \
  --blind-key /secure/p0/internal-blind-key.jsonl \
  --blinding-manifest /secure/p0/blinding-manifest.json \
  --adjudications /secure/p0/adjudications.jsonl \
  --evidence-root /secure/p0 \
  --output /secure/p0/report.json

# Promotion re-hashes and rebuilds the retained typed evidence before comparing
# it to the report certificate, then requires a named acceptance record.
uv run --project . --extra dev python scripts/promote_provenance_p0.py \
  /secure/p0/report.json data/provenance_p0_results.json \
  --evidence-root /secure/p0 \
  --acceptance /secure/p0/acceptance.json
```

`rows.jsonl`, run receipts, packets, blind key, blinding manifest,
adjudications, protocol, frozen rubric, and every atomic raw execution,
run-receipt, and adjudication record must reside below the evidence root. The
report binds their typed content and file digests. Initial and rerun rows must
have distinct retained execution receipts; the rerun and designated held-out
family must each have a 95% interval above zero. The directional lower 95%
bound must also satisfy each predeclared correctness and false-source safety
margin before the report can become eligible.

`promotion_eligible` is only a statistical/evidence gate; the last command is
the separate, explicit release action. A successful P0 promotion still does not
establish general answer quality, poisoning resistance, security, or population
performance.
