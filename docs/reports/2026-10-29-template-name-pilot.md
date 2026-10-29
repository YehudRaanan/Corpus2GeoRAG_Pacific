# Source-name and template pilot — 29 October 2026

**Status: all paired runs, exports and independent source-context reviews complete. VM confirmed stopped at 16:03:36 on 29 October 2026, Asia/Jerusalem. Results remain experimental.**

The corrected 100-page run matches **961 more original mentions**: 13,627 to 14,588. However, recovery of the unchanged source-positive reference falls from 6,834 to 6,798 of 8,154 pairs. Candidate coverage improves while final reference recovery declines. This is a mixed result, not evidence of improved overall accuracy. Original data and the fixed model remain unchanged; neither experiment arm is promoted to production.

Scope: the saved 100 pages, 132 used historical revisions and 40,070 Daniel rows. DATE is excluded from matching; all 7,372 DATE rows remain in the exported data. Original source files and model weights are unchanged.

## Process and files

| Code file | Work |
|---|---|
| `hundred_page_pilot/recover_page_qids.py` | Recover source-encoded targets and missing page QIDs. Preserve historical text evidence separately from current lookups. |
| `hundred_page_pilot/prepare_mentions.py` | Prepare supported complete names; preserve `word_original`, original offsets, IDs and type. Save recovered spans and their links to original rows. |
| `hundred_page_pilot/prepare_candidates.py` | Group names/types on the same page revision. Apply independent literal exact matching, then top-80 trigram candidates plus source-supported candidates. |
| `hundred_page_pilot/resolve_entities.py` | Use the fixed scorer and select remaining groups until the stop sentence wins. Several groups and QIDs can be linked. |
| `hundred_page_pilot/readiness.py` | Check actual checkpoint restore evidence, source hashes and explicit experimental approval. |
| `hundred_page_pilot/report.py` | Require complete scores, export every original row, and compare original row-to-QID sets. |

Training remains separate in `decision_model/`. This run does not train or change the model formatter, stop sentence, thresholds or numerical precision.

## Verified source preparation

- Original inventory: 12,371 page–revision–QID rows.
- Expanded inventory: 13,470 rows; 1,099 added rows, including 23 earlier recovered rows.
- The added rows contain 606 distinct QIDs; 550 were absent from the original pilot inventory across all pages.
- Recovery used 126 public API requests, with no request failures. The corrected cache-only replay used zero new requests.
- Original 100-page baseline: 19,142 non-DATE groups, 3,455 exact group–QID pairs, 12,342 model questions and 754,445 option evaluations including stop.

These counts do not measure matching accuracy. A recovered page QID only makes an identity available as a candidate.

## Problems caught before inference

The first prepared artifact proposed 3,926 replacements. It was **not accepted for inference**. A prediction-independent sample found that enclosing text can refer to another entity:

| Original | Rejected first suggestion | Reason |
|---|---|---|
| Virginia | Fort Humphreys, Virginia | A state name inside a fort label is not proof of fort identity. |
| U.S. Treasury | U.S. Treasury bills | The organization and its securities are different entities. |
| World War II | List of World War II aces from Japan | A war name inside a list title does not name that list. |
| Nadzab | Landing at Nadzab | The first suggestion came from a navigation template. |
| Purple | Purple Heart | This occurrence came from a ribbon image filename. |

Original prepared files, sample IDs and exact source slices are retained. The source guard update excludes hidden metadata/navigation from general name discovery and keeps unsupported complete-word expansions for review. Explicit supported name fields and clipped tokens have separate rules. Types are preserved; incompatible explicit ship/person/place cases remain under review.

A separate bug blocked independent exact proof for unchanged original names whenever QID-name evidence existed. This was fixed with a regression test. Changed names still cannot create their own automatic exact proof.

The accepted preparation repaired **1,815 rows** (918 distinct names, 1,072 page/revision/name/type groups). All 40,070 original rows and columns except `word` are preserved. All 7,372 DATE rows are unchanged. Original `start`/`end` still select `word_original` within `Text`; separate repaired/source offsets identify the recovered support. A reconstructed template title need not be a literal substring. Repair methods: citation authors 1,097; documented ship targets 440; ordinary anchors 77; anchor plus QID label/alias occurrence 46; QID label/alias occurrence 153; nihongo 2. There are 20,637 source-evidence rows and 19,202 original-row bridges; evidence rows are not unique entity counts. A further 4,058 recovered-only evidence spans have no original mention overlap; they are retained as evidence, not added as Daniel rows.

