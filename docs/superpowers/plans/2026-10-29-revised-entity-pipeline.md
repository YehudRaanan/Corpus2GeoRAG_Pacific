# Revised Entity Pipeline and Table Write Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement approved tasks. This is a proposed design, not permission to run inference, collect data, spend or publish tables.

**Goal:** Process Daniel's input through source verification, cleaning, exact matching, decision-model matching and QID enrichment, with explicit table write points.

**Architecture:** Keep immutable input and stage outputs under one run ID. Write checked batches to a new run version; make a complete version available only after integrity checks. Reuse existing Python steps; keep model training separate.

**Tech Stack:** Existing Python, PyArrow/Parquet, local JSON exports, pytest and LUKE scorer. No new database or framework is proposed.

**Spec:** OWNER's six-stage pipeline request and subsequent request to decide when data-model tables are populated, 29 October 2026. Decisions below are recommendations pending discussion.

## Global constraints

- Preserve all original rows, text, types and offsets. Store working cleaned values separately.
- Match only within the verified Wikipedia page/revision. A supplied page ID does not prove the revision.
- Exact means identical official label, one Daniel type for that name and one QID for that label on that page/revision. No new type mapping or alias-only exact rule.
- Allow many-to-many identity links. Resolved entity identity is QID plus Daniel type.
- Keep page/revision failure, excluded content, source review, deferred DATE and entity unresolved as separate statuses.
- Linked entities and the page's own QID remain the pilot inventory. Cache first. No paid BigQuery or additional extraction is implied.
- Events must be present as linked QIDs in saved article evidence. Keep native directed relations separate from co-occurrence weights and derived inverse rows.
- Training remains in `GG_Data/entity_resolution/decision_model/`; reuse the trained checkpoint subject to readiness and quality disposition. No retraining is in this plan.
- Excluded source rows remain auditable but do not become graph nodes solely because Daniel extracted them.

## Current verified state

- Active worktree: `D:/Projects/GeoAI-luke-pilot-20261028`.
- `post_qid_run.build_core` currently builds page, entity, mention and bridge exports after saved matching decisions are available. Outputs are local files; this does not prove a database load.
- `post_qid_mentions.populate` currently requires valid page/revision IDs and a saved group for every row. It must be adapted before it can represent early pending, excluded or page-unresolved rows.
- `prepare_candidates.group_mentions` still reads `Text`, `start`, `end` and existing source context. The cleaner outputs are not yet connected end to end to matching.
- Cleaner `source-text-v3` was checked on the saved 100-page sample: 40,070 rows retained; 23,239 mapped, 14,884 excluded and 1,947 uncertain. Mapped means a surviving text span, not a QID match.
- Saved model test: 551/608 correct state choices (90.625%); 278/311 stop precision (89.389%); 245/296 complete labelled sets (82.770%). Source: `train_20261029/final_public_test_metrics.json` and the matching-label audit.
- These are public-label diagnostics, not measured accuracy on Daniel's 100 pages. Stop precision missed the agreed 90% gate; model results remain experimental.

## Proposed write points

Logical table labels below describe responsibilities, not a migration already applied.

| Stage | Processing | Write point and data |
|---|---|---|
| 1a | Load and validate Daniel's input | Save immutable input, checksum and stable mention IDs immediately. No QID entity assignments yet. |
| 1b | Verify supplied page IDs; recover missing pages/revisions iteratively | Write verified page/revision records, evidence hashes, timestamps and lookup method after each checked batch. Keep unresolved rows with a reason and no invented revision. |
| 2 | Clean the source and project mention spans | Write/update the run's Mentions with original and clean values, span mapping, policy version and source status. Mark eligible rows pending matching; preserve excluded/review rows. |
| 3 | Strict exact matching | Write accepted resolved Entities and Mention-Entity links together after batch validation. Save method `exact` and uniqueness evidence. Other eligible rows stay pending, not finally unresolved. |
| 4 | Same-page trigram, then iterative decision model | Write accepted Entities and links together per completed page/revision, with candidate and model evidence. Preserve stage 3 links. Do not write candidates or rejected options as accepted links. |
| 5 | Close the matching pass and classify remaining rows | Create provisional Entities and unresolved bridges only for eligible unmatched groups. Record reason and evidence availability; DATE remains deferred. Keep excluded/review/page failures distinct. Later repairs produce a new run version. |
| 6 | QID-based Events and Relations | Write eligible Events after referenced Entities exist; write Relations after both required endpoints exist. Preserve source assertions, direction and any separately derived inverse rule. Then validate the run snapshot. |

Do not wait for stage 5 to be fully solved before producing a usable experimental delivery. An explicit unresolved state is a valid stage result. It is not a false QID assignment.

### Consistency and resume rules

