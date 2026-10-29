# Template and complete-name matching: 100-page implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development task-by-task. Update the checkboxes and checkpoint log below. Preserve unrelated working changes.

**Goal:** Measure how source-backed complete names and template extraction change matching across the saved 100-page pilot.

**Architecture:** Reuse the existing collection, candidate, inference and export steps. Add one clear mention-preparation step, generalize the existing template recovery step, and compare the original and corrected inputs with the same trained checkpoint. Training stays in `decision_model/`; this experiment does not retrain or silently change model formatting.

**Tech Stack:** Existing Python, PyArrow, pytest and saved LUKE checkpoint. Reuse installed/source helpers; use a standard wikitext parser if nested structures require one rather than building a general parser.

**Spec:** The user-approved source-name/template direction and the acceptance contract below. Earlier evidence: `docs/reports/2026-10-29-unresolved-page-qid-recovery.md`.

## Acceptance contract and constraints

- Read the frozen new-Daniel pilot: 40,070 original rows, 100 source pages, 132 used historical revisions. No full-corpus rerun or new page selection.
- Keep original files, assignments, checkpoint, public reference and previous outputs unchanged. Use a new output directory for each arm.
- Replace `word` only when a source-backed complete surface can be selected without ambiguity. Preserve `word_original` for every original row, plus original row ID, type, text, offsets, page and revision.
- Add separate recovered-span offsets, extraction method, source role and evidence. Original offsets still address original `Text` and `word_original`.
- Find full QID names and verified aliases in the copied text for the same revision. A recovered span may support several original mentions. Keep their IDs/types and record the links explicitly.
- A QID-guided name suggestion is candidate evidence, not its own automatic exact-match proof. Keep literal unique-name/unique-type/unique-QID exact matching separately auditable.
- Where several repairs are possible, keep the original value and alternative evidence; do not choose by iteration order.
- Record complete spans with no original overlap as recovered evidence, not fabricated Daniel records. Report this denominator separately.
- Unknown templates, ambiguous locations, incompatible years/types, redirects or missing metadata remain explicit review cases. Current template expansion must not add navigation entities or replace historical page evidence.
- Keep DATE unchanged and outside this repair/matching experiment. Preserve the 7,372 DATE rows and report them separately.
- Keep many-to-many matches and final `(QID, Daniel type)` identities. Per-page relationship counts must not increase merely because several raw spans support the same entity.
- Retain trigram top 80 plus source-supported candidates; report the union size, protected candidates and excluded alternatives. No fixed weighted graph/trigram blend.
- Keep both model arms on the same checkpoint, formatter, truncation, numeric precision and stop sentence: `None of the remaining mention groups refers to this entity.`
- Preserve the old three-page quality exception. The user's current request authorizes an exploratory 100-page experiment; record a separate hash-bound receipt, not a quality pass.
- No retraining, paid BigQuery, Geography, Event/relation/table rebuild, GitHub push or source-file replacement in this experiment.
- Public API recovery is cache-first and bounded to 200 new requests and 30 minutes. Unknowns remain unknown when limits are reached. Japanese names/sitelinks can corroborate the same source-mentioned identity; do not import a Japanese article's additional entities.
- Root exclusively owns GCP/SSH and GPU execution. Other workers own disjoint source files or read-only reviews. No overlapping cloud sessions.
- Existing US$10 ceiling remains aggregate, not a new allocation. Preserve US$2 reserve for unmeasured costs. Limit additional GPU running time to three hours and the earlier aggregate allowance to six hours; verify actual remaining limits before starting.
- GPU availability and OWNER approval waits are excluded from the execution estimate and recorded separately. Checkpoints are reporting duties, not a mechanically guaranteed timer.

## Review focus

1. Repeated copied passages: 128 passage IDs have multiple exact raw occurrences; keep all placements or an explicit ambiguity, never first-match assignment.
2. Normalized containment: 21 passage IDs need NFC/whitespace matching; use a verified position map or leave repairs unchanged with a reason.
3. Nested/multiline templates and pipes: preserve field roles, ship identifiers, display parameters and source positions; unsupported syntax remains reviewable.
4. QID-name substrings inside different names (for example, World War II Database): context must prevent self-confirming identity changes.
5. Repaired strings can merge/split groups; every original row and type must still be traceable, and evaluation must compare stable original IDs rather than new group hashes.