The same 139 original row IDs were reviewed before predictions. The 21 remaining repaired contexts in this sample had no further confirmed wrong repair. This sample does not establish accuracy. All ten reported/follow-up critical names retain their original words. A synthetic ship-infobox type-guard gap remains documented; no actual accepted repair uses that infobox family.

## Three-page delivery

| Measure | Baseline | Corrected |
|---|---:|---:|
| Original rows |535|535|
| Excluded DATE rows |90|90|
| Eligible non-DATE rows |445|445|
| Matched original rows |166|183|
| Unresolved non-DATE rows |279|262|
| Original-row/QID pairs |168|185|
| Matched groups, independently corrected |84|99|
| Unresolved groups, independently corrected |188|163|
| Frozen source-positive pairs recovered |83/90|83/90|

There are **17 newly matched rows/pairs, zero lost pairs and zero changes to existing nonempty QID sets**. Forty-two original names were repaired. Two corrected rows have more than one QID. Examples include `I` and `25` becoming `I-25`, linked to Q2354535. All 17 new pairs lie outside the incomplete positive reference; they remain unlabelled. Repairing citation-author names does not guarantee a page-linked QID exists for those authors.

Independent review checked all original columns, all pair-set/type/page counts and every new source context. A summary-only bug counted empty dictionary lookups as matched groups. Original three-page summary files are retained; `comparison_review_3/review.json` supplies the corrected group counts above. A two-line reporting fix and regression test passed the 136-test full pipeline suite; later exports use it. Row-level Parquet/QID data are unaffected.

## Ten-page delivery

| Measure | Baseline | Corrected |
|---|---:|---:|
| Original rows |3785|3785|
| Excluded DATE rows |811|811|
| Eligible non-DATE rows |2974|2974|
| Matched original rows |1290|1426|
| Unresolved non-DATE rows |1684|1548|
| Matched groups |612|671|
| Unresolved groups |1029|941|
| Exact group/QID pairs |283|218|
| Model group/QID pairs |369|493|
| Frozen source-positive pairs recovered |611/763|611/763|

The corrected run has **140 new original-row/QID pairs and four lost pairs**. There are 139 newly matched rows and three rows that lose all matches: net +136 matched rows. Two hundred and ten names were repaired; 98 corrected rows have multiple QIDs. Independent review traced all four lost pairs to previous model predictions on three repaired rows; none came from lost exact proof. Examples: Diego expanded to Diego-Suarez and lost Diego Garcia; citation author John Wukovits lost John S. McCain and John Henry Towers; W. Thomas Smith lost Thomas Withers. These are source-context diagnostics, not a complete accuracy score. All 195 baseline exact row/QID pairs sent to model review by the new guards were recovered by that model. Of 12 deterministic new examples inspected, a Robert/Robert W. Hayler assignment remains uncertain because the saved text only gives an editor first name. All 140 new pairs remain unlabelled outside the frozen reference. More matched rows do not establish greater accuracy.

Combined ten-page inference: 394.83265 s for 131,448 option evaluations, or 332.9208 pairs/s. This gave a 78.74-minute linear forecast for the two 100-page arms, before setup/transfer/report overhead. Actual combined 100-page inference was 75.69 minutes.

## Hundred-page delivery

| Measure | Baseline | Corrected |
|---|---:|---:|
| Original rows |40,070|40,070|
| Excluded DATE rows |7,372|7,372|
| Eligible non-DATE rows |32,698|32,698|
| Matched original rows |13,627|14,588|
| Matched share of eligible rows |41.68%|44.61%|
| Unresolved non-DATE rows |19,071|18,110|
| Original-row/QID pairs |15,983|17,667|
| Rows with multiple QIDs |1,605|1,781|
| Matched page/revision/name/type groups |6,543|7,217|
| Unresolved groups |12,599|11,712|
| Exact group/QID pairs |3,455|2,461|
| Model group/QID pairs |3,559|5,395|
| Final distinct QID/Daniel-type entities |3,458|4,075|
| Frozen source-positive pairs recovered |6,834/8,154 (83.81%)|6,798/8,154 (83.37%)|

The corrected arm adds **1,850 row/QID pairs and removes 166**. There are 1,037 newly matched rows and 76 rows that lose all matches: net **+961** matched rows. Another 324 rows have changed nonempty QID sets. These measures overlap where appropriate; pair counts and row counts are different units. All 1,815 repaired mention rows retain their old values and source evidence; they contain 918 distinct repaired names.

