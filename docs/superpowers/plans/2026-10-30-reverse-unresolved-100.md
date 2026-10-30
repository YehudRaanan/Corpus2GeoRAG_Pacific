# Reverse matching of all remaining pilot mentions

> For execution: use Superpowers executing-plans or subagent-driven-development.

**Goal:** Test whether remaining Daniel mentions select a QID from their own saved
Wikipedia page and revision, using existing weights without retraining.

**Architecture:** Separate experimental run. Reuse the canonical LUKE scorer and
the tested reversed text format. Preserve all production assignments. Stream and
checkpoint scores by group; join proposals only to explicit remaining mention IDs.

**Tech stack:** Existing Python environment, PyArrow, Torch and Transformers; one
existing GCP L4 VM. No new libraries, data collection, paid BigQuery or training.

## Verified inputs and boundaries

- 100 pages, 130 saved revisions with remaining mentions.
- 13,129 eligible unassigned occurrences: 5,852 previous model-unresolved and
  7,277 previously blocked review occurrences. Report both cohorts separately.
- 9,016 literal name/type/page/revision groups. Exclude assigned occurrences first.
  Reuse `prepare_candidates.group_mentions` to rebuild remaining-only contexts.
  577 groups have other assigned occurrences: never copy proposals to these.
- DATE remains deferred; excluded source content remains excluded.
- All saved same-page/revision QIDs are options, with no trigram limit. Missing
  labels in 29 inventory records use saved linked titles, explicitly marked as
  title fallbacks. No external lookup is implied. Maximum pool: 625 QIDs.
- 1,790,387 candidate-plus-stop scores. Some groups contain repeated occurrences;
  score each group once and retain all remaining occurrence IDs.
- Same checkpoint SHA256 as the 12-case experiment; same 256-token pair format.
- Reverse stop: "This mention does not refer to any of the remaining entities."
  This wording and direction were not trained. Selection is experimental.
- First decision per group: highest QID above stop, otherwise unresolved. Stop
  wins ties. QID ties use a recorded deterministic order and are flagged. Save all
  candidate scores for inspection; do not impose one-to-one entity constraints.

Prepared immutable evidence is in
`Data/external/reverse_unresolved_100_20261030/ready.json`, with source/checkpoint
hashes, `remaining_groups.jsonl` and `entities_ready.parquet`. Earlier preflight
files retain the original named-only count for audit; use ready.json for execution.

## Execution tasks and owners

- [x] Root: inspect saved assignments, freeze remaining occurrences and candidate
  inventories, verify counts and resource/budget evidence. Read-only reviewer
  independently confirmed counts and found the mixed-occurrence risk.
- [ ] Root: implement one separate reverse-run script with prepare/score/report
  responsibilities clearly marked; reuse existing scorer/text helpers. Add the
  smallest useful checks for page/revision boundaries, occurrence preservation,
  stop/tie behavior, resume bindings and score completeness.
- [ ] Reviewer, parallel: inspect frozen inputs and changed code, without sharing
  write ownership of root's files. Root owns Git, cloud CLI, transfer and the GPU.
- [ ] Root after tests: verify budget, checkpoint, stopped VM and STOP guard; start
  only `geoai-luke-pilot-20261028`, project geo-hagai-ndvi, us-central1-c.
- [ ] Root: check reversed CPU/GPU reference behavior on a small fixed sample;
  report numerical differences. Run the old unresolved cohort first, then newly
  admitted review occurrences; groups spanning both cohorts are scored once.
- [ ] Root: checkpoint each completed group and runtime. Enforce a 90-minute
  additional VM-running cap, including setup. Do not exceed the six-hour aggregate
  GPU or $10 aggregate limits. On capacity failure, report and wait; do not create
  another VM or switch to an unbounded CPU run.
- [ ] Root: transfer and hash-verify outputs, confirm VM stopped, then produce
  occurrence/group counts, proposals, remaining stops, top alternatives, examples,
  score margins, tie counts, runtime and cost estimates. Distinguish model
  proposals from verified correct identities. No production-table promotion.

Dependencies: input freeze -> code/tests/review -> GPU restore/parity -> scoring
-> verified transfer and stopped VM -> report. Resume must reuse exact input,
checkpoint, code and prompt bindings. Never rescore completed groups silently.

## Estimate and approval gate

Ponytail: reuse saved data and model; no retraining, collection or pipeline refactor.
Superpowers breakdown and independent read-only review agree on the same scope,
dependencies and elapsed-time basis. Epoch PERT reference:
`d86a17ef-cbd7-41bb-bc0c-f4a936aaf45e` (O/M/P 2/2.5/3 hours).

Total model-derived elapsed estimate: **2–3 hours**, including preflight from
2026-10-30 02:38:48 Asia/Jerusalem (UTC+02), excluding OWNER approval and GPU
capacity waits. Precise active work is unknown; waits and model runtime are
recorded separately. First execution checkpoint: ten minutes after approval.
If approved near 02:46, completion is expected near 04:46–05:46 on 30 October.

GPU reference: previous 668,050 pairs in 1,630.55 seconds (~410/s); this implies
about 73 minutes of scoring, not a measured reverse-GPU benchmark. The 90-minute
cap leaves limited setup margin; a checkpointed partial run may be necessary if
actual throughput is slower. Do not exceed the cap to finish.

Saved prior VM time: 15,828.011 seconds; plus 5,400 = 21,228.011, below 21,600.
Saved conservative aggregate estimate: $6.4967; plus at most $1.50 compute gives
about $8.00, within $10 including the existing reserve. This is not actual billing.
Live read verified the existing VM is TERMINATED, its last stop agrees with the
saved ledger and its max-run STOP setting is 5,400 seconds. Recheck before start.

**Status:** preflight ready; full implementation/inference awaits explicit OWNER
duration approval under the AGENTS.md rule for tasks over 20 minutes. No GPU was
started, no inference was run and no assignments were changed by preflight.

## Verification focus

- A proposal never crosses its exact page/revision boundary.
- No previously assigned, DATE or source-excluded occurrence enters targets.
- Mixed groups carry only explicit remaining occurrence IDs and their contexts.
- Each remaining target appears once and every QID option receives a finite score.
- Interrupted output is resumable with binding validation and original evidence.
- A selected QID is a proposal, not proof of correctness or a measured accuracy.
