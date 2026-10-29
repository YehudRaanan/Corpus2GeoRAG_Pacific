# Unresolved 100-page evidence audit

> Execution: use Superpowers executing-plans, with independent parallel reviews.

**Status:** Complete. OWNER approved 45-90-minute local audit; execution started at
16:31:45 on 29 October 2026, Asia/Jerusalem (UTC+02).
**Goal:** Account for all 18,110 non-DATE unresolved original rows in 11,712
saved corrected groups, with evidence, explicit unknowns and practical next actions.
**Spec:** OWNER's request to investigate Unresolved after the completed template/name
pilot; classification proposal accepted with "go ahead" on 29 October 2026.
**Architecture:** Reuse saved exports, reference, inventories, source-span bridges,
candidate jobs and scores. One local audit script; no pipeline or model changes.
**Stack:** Existing task Python environment, standard library and installed PyArrow.

## Rules

- No training, inference, network collection, cloud spending, assignment changes,
  reference-label changes, DATE processing or full-corpus run.
- Preserve all existing outputs and unrelated edits. New versioned audit outputs only.
- A missing reference is not proof of a missing QID. Candidate exposure is not proof
  of identity. A model rejection is a pipeline stage, not necessarily a model error.
- Source-context, partial-name and general-word flags remain hypotheses unless the
  saved source evidence establishes the intended entity.
- Preserve many-to-many links and the agreed grouping policy. Report rows and groups
  separately. Multiple contributing flags can overlap; never sum them as disjoint.
- Only a supported expected QID permits a specific inventory/retrieval/decision-stage
  diagnosis. Other cases retain UNKNOWN_IDENTITY, with useful evidence flags.
- AI source review is explicitly marked AI review, never human gold.

## Tasks, ownership and checks

All work is in D:/Projects/GeoAI-luke-pilot-20261028. Root alone owns Git,
the integration script, tests, final report and state. Reviewers read shared inputs;
each writes only its own output subdirectory. No shared remote resource is needed.

| Task | Owner | Dependencies / output | Exit check |
|---|---|---|---|
| 1. Inventory and diagnostic design | root | Saved summary, exports, existing diagnose.py; this plan | Verify 18,110 rows, 11,712 saved groups, 1,159 rows with reference positives; preserve input hashes. |
| 2. Candidate and decision evidence | candidate reviewer | Saved groups/jobs/scores/reference; audit candidate_review/ | Reconcile all supported unresolved row/QID pairs; show ranks, inclusion and saved stop decisions where available; explicit unknowns otherwise. |
| 3. Source and inventory evidence | source reviewer | Saved revisions, target evidence, bridges, inventories; audit source_review/ | Identify source-supported targets absent from inventory versus available targets; distinguish historical evidence from current mapping. No guessed gold. |
| 4. Span and label evidence | span reviewer | Original/prepared mentions, source bridges; audit span_review/ | Account for partial/general/ambiguous spans, missing usable labels and unsupported repairs with evidence and uncertainty. |
| 5. Reproducible integration | root | Tasks 2-4; one audit.py, focused test file, case-level Parquet/CSV and summary.json | Every unresolved original row appears exactly once; all 11,712 saved groups accounted for; DATE excluded; evidence flags and primary supported-stage/unknown fields separate. |
| 6. Independent check and report | reviewer + root | Task 5; verification.json and docs/reports/2026-10-29-unresolved-100-page-audit.md | Counts reconcile; unchanged-input hashes; representative examples have source provenance; ranked next actions distinguish measured opportunities from hypotheses. |

- [x] Read current results and prior diagnostic implementation; verify scope.
- [x] Apply Ponytail full, Superpowers writing-plans and Epoch to the same scope.
- [x] Obtain required duration approval.
- [x] Run tasks 2-4 in parallel, with exclusive output directories.
- [x] Integrate evidence using one simple script; add focused tests for overlaps,
  duplicate rows, missing labels and unknown identities.
- [x] Run local audit; verify complete denominators and unchanged input hashes.
- [x] Independent review; report main unresolved groups and proposed remedies.

Completion evidence: unresolved_audit_100/summary.json and verification.json,
candidate_review/final_output_review.json and report_review.json, plus the
source_review/reference_quality_verification.json supplement. All 18,110 original
rows and 11,712 saved groups are covered; six tests, Ruff and Black pass. No data
assignments, frozen labels, collection, inference or training changed. Completion
time, runtime basis, issues and backup limitations are in completion.json.

## Estimate and checkpoints

Estimate v1: 45-90 minutes total elapsed execution, including preflight from about
16:25 Asia/Jerusalem (UTC+02), excluding approval and environment waits. Independent
reviews overlap; integration and final verification follow them. Model-derived,
not an empirically calibrated task forecast. Epoch O/M/P: 0.75/1.10/1.50 hours;
raw expected 1.11 hours; feedbackRef a3e94296-554a-4695-bbe2-539976297948.
Do not substitute the tool's display correction or broad testing reference class
for this explicit full evidence-audit scope. Superpowers breakdown and Epoch inputs
have the same scope, dependencies, hour units and elapsed basis; no remaining conflict.

At approval near 16:30, expected completion is approximately 17:15-18:00 on
29 October 2026, Asia/Jerusalem (UTC+02). First execution checkpoint ten minutes
after approval, then every 5-10 minutes. These are behavioral checkpoints, not
mechanically enforced timers. Approval/environment waits and active work must be
tracked separately; unmeasured intervals remain unknown.

## Deliverables and protection

New local directory under template_name_pilot_20261029/unresolved_audit_100/:
audit.py, focused tests, reviewer evidence, row/group case files, summary,
verification and runtime/problem log. No prior output is overwritten.
Report contains counts, evidence-backed examples, unknowns and a prioritized
repair plan. No fixes are silently applied.

Current branch experiment/luke-decision-pilot-20261028 at c282dfd has no upstream.
No push is authorized. Ignored audit data remain local; report code protection
accurately at handoff. Preserve the existing evaluate.py edit and older untracked
three-page audit plan/report.