| Daniel type | Original rows | Baseline matched | Corrected matched | Corrected unresolved | New / lost row-QID pairs |
|---|---:|---:|---:|---:|---:|
| LOC |10,478|5,145|5,305|5,173|174 / 1|
| MISC |8,983|3,409|3,866|5,117|777 / 103|
| ORG |7,555|2,907|3,182|4,373|557 / 5|
| PER |5,682|2,166|2,235|3,447|342 / 57|
| DATE, excluded |7,372|0|0|Not an unresolved matching result|0 / 0|

Both exports contain every original row. `unresolved_mentions.parquet` contains both `UNRESOLVED_ENTITY` and `EXCLUDED_DATE` records; filter the status when counting unresolved entities. DATE is not included in the 18,110 unresolved total.

The independent automated review checks original/prepared columns, offsets and revision provenance, every type/page/group metric, score completeness, checkpoint/reference hashes and expansion from group pairs to original-row pairs. All checks pass. The baseline used at most 80 mention candidates plus stop per question. Source protection increased the corrected maximum to 85 mention candidates plus stop; the measured pair totals include every option.

## Source-context review and interpretation

An AI reviewer inspected every lost pair: **166 pairs, 117 original rows and 93 distinct contexts**. It also inspected the prediction-independent sample rule's 24 new pairs across 23 rows. Source verdicts for this new-pair sample are 15 source-consistent, eight identity conflicts and one uncertain boundary. This is a small deterministic diagnostic, not a representative accuracy estimate, human gold labelling or independent validation of every QID.

| Case | Observed result | Meaning |
|---|---|---|
| `I` / `25` in a submarine target | Reconstructed `I-25` and linked Q2354535 | Source reconstruction can expose the intended full name. |
| Person `Shoup` in general/Commandant prose | Added USS Shoup, Q2003694 | Same surname does not mean the same entity; the original person match also remains. |
| `Fletcher` reconstructed as Fletcher-class destroyer | Added individual ships, including USS Dyson Q1239245 | A class and its members are related but are different identities. |
| Citation `Brian MacArthur` | Removed a Douglas MacArthur match | Some lost predictions were inconsistent with the source author. |
| Unchanged `World War II` | Lost 34 known Q362 pairs on two pages | Conservative source-review guards moved exact matches into model review, where they were rejected. |
| `D-Day` with explicit Normandy landings link | Lost the prior Q16470 model match | Candidate availability and source support do not guarantee model selection. |

All 36 lost frozen positives are 34 World War II pairs, one Red Army Q251395 pair and one D-Day/Normandy landings Q16470 pair. Other unlabelled losses include plausible identities such as William F. Halsey and I-158; they must not all be called corrections. The separate `comparison_review_100/review_needed_cases.csv` contains 50 review cases: nine new conflicts/uncertainties, 36 known positive losses and five plausible/uncertain unlabelled losses. No source verdict changes the saved assignments or reference.

| Same corrected-source cohort in both arms | Rows | Baseline matched | Corrected matched |
|---|---:|---:|---:|
| Documented template target |441|37|378|
| Citation author fields |1,097|57|20|
| Ordinary anchor |748|320|341|
| Anchor plus QID label/alias occurrence |2,478|2,367|2,393|
| QID label/alias occurrence |2,444|1,999|2,223|
| Nihongo name |2|0|0|
| No source method |25,488|8,847|9,233|

These are method cohorts, including supported unchanged rows; they are not counts of repaired names or isolated method effects. The 441 template-target cohort includes 440 repaired rows and one unchanged row. Many-to-many matching remains permitted, but it does not justify linking related classes, ships and people as the same identity.

**Automatic acceptance is not recommended.** A useful next experiment would preserve valid independent exact proof for unchanged names, test same-page hard negatives such as person/ship and class/member pairs, and evaluate reviewed positive and negative cases with aligned training/inference formatting. Those changes and any retraining are outside this completed experiment. Source recovery has value, but this combined version does not establish better final identity matching.

## What remains unresolved

The following table concerns only the same **8,154 known non-DATE positive row/QID pairs**, not all Daniel mentions:

| Final stage | Baseline | Corrected |
|---|---:|---:|
| Recovered |6,834|6,798|
| Reached model candidates but not selected |1,091|1,186|
| Excluded by retrieval |98|39|
| Missing usable English label/job |131|131|

