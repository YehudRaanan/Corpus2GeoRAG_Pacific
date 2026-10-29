# Revised Daniel pipeline: 100-page comparison

Completed at 30 October 2026 01:40 Asia/Jerusalem: the revised pipeline ran on the new Daniel file for the same 3, 10 and 100 pages. Final local tables, article-bound enrichment, both prior-run comparisons and independent accounting are complete. All original rows are retained. The existing VM is stopped; no temporary VM or image was created. Structural checks passed; scientific accuracy remains unverified.

The main result is 7,387 matched mentions out of 13,239 eligible mentions (55.80%), with 5,852 eligible unresolved. On the same eligible rows, the previous corrected run matched 7,088: the new workflow adds 421 newly matched rows and loses all matches on 122 rows, a net increase of 299. These are processing outcomes, not verified accuracy gains. Another 7,918 rows need source review; this remains a substantial coverage limit.

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

The current checkpoint restore and scorer compatibility check passed on CUDA. Original training-time code immutability is not proven: the saved checkpoint and metrics did not embed training-time code hashes. Current source bytes and checkpoint hashes are recorded separately. Stop remains `None of the remaining mention groups refers to this entity.` A tie selects stop. The loop can accept several Daniel groups for a QID, and the same group can be accepted for several QIDs.

## Hundred-page matching comparison

| Final mention state | Rows |
|---|---:|
| Accepted exact status | 3,432 |
| Accepted model status, including exact/model overlap | 3,955 |
| Eligible unresolved | 5,852 |
| Source excluded | 14,980 |
| Source review | 7,918 |
| Deferred DATE | 3,933 |
| All original rows | 40,070 |

No page/revision failure or pending model row remains. The earlier exact stage linked 3,629 mentions. In the final writer, a mention with any additional model match has model status; this is why final exact-only status is 3,432.

Matched mentions comprise 3,432 exact-only, 3,758 model-only and 197 with both methods. The 9,418 resolved occurrence–QID links comprise 3,629 exact and 5,789 model links. The remaining 5,852 bridges point to provisional identities for eligible unresolved mentions.

**A material model concern:** 1,338 mentions have several QIDs. Three occurrences of `Japanese` (MISC) in `Japanese war crimes`, page 1120226, revision 1380836643, each received 27 model QIDs. Targets include Japanese war crimes, yen, Japanese cruiser Tone and the Japanese Communist Party. The contexts refer to Japanese people/soldiers. This is a strong reason to review decision specificity before accepting model identities. It is not an adjudicated error count. The unrestricted many-to-many policy was preserved; no result was silently removed. Evidence: `accounting_100.json` and `high_qid_review_examples_100.json`.

| Same currently eligible 13,239 rows | Original baseline | Previous corrected run | New workflow |
|---|---:|---:|---:|
| Matched mentions | 6,879 | 7,088 | 7,387 |
| Unresolved mentions | 6,360 | 6,151 | 5,852 |
| Mention–QID pairs | 8,198 | 8,666 | 9,418 |

Against the original baseline: 627 newly matched rows, 119 rows losing all matches, net +508 matched rows. Against the corrected run: 421 newly matched rows, 122 losing all matches, net +299. QID sets also changed on 856 and 716 already-matched rows respectively. These cases need identity review before a quality claim.

Whole-file matched totals fell from 13,627/14,588 to 7,387 because 6,748/7,500 previously matched rows are now outside matching eligibility. Excluded material and held source-review rows must not be called model errors or matching improvements. Source-review rows can include useful article content with uncertain placement; they are preserved, not discarded.

Both workflow comparisons verify all 40,070 original-row identities and eight unchanged non-Source values. The declared Source change is article title to article QID. Case-level outputs are in `comparison_final_baseline_100/` and `comparison_final_corrected_100/`, each with `workflow_comparison.json`, CSV and JSONL rows. Precision, accuracy and candidate truth remain unknown.

## Checks, timing and issues

The combined affected suite passed 552 tests. A later early-snapshot EDA regression passed in the 71-test focused suite. Ruff and diff checks passed. Independent review closed input/scope approval, same-core Event provenance, final-stage and inverse-evidence gaps.

Actual exact-stage EDA found missing early importance totals. The existing final calculation was shared with the early writer and EDA now runs before publication. Rejected `exact_3` remains recorded in `rejected_snapshots.json`; validated replacements are `exact_ready_3`, `exact_ready_10` and `exact_ready_100`.

Native acquisition handled 15 HTTP 429 responses with bounded retries. The cache has no missing required records. A redirected QID needed the approved historical record; API empty-map serialization needed a derived-format correction while retaining original response bytes. GPU capacity required seven start attempts. These adjustments did not change matching thresholds, model weights or source assignments.

A final focused check of revised orchestration, table/EDA controls and workflow comparison passed **63 tests in 10.92 seconds**. These overlap earlier suites and must not be added to 552 as unique coverage.

`stage_runtime.jsonl`, `issues.json`, input validation receipts and native acquisition receipts record measured elapsed time and adjustments. Active work was not separately measured; elapsed time is not reported as active work.

## Cost and protection

No training or paid BigQuery ran. Six start attempts failed because the zone had no L4 capacity. The seventh succeeded at 00:50:35.329 Asia/Jerusalem. The existing VM stopped at 01:33:49.696, verified `TERMINATED`. New runtime was 2,594.367 seconds (43 minutes 14 seconds), below 90 minutes. Aggregate saved runtime is 15,828.011 seconds (4.397 hours), below six hours. The 5,400-second STOP guard remained configured. Temporary-resource approval was received but unused; no temporary VM, disk or image was created.

