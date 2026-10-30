# Shared QID filters and bidirectional comparison implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Apply the same article-content and type rules before exact, normal and reverse matching, then compare experimental proposals on the saved 100 pages.

**Architecture:** One shared filter step writes a scoped QID inventory and source/type evidence. Pair compatibility is shared by both model directions and the final assignment validator. Existing source parsing, type metadata, checkpoint and scoring code are reused; saved assignments are immutable.

**Tech Stack:** Existing Python environment, PyArrow, mwparserfromhell, pytest, PyTorch/LUKE; no new dependencies.

**Spec:** Current OWNER request: try the proposed type mapping and exclude QIDs supported only by excluded article regions in both directions. Content filtering must apply throughout the pipeline.

## Global constraints

- This is a plan awaiting explicit duration/resource approval; no full inference is authorized yet. The preceding unfiltered reverse run was declined.
- Scope: saved 100 pages and exact revisions. Remaining cohort: 13,129 occurrences in 9,016 groups; 5,852 previously unresolved and 7,277 newly admitted review occurrences. Do not mix assigned occurrences back into these groups.
- Preserve original rows, existing assignments, all source evidence and old outputs. New outputs are experimental proposals, not reference labels.
- DATE deferred. REVIEW is advisory, never a veto. No retraining, Geography, paid BigQuery, new collection, full-corpus rerun or new VM.
- Aggregate limits remain US$10 and six GPU hours. Existing VM only, maximum 90 additional running minutes, subject to fresh aggregate-budget checks and explicit approval. Stop safely before the lower remaining limit; never silently enlarge a limit.
- Prior conservative estimate is US$6.50, not actual billing. Prior running time is 15,828.011 seconds; live checks must verify these inputs before a restart.
- Minimal meaningful files; no broad refactor. Root owns integration, Git and GPU. Parallel workers use disjoint files or read-only review.

## Rules

1. Join every source occurrence by `(page_id, revision_id, qid)`. Classify exact raw anchors with the existing `source_intervals` and `classify_span`. Include original direct-link and recovered-template evidence.
2. Keep a QID if any support is KEEP or REVIEW. Keep verified page identity. Remove only when all recorded support is proved EXCLUDE and evidence coverage is complete. Incomplete support stays UNKNOWN_KEEP, with its reason; this is not proof of article presence.
3. Pair-level type rules: PER people; ORG organisations/military units; LOC places/geographic facilities using existing roots; MISC unrestricted; DATE deferred. Multiple categories are allowed. Missing or incomplete ancestry remains eligible and marked unknown. Never infer incompatibility from label text.
4. Use native P31 plus cached P279 traversal. Record both snapshots: hierarchy cache 2026-10-18 and inventory native metadata 2026-10-25. The hierarchy cache has 544,375 records, SHA256 `0032e97cf9af90f56dae231071dbdd2bed8d9c379708a029c4a53b407a9378f8`.
5. Feed the filtered inventory into exact matching before uniqueness checks, normal candidate preparation before trigram/protection/coverage, reverse pools, and final accepted-pair validation. Previously saved decisions cannot restore banned pairs.
6. Exact matching retains the agreed literal-name/one-QID/one-Daniel-type rule. Changes caused by filtering are reported separately; no historical assignment is overwritten.
7. Normal direction: QID query, compatible mention options, existing trigram policy and iterative stop rule. Reverse: remaining mention query, every compatible QID on that exact page/revision, no trigram cutoff. Keep both directions' proposals separate; no automatic conflict resolution.
8. Preserve checkpoint, text formatting and stop rules. Reverse stop is untrained: `This mention does not refer to any of the remaining entities.` Report this limitation.
9. Reuse a saved forward scalar only for the identical ordered encoded pair, checkpoint, tokenizer and encoding settings. IDs alone are insufficient. Changed contexts need scoring; forward scores cannot replace reverse scores.

## Review focus

- A QID in both bibliography and body must survive.
- Recovered templates, page identity and incomplete source evidence must not disappear through a direct-link-only join.
- Missing hierarchy parents and overlapping LOC/ORG classes must not produce false incompatibility.
- Trigram coverage/protected-candidate code and stale saved decisions must not bypass the shared predicate.
- Mixed assigned/unassigned groups, changed context text, and equal stop scores must retain existing safety rules.

## Tasks and dependencies

### 1. Freeze evidence and count pools — root, read-only workers
- [x] Inspect source-support insertion points and score reuse requirements.
- [x] Verify local hierarchy cache and offline type coverage.
- [x] Count type-only reverse pools: 1,790,387 -> 1,009,027 candidate-plus-stop scores (43.64% reduction); 981 inventory records have missing/incomplete type data and remain eligible.
- [x] Complete source-only count: 599 of 13,470 page/revision/QID records excluded; 12,871 retained (12,707 KEEP and 164 REVIEW_KEEP). Distinct QIDs decrease from 5,072 to 4,874. Verified 132 revision files, raw hashes, source offsets and page-own supports; no unknown source-support gaps were found.
- [ ] Complete combined pool counts and persist the case-level exclusion ledger during implementation.
- [ ] Freeze input hashes, cohort definitions and estimate basis in the new output manifest.