The 59 added reachable positives do not become additional recovered reference matches. Final reference recovery has zero gains and 36 losses. Of 2,580 former exact row/QID pairs sent to model review by the new guards, 2,545 are recovered and 35 are lost; all 35 losses are in unchanged source-review groups. Thus a source guard can reduce automatic exact acceptance and expose a supported match to model rejection. These observations identify a practical weakness to review; they do not isolate the causal effect of each source/inventory/retrieval change.

In the corrected arm, 1,159 unresolved original rows have at least one frozen positive reference pair. The remaining unresolved rows have no positive in this incomplete reference; that does not prove the required QID is absent or that rejection is correct. Detailed same-cohort tables by repair method, repair status, Daniel type and page are in `outcome_diagnostics_100/`. No DATE linking or new fallback is applied.

## Candidate coverage diagnostic, all 100 pages

The unchanged frozen reference has 4,301 original group/QID positive pairs. Expanding original groups to their source rows gives 8,181 row/QID pairs: 8,154 non-DATE and 27 DATE excluded by policy. This is a source-derived diagnostic, not independently labelled mention truth.

| Stage of the same non-DATE reference pairs | Baseline | Corrected |
|---|---:|---:|
| Accepted by exact matching |5602|3639|
| Reaches model candidate list |2323|4345|
| Combined coverage |7925/8154 (97.19%)|7984/8154 (97.92%)|
| Excluded by candidate retrieval |98|39|
| Missing usable English label/job |131|131|
| Absent from inventory |0|0|

The correction makes 59 previously excluded source-positive row/QID pairs reachable; no new retrieval miss appears in this reference. The 131 missing-label pairs involve 14 distinct QIDs across 15 page/revision/QID rows; aliases are available, but this experiment does not silently substitute them for labels. Entire inventories have 29 missing-label scope/QID rows across 16 distinct QIDs. English sitelinks are not in this inventory schema; linked source titles are not labelled as sitelinks.

The frozen reference was built using original available mappings. Therefore inventory-absent count zero does **not** prove complete coverage of all Daniel names or unlinked entities. Candidate coverage is separate from final model recall, precision and accuracy. Evidence and missed-pair CSVs are in `candidate_coverage_review_100/`; audit 11.562 s and verification 1.610 s. No model or API call was used.

## Model and evaluation limits

- Fixed LUKE checkpoint SHA-256: `51246b874d6346bf2769077e0067f99f20cb28f6c7a09a02ee78f1c30a2fad20`.
- The checkpoint contains encoder weights after 1,000 encoder optimizer updates; training had a frozen warmup first.
- Previous held-out choice accuracy: 551/608 = 90.63%. Stop precision: 278/311 = 89.39%, below the agreed 90% target.
- OWNER approved this exploratory run. That approval is not a quality pass.
- The frozen Daniel reference contains source-supported positives, not complete positive/negative labels. Its recall can be reported; overall precision and accuracy remain unknown.
- Current code can be bound to the restored checkpoint. Original training-time code immutability is not proved.
- The earlier training/inference input-format difference remains deferred; both experiment arms use the same current formatter.
- Historical text containment identifies a supported revision; it does not prove Daniel extracted that exact revision.

## Issues and adaptations recorded during execution

| Issue | Action and evidence |
|---|---|
| Reused recovery rows could bypass a current conflict review | Corrected the merge rule and replayed from cache in 6.204 s; no additional API call. |
| First name preparation used enclosing or hidden source text | Rejected the first artifact before inference; added visible-source and token-boundary guards; retained both versions. |
| Wiki bold/italic parser nodes have no HTML opening bracket | Added a regression and used parser markup offsets; the failed run stopped before output. |
| Unchanged original names were incorrectly blocked from independent exact proof | Added regression; repaired/review groups stay conservative. |
| A completed worker did not restart from a message | Used a follow-up task; about six minutes of coordination delay are recorded, not labelled active work. |
| Default Windows encoding failed while writing the plan | Restored the tracked plan and execution log with explicit UTF-8; no source input or code was affected. |
| First offline restore used the wrong cache path | Verified the existing pinned cache and set `HF_HOME`; actual restore then passed before inference. |
| Empty group lookups inflated two summary fields | Corrected two lookups and added a regression. Saved three-page summaries remain immutable with a separate correction record. |
| README command selected the global interpreter | Used the existing task interpreter explicitly; smoke check passed. |
| New review records used a human-review field name for AI work | Renamed the fields to `ai_source_review_complete` / `reviewer_kind=AI_AGENT`; checked all 190 reviewed pair records and regenerated artifact hashes. Verdicts and assignments are unchanged. |

