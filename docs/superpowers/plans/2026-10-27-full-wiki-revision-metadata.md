# Full Wikipedia revision metadata — execution plan

Status: superseded in part by OWNER's staged-output instruction. The broad historical search below remains pending approval; first create immutable V1 using already verified pilot recovery, then V2 by copying saved baseline revision evidence. Do not rematch the resolved 301,235 rows.

## Staged execution amendment — 27/10/2026 22:18:52 Asia/Jerusalem UTC+02

Owner root; exclusive worktree/API/output ownership. New first-step estimate v1: 8–18 elapsed minutes, model-derived, point about 12; Epoch `230f2504-c512-4470-8f26-38175f9a47b4`. Superpowers breakdown A (V1) -> B (V2) -> C (audit/report) and Epoch use the same scope, dependencies, elapsed-hour units and time basis; agreement after one iteration. Approval wait zero for authorized short staged export; active_work/environment_wait separately unknown; measure elapsed and request time.

Ruling: apply the 2,707 already verified historical rows immediately, with no new history search, to provide the requested starting file. Backfill prior resolved revision metadata by 34,254 saved passage decisions / 425 unique revision IDs, not entity extraction or full-passage rematching. Reading/copying rows for export and integrity checks is required and is not a matching rerun. The 5,922 other unresolved rows remain pending historical search under the earlier long-run approval gate; this amendment does not cancel that objective or claim it complete.

- [x] A: small tested staged exporter; V1 has only newly recovered IDs and their complete revision metadata. Preserve existing IDs; metadata on earlier accepted rows remains pending.
- [x] B: query timestamps for the 425 saved revision IDs in batches, validate page/revision identity, backfill V2 metadata for the 301,235 earlier accepted rows. No matching calls.
- [x] C: verify original values/order, immutable baseline IDs, V1->V2 IDs and recovered metadata, full counts and input/evidence hashes; independent review; local checkpoint/report.

Completed outputs: V1 page-ID303942/revision2707; V2 page-ID303942/revision303942;5922nullrows,414unresolvedpairs. Nine metadata calls,3.969 summed seconds. No original raw Parquet read or text matching. Baseline2138andpilot38manifestfiles checked;12focused/regressionchecks, Ruff/Black/isort pass. Reviewer found missing baseline manifest guard; failing test -> guard -> passing test; review confirmed fix. Current output provenance independently reconciled without overwriting either file.

Completion clock22:26:43: verified elapsed471seconds (7m51), not active work. Epoch accepted an approximate0.128h actual before this final clock (7m40.8); exact correction0.130833h was rejected because only one actual per estimate is allowed. Retain the verified clock-derived duration here; do not treat the approximate stored value as exact. Code/docs checkpoint7095ff7; ignored data unprotected.

Checkpoint 22:28, upper estimate 22:36:52. Outputs `Data/external/source_page_versions_staged_20261027/`, distinct `_v1_historical_recovery.parquet` and `_v2_revision_metadata.parquet` filenames. Original inputs and V1 remain unchanged. No original-file processing, new history sampling, remote writes, installation, graph changes or cleanup.

### Pending continuation — history only, not started

Process only the 414 remaining unresolved Source/Text pairs (5,922 rows); preserve all 303,942 accepted page/revision assignments and append results into another new Parquet. A cache/context/progress preparation (15–20min) -> B bounded historical matching only on unresolved (35–110min) -> C incremental export/audit (10–20min), root exclusive owner. Model-derived estimate60–150elapsedminutes,mostlikely90,PERTpoint95; Epoch `a5dc98a4-0388-4d62-927e-fe524192d542`. Superpowers decomposition and Epoch share identical scope, dependency order, elapsed-hour basis and limits, one exchange. Generic0.5hreference-class suggestion excludes measured historical parsing/network work and is not used. Do not infer empirical P80 calibration.

Approval wait begins only when the explicit OWNER question is sent; active_work and environment_wait currently zero for this unstarted phase. Same collection ceilings:2200newAPIcalls/120minretrieval/3GiB, no failed-call retries. Initial coverage of all remaining contexts precedes deeper sampling; nulls/statuses are valid outputs and historical absence cannot be proved by a bounded sweep. With approval/start at27/10/2026 22:30 Asia/Jerusalem UTC+02, expected completion27/10 23:30–28/10 01:00; firstcheckpoint27/10 22:40, adjusted to actual approval time. Explicit OWNER approval is required under supplied AGENTS.md for this >20min phase. No extraction or rematching of previously accepted rows.