### 2. Shared filtering — implementation owner A; depends on task 1
Create `GG_Data/entity_resolution/hundred_page_pilot/filter_qid_inventory.py` and `test_filter_qid_inventory.py`.
Interfaces: `filter_inventory(entities, evidence, raw_root, type_metadata)` produces retained rows plus source/type audit; `compatible(entity, mention_type)` returns eligibility and reason. Use existing records/dicts, not a new framework.
- [ ] Add failing tests for mixed body/reference support, excluded-only support, unknown evidence, template anchors, page identity, complete/incomplete ancestry, overlapping categories and broad MISC.
- [ ] Run focused pytest, implement minimal functions and CLI, rerun tests.
- [ ] Write fresh filtered inventory and ledger; compare each removal against raw evidence. Check independently labelled examples and report any conflict before promotion.

### 3. Pipeline wiring — root, depends on task 2; test preparation can run in parallel
Modify `match_exact.py`, `prepare_candidates.py`, the existing workflow entry points and `GG_Data/pipeline/post_qid_entities.py` only where needed. Reuse existing tests in `test_revised_input_candidates.py`, `test_source_candidates.py` and `GG_Data/pipeline/test_post_qid_entities.py`.
- [ ] Add failing tests: incompatible exact pair rejected, filtering before ranking, coverage cannot restore banned pair, final validator rejects stale banned pair, unknown remains eligible, REVIEW admitted and DATE deferred.
- [ ] Wire the common inventory and predicate, with an explicit manifest policy version. No independent per-direction rules.
- [ ] Run focused pytest and installed lint/format checks on touched files.

### 4. Bidirectional experiment — root sole GPU owner; depends on tasks 2–3 and approval
Reuse normal scorer/decision loop and the reverse ordering in `decision_model/probe_reverse.py`. Add one focused batch experiment runner if existing orchestration cannot express both directions safely.
- [ ] Build immutable normal/reverse jobs from remaining-only groups. Verify exact page/revision boundaries and counts; distinguish empty pools from model rejection.
- [ ] Prove exact-text forward reuse where possible; record reused versus newly scored counts. Never resume an old changed-hash job manifest.
- [ ] Check current VM state, disk/model inputs, aggregate budget and STOP limit; restart only within approved bounds.
- [ ] Run retained three-page slice, verify proposals/provenance and resource rate, then expand to 10 and 100 within the same approved limits. Report revised runtime before expanding if measurements differ materially.
- [ ] Save all candidate/stop scores and direction-specific proposals, transfer and verify results, stop the VM. On a cap, save progress and report remaining work; do not claim completion.

### 5. Compare and report — independent reviewer plus root; depends on task 4
- [ ] Report counts by direction, type and old/new cohort: source removals, type removals, unknown retained, exact changes, offered groups, selected proposals, stop decisions and no-compatible-QID cases.
- [ ] Compare common proposals, direction disagreements, multiple-QID possibilities and source-supported examples. Selection rate is not accuracy.
- [ ] Preserve current assignments and list possible previous assignments affected by the new filters; do not silently remove them.
- [ ] Review targeted diff, commit only relevant code/docs, report local backup status. No push without standing permission.

## Estimate and checkpoints

Preflight type-only score counts, before source exclusions (candidate scores plus one stop per group):

| Daniel type | Groups | Before | After |
| --- | ---: | ---: | ---: |
| LOC | 3,063 | 735,380 | 412,747 |
| PER | 1,527 | 298,180 | 57,082 |
| MISC | 2,153 | 398,975 | 398,975 |
| ORG | 2,273 | 357,852 | 140,223 |
| Total | 9,016 | 1,790,387 | 1,009,027 |

All groups retain candidates in this type-only check. There are 133,588 candidate pairs retained because type evidence is incomplete. Groups containing prior-eligible occurrences: 3,856, scoring 731,578 -> 413,688. Newly-admitted-only groups: 5,160, scoring 1,058,809 -> 595,339. These group cohorts partition 9,016; occurrence cohorts remain 5,852 and 7,277 because 386 groups contain both kinds of occurrence.

Time basis: total elapsed execution hours, including current preflight; approval_wait and environment_wait excluded. Active work is tracked separately and remains unknown unless measured.

Shared Superpowers breakdown supplied to Epoch: preflight 15 min; implementation/tests 45–80 min; scoring 30–65 min; verification/report 20–35 min. Parallel evidence and test review; integration/scoring are dependent and GPU has one owner. Proposed total range **2–4 hours**. This is model-derived, not a calibrated confidence interval. GPU estimate uses the previous measured 410 pairs/sec only as a reference; current reverse throughput is unmeasured.

Epoch invoked once for this scope: PERT optimistic 2 h, most likely 3 h, pessimistic 4 h; expected 3 h; estimate ID `3988c3d5-f114-4992-868c-ac9378db4a4f`. Its displayed calibration fields conflict with each other, so they are not used. Scope, dependencies, units and execution-time basis agree with the breakdown above; no second iteration is needed unless the completed source count changes them.

Preflight started 2026-10-30 02:56:25 Asia/Jerusalem (UTC+02); local check checkpoint 03:05. Implementation requires OWNER duration approval. After approval: first checkpoint ten minutes later; regular reports identify completed work, next step, uncertainty, resource consumption and waits. Read this state after compaction; do not repeat completed preflight.

## State

Planning/evidence only. No current-scope model inference, cloud restart, assignment changes or implementation edits have occurred. Pre-existing unrelated working-tree changes are preserved. Plan file is an uncommitted local artifact until checkpointed.
