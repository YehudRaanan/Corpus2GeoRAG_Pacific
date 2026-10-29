# Revised Daniel pipeline: 100-page comparison

Status at 30 October 2026 00:58 Asia/Jerusalem: three-page inference, local tables, Events/Relations and structural controls are complete. Ten-page inference is active. This is an interim report, not a completed 100-page matching result.

## Input and scope

- New source: `Data/external/daniel_qid_input_20261029/georag_selected_v2_qid.parquet`, pinned GitHub commit `3124f58f2a170cc66087841ed1ade18271fe1bf8`.
- Input SHA-256: `47141678ff0f67ef16c070b4beb58bb8b1273a1635d25fea875e241e48bdd006`.
- All 2,235,432 source rows have the same eight non-Source values as the earlier file. Source now holds the article QID, not an entity assignment or numeric Wikipedia page ID.
- The same 40,070 occurrences, 100 pages and 132 historical revisions are retained. Original text, names and offsets remain in raw fields. Working names and cleaned text/positions are separate.
- Run artifacts: `Data/external/revised_pipeline_20261030/`. No database was loaded; outputs are versioned local table files.

## Prepared population

| State before model use | Rows |
|---|---:|
| Strict exact accepted | 3,629 |
| Eligible, model pending | 9,610 |
| Source excluded | 14,980 |
| Source review | 7,918 |
| Deferred DATE | 3,933 |
| Total original rows | 40,070 |

There are 7,372 original DATE rows overall. DATE rows inside excluded/review source regions remain in those source states; 3,933 is the deferred-only state, not the full DATE population. Exclusions/review are not matching improvements. The eligible denominator is 13,239.

Exact preparation produced 2,310 group-QID pairs. After expansion to occurrences, the validated exact tables contain 3,629 bridges and 1,320 typed QID rows (1,312 distinct QIDs). Model work is 13,441 questions and 668,050 candidate/stop evaluations; 1,052 questions have no residual candidate. Candidate count is top 80 plus protected source-supported alternatives.

## Code and write timing

Training remains in `GG_Data/entity_resolution/decision_model/`. The pipeline uses separate files for page input, name preparation, source filtering, cleaning, strict exact matching, trigram candidate preparation, readiness-checked model decisions, table assembly, native enrichment and EDA. See the code maps in `GG_Data/entity_resolution/hundred_page_pilot/README.md` and `GG_Data/pipeline/README.md`.

Pending snapshots retain every row without provisional graph identities. Exact snapshots add only strict accepted identities. Final snapshots add model decisions and provisional identities for eligible unresolved groups only. Audit-only source and date rows remain in mentions but do not create graph identities or bridges. Final assembly binds Event enrichment to the exact core version and verifies table integrity before publication. Geography remains deferred.

## Native records and source dates

Full native coverage is 5,072/5,072 required QIDs: 807 whole cached records, 4,264 current API records and one historical record. Q133503706 now redirects; the original QID is retained through revision 2517763040 at 2026-07-15T13:03:12Z, before the merge. Raw history is preserved. Empty API map fields are converted only in the derived record, with explicit metadata.

Saved Wikipedia revisions and Wikidata lookup dates are separate provenance. This collection does not establish a single historical Wikidata snapshot or complete public Event discovery. Added Events must have a retained-content link in a used article revision. Native relations remain directed; inverse rows retain native evidence and explicit derived direction.

## Model limitation

Fixed checkpoint SHA-256: `51246b874d6346bf2769077e0067f99f20cb28f6c7a09a02ee78f1c30a2fad20`. It has encoder tuning after frozen warmup. Held-out candidate selection was 551/608 (90.63%); stop precision was 278/311 (89.39%), below the 90% target. OWNER approved experimental use for this run. These public-data measures do not establish accuracy on Daniel mentions. No retraining is included.

## Checks, timing and issues

The combined affected suite passed 552 tests. A later early-snapshot EDA regression passed in the 71-test focused suite. Ruff and diff checks passed. Independent review closed input/scope approval, same-core Event provenance, final-stage and inverse-evidence gaps.

Actual exact-stage EDA found missing early importance totals. The existing final calculation was shared with the early writer and EDA now runs before publication. Rejected `exact_3` remains recorded in `rejected_snapshots.json`; validated replacements are `exact_ready_3`, `exact_ready_10` and `exact_ready_100`.

`stage_runtime.jsonl`, `issues.json`, input validation receipts and native acquisition receipts record measured elapsed time and adjustments. Active work was not separately measured; elapsed time is not reported as active work.

## Cost and protection

No training or paid BigQuery ran. The approved existing VM has a verified 5,400-second STOP guard. Six start attempts failed because the zone had no L4 capacity. The seventh succeeded at 00:50:35 Asia/Jerusalem. The existing VM is running with a 02:20:35 STOP deadline; no temporary resource was created and that proposal is withdrawn. Three-page inference completed in 20.716 seconds for 4,336 evaluations; ten-page inference is active. Budget checks use a conservative maximum aggregate estimate of $7.28 including reserve, below the $10 limit. This is an estimate, not actual billing.

Code checkpoints: `7fff9e3` and `ee36420`. Backup status: **Local checkpoint only**. Ignored data/model artifacts are local and are not protected by these Git commits. No push was made.

## Three-page gate

The first final snapshot retains 535 mentions: 53 exact matches, 31 model matches, 67 eligible unresolved, 41 deferred DATE, 253 source exclusions and 90 source-review rows. Six local tables contain 4 page/revision rows, 98 typed entities, 535 mentions, 151 mention-entity links, 8 Events and 161 directed Relation rows. Events comprise five accepted corpus QIDs and three added Events linked in retained article content.

There are 81 native base assertions and 80 derived inverse rows. The self assertion Q928/P17/Q928 does not need an identical reverse row. Structural/source/typed-FK/inverse checks passed. Optional Event/Relation semantic completeness, model accuracy and Geography remain unevaluated; the EDA receipt states this limit.
