# Source-name and template pilot — 29 October 2026

**Status: in progress. Three- and ten-page paired deliveries are complete; the fixed-model 100-page comparison is running.**

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

The accepted preparation repaired **1,815 rows** (918 distinct names, 1,072 page/revision/name/type groups). All 40,070 original rows and columns except `word` are preserved. All 7,372 DATE rows are unchanged. Repair methods: citation authors 1,097; documented ship targets 440; ordinary anchors 77; anchor plus alias 46; alias 153; nihongo 2. There are 20,637 source-evidence rows and 19,202 original-row bridges; evidence rows are not unique entity counts.

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

The corrected run has **140 new original-row/QID pairs and four lost pairs**. There are 139 newly matched rows and three rows that lose all matches: net +136 matched rows. Two hundred and ten names were repaired; 98 corrected rows have multiple QIDs. Independent review traced all four lost pairs to previous model predictions on three repaired rows; none came from lost exact proof. Examples: Diego expanded to Diego-Suarez and lost Diego Garcia; citation author John Wukovits lost John S. McCain and John Henry Towers; W. Thomas Smith lost Thomas Withers. These are source-context diagnostics, not a complete accuracy score. All195 baseline exact row/QID pairs sent to model review by the new guards were recovered by that model. Of12 deterministic new examples inspected, a Robert/Robert W. Hayler assignment remains uncertain because the saved text only gives an editor first name. All140 new pairs remain unlabelled outside the frozen reference. More matched rows do not establish greater accuracy.

Combined ten-page inference:394.83265s for131448 option evaluations,332.9208pairs/s. The remaining100-page arms contain1572823evaluations; linear forecast78.74minutes, before setup/transfer/report overhead. The verified VMSTOPlimit remains unchanged.

## Candidate coverage diagnostic, all100pages

The unchanged frozen reference has4301original group/QID positive pairs. Expanding original groups to their source rows gives8181row/QID pairs:8154non-DATE and27DATE excluded by policy. This is a source-derived diagnostic, not independently labelled mention truth.

| Stage of the same non-DATE reference pairs | Baseline | Corrected |
|---|---:|---:|
| Accepted by exact matching |5602|3639|
| Reaches model candidate list |2323|4345|
| Combined coverage |7925/8154 (97.19%)|7984/8154 (97.92%)|
| Excluded by candidate retrieval |98|39|
| Missing usable English label/job |131|131|
| Absent from inventory |0|0|

The correction makes59previously excluded source-positive row/QID pairs reachable; no new retrieval miss appears in this reference. The131missing-label pairs involve14distinctQIDs across15page/revision/QID rows; aliases are available, but this experiment does not silently substitute them for labels. Entire inventories have29missing-label scope/QID rows across16distinctQIDs. English sitelinks are not in this inventory schema; linked source titles are not labelled as sitelinks.

The frozen reference was built using original available mappings. Therefore inventory-absent0 does **not** prove complete coverage of all Daniel names or unlinked entities. Candidate coverage is separate from final model recall, precision and accuracy. Evidence and missed-pair CSVs are in `candidate_coverage_review_100/`; audit11.562s and verification1.610s. No model or API call was used.

## Model and evaluation limits

- Fixed LUKE checkpoint SHA-256: `51246b874d6346bf2769077e0067f99f20cb28f6c7a09a02ee78f1c30a2fad20`.
- The checkpoint contains encoder weights after 1,000 encoder optimizer updates; training had a frozen warmup first.
- Previous held-out choice accuracy: 551/608 = 90.63%. Stop precision: 278/311 = 89.39%, below the agreed 90% target.
- OWNER approved this exploratory run. That approval is not a quality pass.
- The frozen Daniel reference contains source-supported positives, not complete positive/negative labels. Its recall can be reported; overall precision and accuracy remain unknown.
- Current code can be bound to the restored checkpoint. Original training-time code immutability is not proved.
- The earlier training/inference input-format difference remains deferred; both experiment arms use the same current formatter.
- Historical text containment identifies a supported revision; it does not prove Daniel extracted that exact revision.

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

The existing US$10 aggregate ceiling remains in force, with US$2 reserved for unmeasured costs. Prior estimated compute/query subtotal: US$1.548042. The VM started at 14:27:49.863. It has a verified 10,800-second automatic STOP limit. The six staged arms contain 1,723,240 option evaluations including stop. The saved-rate forecast is 122.78–142.78 minutes including 20–40 minutes overhead; it is not a guaranteed bound. At the full new three-hour compute cap, saved estimates plus the US$2 reserve total US$5.66854, below US$10. Billing actuals, storage and transfer costs are not yet verified.

## Artifacts and protection

Experiment directory: `Data/external/hundred_page_pilot_20261028/template_name_pilot_20261029/`.

It contains frozen input hashes, source evidence, API response hashes, retained earlier artifacts, fixed review samples and separate outputs for each experiment arm and page scope. There is no paid BigQuery query, retraining, Geography, Event/table rebuild or full-corpus rerun in this experiment.

Code checkpoints so far: `d850d28`, `53b88a2`, `c83808b`, `dfd382c`. **Local checkpoint only.** No push is authorized. Ignored data and model weights remain local; a local commit does not protect them on GitHub.