## Tasks, owners and dependencies

### 1. Freeze inputs, baseline and resource evidence — root

Files: this plan; existing readiness/export helpers; new run manifests under the ignored pilot data directory.

- [x] Verify worktree, Git state, free space, source counts and existing output locations.
- [x] Inspect original model checkpoint and saved quality/runtime/cost evidence in parallel with source-template inspection.
- [x] Save the current source/checkpoint/reference hashes and selected page/revision manifest before transformations.
- [ ] Verify current GCP stopped state, pinned encoder/tokenizer cache, remaining compute allowance and estimated cost before any VM start.
- [x] Record OWNER duration approval before implementation or inference.

Outcome: immutable input manifest, experimental scope receipt, exact resource limits or a named blocker.

### 2. Generalize source/template recovery and prepare mentions — source worker

Depends on task 1 approval. Exclusive files: `hundred_page_pilot/recover_page_qids.py`, new `hundred_page_pilot/prepare_mentions.py`, focused tests.

- [ ] Add focused tests for ordinary links, USS/Ship/Jsub/Sclass targets, nihongo names, split citation authors, nested infobox fields, ambiguous/repeated placements and normalized offsets.
- [ ] Reuse `validate_revision`, `raw_links`, cache/title resolution and metadata conversion. Replace the hard-coded three-page guard with explicit manifest-bound scope; preserve the three-page replay path.
- [ ] Inventory actual template families on all used revisions; implement source-supported rules in priority order, and report unsupported families rather than guessing them.
- [ ] Write `prepare_mentions.py` as one readable stage: raw rows and source evidence in; corrected Parquet, recovered spans, original-mention bridge and correction summary out.
- [ ] Keep non-name template parameters distinct. Citation author reconstruction does not itself create an absent QID.
- [ ] Merge newly verified page QIDs with the existing inventory in a new version. Preserve native metadata, current lookup times and historical source evidence separately.
- [ ] Run focused tests and verify all original IDs/columns, including DATE, survive unchanged except explicitly corrected `word` and added provenance.

Outcome: row-preserving corrected data, expanded verified inventory and an exact workload-ready evidence set.

### 3. Prepare candidate/reference/readiness support — model worker

Runs in parallel with task 2 after task 1 approval. Exclusive files: `prepare_candidates.py`, `readiness.py`, `report.py` and their focused tests. Coordinate the corrected-row/evidence interface before edits.

- [ ] Extend preparation to retain source-supported candidates in addition to top-80 trigram options. Keep strict original exact matches separate from QID-guided repairs.
- [ ] Produce original baseline jobs from saved data; preserve or safely reuse previous scores only when query/option bytes, checkpoint and scoring settings are identical.
- [ ] Extend the experimental approval gate to exact manifest-bound 3/10/100 subsets without weakening technical checks or rewriting the old exception.
- [ ] Rebind current loader/source evidence explicitly; perform an actual restore smoke test before recording a new restore receipt.
- [ ] Keep existing input formatting identical on both arms. Record the earlier training/inference preprocessing gap as deferred to a matched training version; do not present this experiment as fixing that model gap.
- [ ] Adapt exports/comparison to stable original row IDs and original reference evidence. Repaired labels or new group IDs cannot redefine the gold positives.
- [ ] Test many-to-many joins, incomplete/partial inference refusal, scope/hash mismatches and unchanged original-row export.

Outcome: two comparable job sets, valid technical receipts and an audit-safe comparison path.

### 4. Deliver three, then ten pages — root integrator/GPU owner

Depends on tasks 2 and 3.

- [ ] Complete CPU candidate preparation for all 100 before GPU startup to avoid paid idle preparation.
- [ ] Calculate exact pair counts and forecast both arms with the saved 279.43 pairs/second observation, plus setup and reserve. If the bound exceeds money/time limits, report before changing scope or candidate limits.
- [ ] Freeze a prediction-independent review sample of corrected/ambiguous cases. Treat source-positive reference coverage separately from verified accuracy.
- [ ] Run the original three pages end to end on both arms. Check original-row preservation, unchanged DATE, repairs and matching changes.
- [ ] Report completed work, before/after counts, examples, remaining questions, elapsed/runtime/cost evidence and the next step.
- [ ] Expand to ten saved pages and repeat the same checks. Do not silently adjust thresholds, model or candidate limit.