## Scope and acceptance

Process all 309,864 original rows. Create a separate enriched Parquet with source article and matching-revision metadata; search historical article versions for all 8,629 baseline unresolved rows (521 Source/Text pairs). Complete and verify revision metadata for the 301,235 already assigned rows as well. Preserve the original nine columns, every duplicate, row order, and original metadata. Keep both previous Parquets unchanged. Preserve existing non-null article IDs; only add previously null article IDs on verified evidence. Any verified page/revision conflict is a reported exception, not an automatic replacement.

The revision is a version whose complete rendered passage matches the copied text, not a claim about the extraction revision. Different passages on the same article may use different matching revisions. A common article-wide revision is not imposed. Whole raw text or NFC/whitespace-normalized whole text is required; no fuzzy or punctuation-stripped acceptance. Candidate discovery is not acceptance evidence.

Deliver a complete row-level audit and metadata schema for every input row. Unverified values remain null with an explicit status. Zero unresolved rows cannot be guaranteed; sampling limits and inaccessible revisions must remain visible.

## Output contract

New output directory: `Data/external/source_page_versions_20261027/`.
Parquet: `georag_selected_v2_full_n36335_r345732948_20261024_with_wiki_page_version.parquet`.
Original fields remain byte/value-equivalent through Arrow projection, including original schema metadata. Preserve `wiki_page_id` from the baseline where non-null.

Added fields:

| Field | Type | Meaning |
|---|---|---|
| wiki_page_title | string, nullable | Canonical title tied to accepted page evidence |
| wiki_revision_id | int64, nullable | Verified matching revision ID |
| wiki_revision_timestamp | timestamp[us, UTC], nullable | Revision timestamp returned by MediaWiki |
| wiki_revision_url | string, nullable | Permanent oldid URL |
| wiki_match_method | string, nullable | Exact or full NFC/whitespace-normalized rendered match; current snapshot or historical |
| wiki_match_status | string, required | Verified, unresolved, ambiguous, unavailable, request failure, or search limit |
| wiki_revision_evidence | string, nullable | Relative saved evidence reference |
| wiki_text_sha256 | string, required | SHA-256 of original copied Text |
| wiki_baseline_status | string, required | Original attribution decision for audit |

If an existing article assignment lacks a verified revision after rendering, retain the article ID and mark revision metadata unverified. Do not describe page assignment alone as full revision verification. Include decision JSONL, unresolved CSV, summary counts, API cache, manifest hashes, reproducible script/tests, and report.

## Owner, dependencies and limits

Root owns the isolated worktree, API session, terminal and output files. Existing completed pilot and baseline are read-only inputs. Each task depends on the prior task; no parallel writers. A final read-only independent review is permitted by the execution skill. No remote push, cloud run, paid model call, installation, graph rebuild, identity remapping or cleanup.

Preflight confirmed clean task branch `data/source-page-ids-20261026` at `f11c654`, local D: workspace, about 114.74 GiB free, ignored data outputs, no configured branch upstream. Code/docs local checkpoints only; ignored data unprotected. Original main workspace remains untouched.

Evidence: 34,254 verified baseline pairs have 425 distinct revision IDs and 436 page evidence records; 138 of those records already contain rendered text. There are 131 best-context article IDs among unresolved diagnostics, with 137 Source labels total. The pilot verified 2,707 unresolved raw rows across 16 revisions, using 32 successful calls and 108.595 summed request seconds. Cache reuse is required, with page/revision identity validation.

Collection ceiling: 2,200 new API calls, 120 elapsed minutes of retrieval, and 3 GiB of new saved evidence. Save progress after each article/revision. Do not retry failed calls automatically. Process every unresolved pair in the initial pass before allocating remaining budget to deeper refinement. Stop collection at the first ceiling and export verified results plus explicit limit statuses; a ceiling is not proof of historical absence. Do not start a deeper run without a revised report and required approval.

## Independently testable tasks

### A — Revision evidence and schema (20–35 elapsed minutes)