New compute estimate: **$0.51**. Aggregate compute/query estimate: **$3.19**. A conservative aggregate estimate using $1/hour and a $2 unmeasured storage/transfer reserve is **$6.50**, below the $10 budget. These are estimates, not billing actuals. The existing persistent disk is retained and can still incur storage charges. Evidence: `vm_stopped_verified.json`, `budget_preflight.json`, `budget_final.json`.

| Measured stage | Elapsed seconds |
|---|---:|
| Input adapter | 2.656 |
| Name/template preparation | 233.922 |
| Source filter | 37.156 |
| Source cleaner | 24.282 |
| Strict exact matching | 3.343 |
| Trigram candidate preparation | 25.953 |
| Three-page inference, 4,336 evaluations | 20.716 |
| Ten-page inference, 59,949 evaluations | 165.575 |
| Hundred-page inference, 668,050 evaluations | 1,630.552 |
| Hundred-page final core validation | 79.281 |

The hundred-page model answered 13,441 questions and selected 1,956 group–QID pairs before occurrence expansion. Measured callable and VM elapsed times are separate from active work. Preflight start, approval wait and overlapped capacity wait were not measured on a complete common basis; no full-task active-work or calibrated Epoch actual is claimed.

Code checkpoints: `7fff9e3` and `ee36420`; interim documentation checkpoint `ac0ac0d`. Backup status: **Local checkpoint only**. Ignored data/model artifacts are local and are not protected by these Git commits. No push was made.

## Three-page gate

The first final snapshot retains 535 mentions: 53 exact matches, 31 model matches, 67 eligible unresolved, 41 deferred DATE, 253 source exclusions and 90 source-review rows. Six local tables contain 4 page/revision rows, 98 typed entities, 535 mentions, 151 mention-entity links, 8 Events and 161 directed Relation rows. Events comprise five accepted corpus QIDs and three added Events linked in retained article content.

There are 81 native base assertions and 80 derived inverse rows. The self assertion Q928/P17/Q928 does not need an identical reverse row. Structural/source/typed-FK/inverse checks passed. Optional Event/Relation semantic completeness, model accuracy and Geography remain unevaluated; the EDA receipt states this limit.

## Ten-page gate and independent accounting

The ten-page final snapshot has 3,785 mentions, 1,342 mention-entity links, 646 typed entities, 13 page/revision rows, 43 Events and 2,393 directed Relation rows. Eligible mentions total 1,248: 781 matched and 467 unresolved. Matched mentions comprise 330 exact-only, 435 model-only and 16 with both methods. The earlier exact stage linked 346 mentions; the final exact-only status excludes the 16 that also acquired a model match. There are 94 mentions with two QIDs. These are allowed many-to-many processing outcomes, not proof of correct identities.

An independent local audit verified all 535 shared mention rows and 151 typed bridges across three and ten pages. Evidence: `accounting_3_10.json`. Six source-preserving examples are in `report_examples_10.json`: exact, model, unresolved, exclusion, review and multiple QIDs. Miami has city and airport outputs and is explicitly ambiguous. No independent gold accuracy was measured.

## Final local tables and controls

| Table | Three-page scope | Ten-page scope | Hundred-page scope |
|---|---:|---:|---:|
| wiki_pages: page/revision rows | 4 | 13 | 132 |
| entities: typed rows | 98 | 646 | 5,530 |
| mentions: all originals | 535 | 3,785 | 40,070 |
| mention_entity_links | 151 | 1,342 | 15,270 |
| events | 8 | 43 | 299 |
| relations: directed rows | 161 | 2,393 | 18,330 |

The hundred-page entity table contains 2,383 resolved QID/type rows (2,155 distinct QIDs), 2,848 provisional rows and 299 Event-type rows. Events comprise 181 accepted corpus QIDs and 118 added article-linked Events. Relations contain 9,187 native base assertions plus 9,143 derived inverse rows. A self assertion does not create an identical duplicate inverse.

The six compressed tables are in `final_3/`, `final_10/` and `final_100/`, each with a hash manifest. These are local model-table snapshots, not database loads. The 132 wiki_pages rows represent historical revisions of 100 distinct pages, not 132 different pages.

Independent accounting verified every shared mention and typed bridge across 3→100 and 10→100, after declared scope-specific evidence fields were excluded. Raw fields, stable IDs, source/page/revision metadata, eligibility, unique bridges and typed endpoints pass. Root independently reread all final tables, checked their hashes and counts, reran core EDA controls and checked both comparison file hashes. Evidence: `root_final_verification.json` and `eda_final_N/execution_receipt.json`.

Hundred-page cache-only enrichment, final assembly and EDA took 157.719 seconds (82.125 + 61.094 + 14.500). Combined elapsed for those stages across all three scopes was 210.157 seconds; it excludes waiting for core inputs. Per-stage receipts retain timings and explicit validation limits.

EDA status is `CORE_CONTROLS_PASSED_OPTIONAL_TABLES_NOT_EVALUATED`. Structural checks include source/hash/count/typed foreign keys and native inverse evidence. They do not establish Event-discovery completeness, Event semantics, relation mapping/temporal semantics, model accuracy or Geography. Optional co-occurrence analysis was not run.

## Remaining work outside this execution

1. Review the 7,918 source-review rows, including useful content held by context uncertainty.
2. Review changed/lost QID sets and high-QID fan-out before promoting experimental model assignments.
3. Investigate eligible unresolved mentions against source inventory, candidate coverage and model rejection using independently reviewed examples.
4. Keep DATE, Geography, database loading and any model retraining as separate, unexecuted work.