Outcome: two small complete deliveries with safe restartable outputs.

### 5. Complete the 100-page comparison — root GPU owner

Depends on task 4. CPU analysis can run in parallel under a separate owner; GCP remains root-owned.

- [ ] Finish original and corrected inference across all 100 pages, preserving completed scores and per-state traces. Use one GPU with bounded runtime and verified automatic shutdown.
- [ ] Export every original row with corrected/original names, all QID matches, source evidence and unresolved reasons.
- [ ] Verify output completeness before declaring a run complete. Preserve partial results if a limit is reached.
- [ ] Verify VM stopped and record measured running time; distinguish estimated costs from billing actuals.

Outcome: complete matched/unresolved exports for both arms, or an exact bounded-run blocker with partial results clearly identified.

### 6. Explain results and checkpoint — report worker, root review

Depends on task 5 for final statistics; prepare reporting code/document structure earlier without predictions.

- [ ] Report original rows, repaired rows, corrected groups, recovered-only spans, added QIDs, candidate coverage, exact/model matches, unresolved rows and ambiguity by page/type/method.
- [ ] Compare stable original row-to-QID pairs: newly matched, lost, changed and multiple matches. Show DATE separately and label unverified outcomes.
- [ ] Evaluate the frozen source-positive reference without calling it overall precision. Show reviewed examples and all evidence limits.
- [ ] Record automated runtimes, observed elapsed time, known waits, unknown active-work time, issues and adaptations. Never invent an actual for Epoch's wait-excluded basis.
- [ ] Run focused pytest, existing formatting/lint tools and input/output invariant checks. Review only task-owned diffs; keep unrelated `luke_pilot/evaluate.py` changes.
- [ ] Commit task-owned code/docs locally. Report `Local checkpoint only`; ignored data/weights remain local and no push is authorized.

Outcome: short plain-English report, detailed case files, reproduction commands and explicit backup status.

## Estimates and checkpoints

- Version 2 estimate: 2–6 hours elapsed execution including preflight; excludes approval and unavailable-GPU waits. Model-derived, not a calibrated coverage guarantee.
- Nominal dependency path: preflight 10 minutes; source repair 50 minutes parallel with readiness 35; three/ten checks 25; two-arm inference 105; final report 30 = 220 minutes.
- Epoch PERT v2: O=2, M=3.67, P=6 hours; expected 3.78 hours; feedback `4bed6361-74ed-40a9-b4c4-7b298693cfa2`.
- Epoch's separate critical-path response mixes a 24-hour-day total with an eight-hour-day `estimatedHours` field. Its converted hour field is not used. The dependency path and PERT inputs above use elapsed hours consistently; this tool conversion limitation remains explicit.
- Saved measured inference: 8,886 pairs / 31.8008 seconds. Baseline 778,389 pairs implies about 46 minutes, before overhead. Corrected workload remains unknown until prepared.
- Prior saved VM allowance remaining: 14,112.916 seconds. Prior estimated compute/query subtotal US$1.548042; storage/transfer/billing actuals unknown. This is not a live billing check.
- Initial planning checkpoint: 13:37 on 29 October 2026, Asia/Jerusalem (UTC+02). Execution checkpoint: ten minutes after duration approval, then every 5–10 minutes and after each 3/10/100 delivery.

## Checkpoint log

| Time, Asia/Jerusalem | State | Next / blocker |
|---|---|---|
| 2026-10-29 13:27 | Planning/preflight started; no new cloud activity | Inspect saved source/model/resource evidence |
| 2026-10-29 13:31 | Saved counts, model and costs checked; two read-only reviews complete or finishing | Save plan; request mandatory duration approval before implementation |

**Current status:** EXECUTING. OWNER approved the saved plan; three implementation workers active. Input hashes frozen. Live VM verified TERMINATED. No new paid run started.

| 2026-10-29 13:34 | OWNER approved execution; 2–6h estimate, existing US$10 total, 3 additional GPU hours | First checkpoint13:44; prepare all CPU inputs before GPU start |