- [ ] Reuse `attach_source_page_ids.py` client, normalization, rendering, serialization and integrity patterns; reuse pilot cache without modifying it.
- [ ] Add the smallest revision-provenance module and focused tests for complete matching, wrong revision/page identity, ambiguous candidate pages, duplicate row propagation, null metadata, and immutable original projection.
- [ ] Read all 34,775 baseline decisions; batch revision ID/timestamp queries; bind saved parse evidence to exact oldid, and render missing baseline revisions. API evidence must establish actual revision ID, page ID and timestamp.
- [ ] Pass focused tests, formatting/lint checks, and a local export fixture before collection.

### B — Full unresolved recovery (55–115 elapsed minutes)

- [ ] Apply already verified pilot matches and try relevant cached revision renderings first, preserving all source labels and rows.
- [ ] On unresolved article contexts, use the pilot's eight target dates (24/10/2026, 01/07/2026, 01/01/2026, 01/07/2025, 01/01/2025, 01/07/2024, 01/01/2024, 01/01/2023), querying the last revision at or before each date and parsing distinct revisions. Stop searching an article when all its eligible unresolved passages have full matches.
- [ ] Reuse saved candidate discovery for incorrect/missing Source labels; use bounded new text discovery only where no relevant candidate exists. Keep current global-search minimum 50 normalized characters/eight words. Short passages require verified direct source context; do not bypass ambiguous global matches.
- [ ] Use remaining budget for targeted intermediate revisions around promising sampled matches or known wording changes, then older dates for remaining cases. Search is explicitly bounded, not exhaustive article history.
- [ ] Select the newest verified matching revision among the versions actually checked for that passage. Keep complete evidence for each acceptance and explicit reasons for every unverified pair.

### C — Export and audit (15–30 elapsed minutes)

- [ ] Atomically export the new full-row Parquet; reread and compare all original fields/order/schema metadata, baseline non-null IDs, metadata types and null/status rules.
- [ ] Reconcile every accepted revision to saved metadata/rendered full-text evidence and every original row. Reconcile all status/type/source denominators and unique entity pair count (74,339).
- [ ] Verify original and baseline hashes, generate all-file manifest, run independent review, write report, and make local code/docs checkpoint. No push.

## Estimate and agreement record

Estimate v1: **90–180 elapsed minutes**, point **135 minutes**, excluding OWNER approval wait. Preparation began 27/10/2026 09:37:49 Asia/Jerusalem UTC+02. If authorized at about 09:43, expected completion 11:13–12:43; move the completion window by actual approval delay. First execution checkpoint is ten minutes after approval, followed by checkpoints every 5–10 minutes; normal progress updates can be earlier. This is a behavioral schedule, not an enforced timer.

Ponytail full: reuse the established client/cache/rendering and append-only export pattern; no new dependencies or generalized resolver framework. Superpowers decomposition: sequential A->B->C above, one owner, separate measurable gates. Epoch exchange iteration1 supplied that breakdown and API evidence (reference `3f9a13a9-c888-4edc-808b-cc183c4ed3d5`); iteration2 supplied measured cache coverage and rejected the generic 30-minute reference-class suggestion because it omits hundreds/thousands of HTTP calls (reference `87dae209-9a1c-4383-9ed0-e490660e768c`). Both PERT outputs retain the same 1.5/2.25/3.0 elapsed-hour inputs and 2.25-hour point. Scope, dependencies, units and time basis agree; the generic reference-class suggestion is not evidence for this network task. No further estimation loop is authorized by this plan.

The range is model-derived, not empirically calibrated P80. Track active_work, approval_wait and environment_wait separately where measured; otherwise mark unknown. Pilot HTTP durations are evidence for network cost, not total focused effort. At each checkpoint record stage, exact verified counts, pending calls, limits and next checkpoint. If total estimate exceeds approved limits, reach a safe pause and seek OWNER approval under the supplied AGENTS.md instructions.

## Review focus

Wrong page/revision binding; extract/render disagreement; source aliases and duplicate-row counts; short or repeated citation ambiguity; failed/hidden revisions; exhausted search budget; UTC revision dates versus Israel-local checkpoints; output overwrite; prior accepted IDs replaced without proof. A matching historical revision does not establish when data was extracted or that rendered template state is historically frozen.