The same fixed model, option limit, formatter, source reference and stop rule remain in use. Source fixes, added inventory and protected retrieval are tested together; any net change cannot be attributed to name repair alone.

Final fresh verification: **136 tests passed in 11.01 seconds**. Root independently rechecked original input hashes, every original column against the corrected export, all 40,070 row IDs, all 7,372 DATE exclusions, pair-set counts, fixed checkpoint/completed-question records, review artifact hashes and stopped-state/cost arithmetic. `root_delivery_verification.json` records PASS at 16:12:24. Existing unrelated `luke_pilot/evaluate.py` changes and unresolved-audit documents are untouched.

## Runtime and cost record

All clock times use Asia/Jerusalem (UTC+02 on this date). Execution started at 13:34:24. Active work time is not measured. Script durations are distinct from total elapsed time.

| Stage | Measured runtime |
|---|---:|
| Baseline 100-page candidate preparation | 47.953 s |
| Initial bounded recovery | 58.344 s |
| Corrected cache-only recovery | 6.204 s |
| First mention preparation, retained for audit | 541.406 s |
| Accepted mention preparation v2 | 215.922 s |
| Corrected 100-page candidate preparation | 53.078 s |
| Three-page baseline / corrected inference | 28.775 / 33.649 s |
| Ten-page baseline / corrected inference | 189.009 / 205.823 s |
| Hundred-page baseline / corrected inference | 2,127.179 / 2,414.496 s |
| Hundred-page outcome diagnostic | 7.750 s |

The existing US$10 aggregate ceiling remains in force, with US$2 reserved for unmeasured costs. The VM ran from **14:27:49.863 to 16:03:36.423**, a measured 5,746.560 seconds (95.776 minutes), and is **TERMINATED**. Its 10,800-second automatic STOP guard was not reached. Prior plus new measured VM runtime is 13,233.644 seconds (3.676 hours), within the six-hour aggregate allowance.

At the saved US$0.706832276/hour rate, this run's compute estimate is **US$1.128293**. Adding the prior estimated compute/query subtotal US$1.548042 gives **US$2.676335**. Including the US$2 reserve gives **US$4.676335**, below US$10. These are estimates, not billing actuals; storage and transfer remain unverified. `vm_stopped.json` and `cost_after_stop.json` hold the evidence and arithmetic. No new paid BigQuery query was run.

The six staged arms completed 1,723,240 option evaluations including stop. The initial saved-rate forecast was 122.78–142.78 minutes including 20–40 minutes overhead; actual new VM runtime was 95.776 minutes. Forecasts were model-derived, not guarantees. Local reporting/review time is separate from VM runtime.

## Artifacts and protection

Experiment directory: `Data/external/hundred_page_pilot_20261028/template_name_pilot_20261029/`.

It contains frozen input hashes, source evidence, API response hashes, retained earlier artifacts, fixed review samples and separate outputs for each experiment arm and page scope. There is no paid BigQuery query, retraining, Geography, Event/table rebuild or full-corpus rerun in this experiment.

| Main artifact under the experiment directory | Content |
|---|---|
| `export_corrected_100/matched_mentions.parquet` | All 40,070 original rows, corrected `word`, `word_original`, matched QIDs, status and provenance. |
| `export_baseline_100/matched_mentions.parquet` | Comparable original-name baseline with the same model. |
| `prepared_100_v2/` | Corrected pre-matching rows, recovered spans and original-row evidence bridges. |
| `recovery_100_v2/` | Expanded source-backed QID inventory and lookup evidence. |
| `comparison_100/comparison.json`, `row_changes.csv` | Overall/type/page counts and original-row pair changes. |
| `comparison_review_100/` | All lost-pair contexts, fixed new-pair sample, review-needed cases and independent checks. |
| `outcome_diagnostics_100/` | Same-cohort method/status/type/page tables and remaining reference-pair stages. |
| `vm_stopped.json`, `cost_after_stop.json` | Verified stopped state, measured VM time and estimated cost arithmetic. |
| `root_delivery_verification.json`, `final_tests.log` | Final source/output checks and 136-test result. |

Code checkpoints include `d850d28`, `53b88a2`, `c83808b`, `dfd382c` and `8730b9d`; the final documentation checkpoint is recorded in the execution ledger. **Local checkpoint only.** No push is authorized. Ignored data and model weights remain local; a local commit does not protect them on GitHub.