- Use a run ID, input checksum, code/policy versions and stage status in the existing manifest/receipts. No new tracking platform.
- Early writes belong to the new run version. They must not overwrite the currently accepted version.
- For file outputs, write a fresh stage directory, verify its files and references, then mark that stage complete in its manifest. Do not claim a database transaction exists.
- Publish Entities and their links as one consistent batch snapshot. Never expose a link without its referenced typed entity.
- Keep original mention identity stable across stages; do not use cleaned offsets with original text, or change original IDs when names are repaired.
- Preserve many-to-many bridges. A selected Daniel group is removed only from that QID's remaining alternatives, not from other QIDs' lists.
- Distinguish pending, accepted exact, accepted model and unresolved. Store experimental quality separately from processing completion.
- Build the final snapshot from run-scoped outputs, check all row counts and references, then mark it ready. Readiness does not turn experimental matches into verified identity truth.

## Implementation tasks after design approval

All tasks have one write owner. Independent checks may run in parallel; no two writers share an output directory.

1. **Input and page contract.** Owner: pipeline implementer. Reuse `hundred_page_pilot/prepare_pages.py` and `pipeline/post_qid_pages.py`. Dependence: input schema/manifest. Check that supplied IDs are verified, failed lookups remain represented and every verified revision has source evidence. Outcome: immutable input and a checked page/revision catalog.
2. **Clean mention contract.** Owner: pipeline implementer. Reuse `clean_source_text.py` and adapt `post_qid_mentions.py`. Dependence: task 1 revision evidence. Check original-row preservation, mapped slices, null unresolved IDs and distinct exclusion/review flags. Outcome: all source rows can be represented before matching.
3. **Exact and candidate contract.** Owner: pipeline implementer. Adapt `prepare_candidates.py` to consume the cleaned text/positions and preserve original group lineage. Dependence: task 2 plus verified linked-QID inventory from `collect_entities.py`. Check bilateral uniqueness, same-revision scope, repaired-name restrictions and excluded/review blocking. Outcome: exact accepted pairs plus auditable trigram jobs.
4. **Decision pass.** Owner: inference implementer. Reuse `readiness.py`, `resolve_entities.py` and the separate trained scorer. Dependence: task 3, a current restore/input-format check and explicit model-quality disposition. Check the repeated choose/remove/stop loop and many-to-many preservation. Outcome: hash-bound model decisions, not a new training run.
5. **Table batch assembly.** Owner: pipeline implementer. Reuse `post_qid_entities.py`, `post_qid_mentions.py`, `report.py` and `post_qid_run.py`. Dependence: tasks 3/4. Check entity-before-link integrity, repeat-run duplicate protection and all original-row denominators. Outcome: consistent exact/model/provisional exports with separate source statuses.
6. **QID enrichment and acceptance.** Owner: enrichment implementer. Reuse `post_qid_native.py`, `post_qid_events.py`, `post_qid_relations.py` and `post_qid_eda.py`. Dependence: task 5 accepted identities; acquisition can prepare cached records earlier. Check article-bound Event evidence, closed endpoints, original QIDs/revisions and relation direction. Outcome: an internally consistent experimental snapshot with an EDA report.

Small delivery order remains 3 pages end to end, then 10, then 100. Do not rerun the full corpus. QID inventory collection and cleaning can overlap after a revision is verified. Cache consolidation and independent schema tests can overlap matching preparation. GPU inference has one resource owner. Table batch publication follows matching dependencies.

## Decisions before implementation

1. Confirm staged run writes and final snapshot publication as described above.
2. Keep the existing restriction against promoting repaired names to strict exact matches, unless the OWNER explicitly changes that policy. Cleaning alone must not manufacture an exact identity.
3. Resolve the model quality gate before any new model execution; the stop-precision target has not been met. Check preprocessing compatibility without silently retraining or altering thresholds.
4. Define future recovery rules for eligible entity-unresolved groups separately. DATE semantics and Geography remain outside this change.
5. If a real database load is required, identify its existing backend and transaction mechanism before designing the loader. Current inspected outputs are local table files.

## Planning estimate and evidence

Scope: inspect existing writers and saved model metrics, then specify six stages and their write points. No implementation, data load, inference, training, collection or cloud spend.

Superpowers breakdown: inspect contracts/metrics, define write dependencies/statuses, review and save this proposal. Epoch used the same whole planning scope and elapsed-hour basis: O/M/P = 5/7/10 minutes; raw expected 7.2 minutes; feedback reference `01896bc3-fcef-4f68-915a-6728f9014129`. This is a model-derived range, not an empirically calibrated confidence claim. No scope/basis conflict remained after review; no second iteration was needed.

Verified clock at estimate: 29 October 2026 23:47:33 Asia/Jerusalem (UTC+02). Status checkpoint: 23:57. Active work and wait decomposition are unmeasured; elapsed time must not be recorded as active work. No implementation-duration estimate is asserted by this planning estimate.

## Review focus

- Page-unresolved rows must not disappear because downstream writers currently require IDs.
- Cleaned spans must use cleaned text; excluded/review rows must not enter inference by accident.
- Group-level matching does not independently prove every occurrence's identity; retain all occurrence evidence and uncertainty.
- Entity, bridge and Event/Relation outputs must refer to the same completed run version.
- Model test diagnostics and source-link support must not be presented as complete native-corpus accuracy.
