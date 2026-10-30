# Shared QID filtering and bidirectional matching: 100-page experiment

Completed run: 2026-10-30, Asia/Jerusalem (UTC+02:00). The three-page, ten-page and 100-page stages are complete. All 13 final output files passed remote/local SHA256 checks; local report replay preserved their bytes. The VM is confirmed TERMINATED. This report records experimental proposals, not accepted identities or measured accuracy. No assignments changed. No Event data run occurred.

## Scope and shared safeguards

The experiment uses the saved 100 pages and their exact revisions. The shared policy is `qid-source-native-types-v1`. Matching joins candidates on `(page_id, revision_id, qid)`; a QID on another revision does not establish support for the current revision.

Source filtering uses saved raw direct links, recovered template evidence, and verified page identity. A QID remains eligible if it has KEEP or REVIEW support. Incomplete evidence remains UNKNOWN_KEEP. Removal requires complete evidence showing that all support is EXCLUDE. REVIEW is advisory, not a rejection rule. Unknown support is not proof of article presence.

Type checks use inventory-native P31 and the saved P279 hierarchy, not label-based inference or replacement P31 from the older hierarchy cache. Native metadata includes a 2026-10-25 BigQuery snapshot retrieved on 2026-10-28 (11,850 retained rows), plus saved Wikidata API retrievals from 2026-10-28 and 2026-10-29 (1,021 retained rows). Of the API rows, 78 have no metadata_snapshot_utc. The hierarchy cache is from 2026-10-18. These snapshots and lookup dates do not establish historical Wikidata types for the article revision. PER, ORG, and LOC use the agreed category roots; multiple categories are allowed. Missing metadata or incomplete ancestry remains eligible and marked unknown. Known types with no compatible category can be rejected. MISC remains broad; DATE is deferred.

The shared checks apply before exact-match uniqueness, before ordinary candidate ranking/protection/coverage, in reverse pools, and in final pair validation. Saved decisions cannot bypass the checks in these paths. Event callers and assembly now require the bound source inventory, exact used revisions, and permitted article-bound phases; these are code safeguards, not evidence of an Event data run. See the [implementation plan and execution record](../superpowers/plans/2026-10-30-shared-qid-filters-bidirectional.md).

## Inventory and candidate counts

The final [pool audit](../../Data/external/filtered_matching_20261030/pool_counts.json) replaces the earlier provisional type-count diagnostics.

| Inventory measure | Count |
|---|---:|
| Original page/revision/QID rows | 13,470 |
| Source-excluded rows | 599 |
| Retained rows | 12,871 |
| Retained KEEP / REVIEW_KEEP rows | 12,707 / 164 |
| Distinct QIDs before / after source filtering | 5,072 / 4,874 |
| Retained rows with unknown types | 1,149 |
| Preserved title-fallback rows | 29 |

**Count correction:** 1,208 unknown-type rows in the filter summary cover all 13,470 rows. The retained-inventory count is 1,149. An earlier plan checkpoint described 1,208 as retained; use the corrected denominator above.

For all 9,016 remaining groups, the potential reverse candidate count changes from 1,781,371 to 1,697,530 after source filtering, then to 969,711 after type checks. The removals are 83,841 source pairs and 727,819 type pairs. The retained pool contains 144,382 unknown-type pairs. Adding one STOP per group gives **978,727 candidate-plus-STOP scores**, an upper bound if every new forward occurrence fails. It is not the actual reverse workload.

Prepared forward input contains 7,277 occurrences in 5,546 groups. It has 367,361 candidate pairs and 10,644 STOP options, or 378,005 prepared scores. Of 12,871 QID questions, 2,227 have empty candidate pools and are skipped. These are prepared workload counts, not final selections or a claim about iterative model-call totals.

## Cohort sequence and completed stages

The forward direction runs only the **7,277 newly admitted review occurrences**. It uses QID queries, compatible mention options, the existing trigram policy, and the iterative stop rule. Reverse then runs the **5,852 prior unresolved occurrences plus only new forward failures**. Reverse offers every compatible QID on the exact page/revision, without a trigram cutoff. It does not start with all 13,129 occurrences.

The inclusive prior/new group views overlap in 386 groups and must not be added. The disjoint partitions are 3,470 prior-only groups, 5,160 new-only groups, and 386 mixed groups, totaling 9,016. Occurrence membership remains separate when a group contains both cohorts.

| Measure | Three pages | Ten pages | 100 pages |
|---|---:|---:|---|
| New forward input occurrences | 85 | 725 | 7,277 input |
| Prior unresolved occurrences | 67 | 467 | 5,852 input |
| Forward-selected distinct occurrences | 35 | 326 | 3,086 |
| Forward-selected QID/group pairs | 32 | 217 | 2,453 |
| New forward failures | 50 | 399 | 4,191 |
| Reverse input occurrences | 117 | 866 | 10,043 |
| Reverse-selected distinct occurrences | 93 | 702 | 7,792 |
| Reverse-selected QID/group pairs | 70 | 446 | 5,074 |
| Reverse STOP occurrences | 24 | 164 | 2,251 |
| No-compatible-QID occurrences | 0 | 0 | 0 |
| Total distinct occurrences with proposals | 128 | 1,028 | 10,878 |
| Remaining occurrences | 24 | 164 | 2,251 |

Sources: [100-page summary](../../Data/external/filtered_matching_20261030/scope_100/summary.json), [three-page summary](../../Data/external/filtered_matching_20261030/scope_3/summary.json) and [ten-page summary](../../Data/external/filtered_matching_20261030/scope_10/summary.json). Scopes overlap and are separate staged outputs; do not add their totals. The execution record reports that three-page proposals agree exactly with the corresponding ten-page output.

**Records are not occurrences:** the three-page file contains 128 proposal records for 128 distinct occurrences. The ten-page file contains 1,040 records for 1,028 distinct occurrences: 338 forward records cover 326 occurrences, while 702 reverse records cover 702 occurrences. Twelve forward occurrences each have two QID proposals. The summary field `proposal_occurrences_by_type` counts proposal records, not deduplicated occurrences. See the [ten-page proposals](../../Data/external/filtered_matching_20261030/scope_10/occurrence_proposals.jsonl).

The full 100-page proposal file contains **11,405 records for 10,878 distinct occurrences**: 3,613 forward records and 7,792 reverse records. The completed forward checkpoint contains 3,086 distinct occurrences, 3,613 occurrence–QID links and 2,453 group–QID pairs (2,448 model, 5 exact). There are 285 occurrences with multiple proposed QIDs; the maximum is 18. The group USS LST on page 901674/revision 1379267177 has 18 proposals; LST-542-class tank landing ship has 14. Such fragments/class names can refer to a class, a member, or incomplete text. Multiple links are permitted, but these counts do not verify identity. See [forward counts](../../Data/external/filtered_matching_20261030/forward_100_checkpoint/summary.json) and [examples](../../Data/external/filtered_matching_20261030/forward_100_checkpoint/multiple_qid_examples.json). The final forward file matches the earlier local checkpoint byte for byte; final remote hashes are verified.

## Source checks on forward selections

The [forward source audit](../../Data/external/filtered_matching_20261030/source_audit_forward/summary.json) checks ten traceable model-selected occurrences from the ten-page stage: seven source agreements and three conflicts. Six are direct-link cases (five agree); four use documented templates (two agree). All ten were model decisions, not exact-match outputs. This selected subset is not an accuracy sample.

Two Brooklyn occurrences explicitly target Brooklyn-class cruiser Q929294 in the source, but the proposal selects Brooklyn city Q18419. The correct class was blocked by the Daniel LOC type predicate. Yugoslavian explicitly links Kingdom of Yugoslavia Q191077; that QID was offered, but Yugoslavia Q36704 was selected. These distinguish a filter loss from a model ranking error. The audit preserves source spans, mapping responses and 33 input hashes.

## Source checks on reverse selections

The [six-case audit](../../Data/external/filtered_matching_20261030/source_audit_3/cases.json) binds exact source spans, raw-file hashes, saved target mappings, candidate availability, and scores. Its [summary](../../Data/external/filtered_matching_20261030/source_audit_3/summary.json) binds 20 files. There are **two source agreements and four conflicts** in this selected, traceable subset. This is not a random sample or an accuracy estimate; no LLM labels are used as gold.

| Source row and mention | Source-supported QID | Selected QID | Source QID offered? |
|---|---|---|---|
| 1470461, Urakaze | Q11558386, Urakaze | Q1132501, Mikazuki | Yes |
| 1470450, Hizen | Q2032888, Retvizan/Hizen | Q4389875, Kitakami | Yes |
| 312952, Pacific | Q98, Pacific Ocean | Q2632857, American Theater | Yes |
| 1470383, Kumano | Q1791961, Kumano | Q81863, Akita Prefecture | No: ORG type rule |
| 1470510, Mogami | Q1850384 | Q1850384 | Yes |
| 1470463, Mikazuki | Q1132501 | Q1132501 | Yes |

Urakaze, Hizen, and Pacific show ranking conflicts even though their source-supported QIDs were offered. Kumano shows a different limitation: the approved native-type predicate can remove a source-supported ship QID when the mention has an ORG label. These findings do not authorize label, filter, threshold, or assignment changes.

Eight of 70 selected reverse groups have a literal inventory label, alias, or linked-title match. Five matching QIDs were offered and two selected. In the actual offered model name/alias text, only Pacific has a literal exact match; it still loses to American Theater. Inventory linked titles must not be confused with aliases actually supplied to the model.

The 70 selected groups cover 93 occurrences and choose 21 QIDs. The five most frequent group QIDs cover 39/70 groups: Mogami 11, barbed wire 9, Michishio 7, Mikazuki 6, and I-25 6. The five most frequent occurrence QIDs cover 54/93 occurrences. Concentration alone does not prove an error.

Eleven named groups, covering 16 occurrences, are explicitly excluded from the clear comparison. Wakatake has no verified QID in saved recovery. Southern Force redirects to Battle of Leyte Gulf, which does not prove force identity. Other exclusions include partial template/title fragments and nonunique raw placements. These named exclusions do not classify all 87 remaining selected occurrences. Saved target mappings are current/cached, and ship targets use documented template rules; neither is historical identity proof for the article revision.

The [type-policy audit](../../Data/external/filtered_matching_20261030/type_filter_caveats.json) verifies Kumano's complete cached ancestry: heavy cruiser → cruiser → warship, with no approved ORG root. The rejection is caused by the chosen category roots, not absent ancestry. Other common classes in known-unclassified saved-link conflicts are destroyer (168 links), guided missile destroyer (116), and battle (114). These counts can overlap for multiple native classes and are not type-accuracy measurements.

## Numerical sensitivity and existing assignments

The [forward CPU/GPU comparison](../../Data/external/filtered_matching_20261030/cpu_gpu_forward_comparison.json) records one changed selection among 124 common questions. The [reverse comparison](../../Data/external/filtered_matching_20261030/cpu_gpu_reverse_comparison.json) records three changed choices among 43 common questions. CPU used float32; GPU used bfloat16 autocast. CPU reverse completed only 44 questions before its 900-second cap; GPU completed 89. This partial comparison shows execution sensitivity, not that either platform is correct, and does not establish dtype as the sole cause. Reverse STOP was not trained for this reversed task. No measured accuracy is available.

The [prior-assignment policy audit](../../Data/external/filtered_matching_20261030/prior_assignment_audit/summary.json) checks 9,833 distinct saved occurrence/QID links. Of these, 8,344 pass the new policy and 1,489 fail: 74 source exclusions and 1,415 type conflicts. Failures affect 1,213 occurrences; 469 also have a passing saved QID and 744 have only failing saved QIDs. There are no absent-inventory failures. Passing means policy eligibility, not correct identity; failing means a policy conflict, not an adjudicated identity error. All saved assignments remain unchanged.

## Code steps

| File or existing step | Purpose |
|---|---|
| `filter_qid_inventory.py` | Produce the source-filtered QID inventory and native-type evidence. |
| `match_exact.py`, `prepare_candidates.py` | Apply shared eligibility before exact matching and candidate preparation. |
| `match_remaining.py` | Run new forward decisions, then reverse only the remaining cohort; save scores, proposals, runtime and resume bindings. |
| Existing `post_qid_*` pipeline files | Reject out-of-scope saved pairs and bind Event evidence/assembly to the same inventory and revisions. No Event data was regenerated here. |

Training files and model weights were not changed.

## Code verification and completion

Local code commit: `3a90a0a` — `Filter page QID inventories consistently and add staged matching experiment`. The execution record reports **902 affected-subsystem tests passed in 37.71 seconds** with:

```text
pytest --import-mode=importlib GG_Data/entity_resolution/hundred_page_pilot GG_Data/pipeline -q
```

Importlib collection avoids duplicate `test_pipeline` module names. Touched-file Ruff checks passed. These are recorded code checks, not model accuracy tests; they were not repeated for this report. Resume checks bind model/helper code, tokenizer assets, package versions, and direction-specific jobs; changed bindings and orphan scores are rejected. No Event data run or assignment promotion is implied by these checks.

The [transfer receipt](../../Data/external/filtered_matching_20261030/scope_100_transfer_verification.json) verifies the archive and all 13 final files. Archive SHA256: `d2267bc15b93cf24bf73ec336e545138308374d15dae563786b5311d02d8c43e`. The [integrity receipt](../../Data/external/filtered_matching_20261030/input_integrity_after.json) verifies 13 original pool-input hashes and unchanged final files after local report replay.

Actual 100-page work: 378,005 forward candidate/STOP scores, followed by 688,201 reverse candidate/STOP scores across 6,789 groups. Total: 1,066,206 scores. Reverse input is exactly 5,852 prior occurrences plus 4,191 new forward failures. Every reverse group had compatible candidates; the 2,251 remaining occurrences received STOP. This does not establish that no relevant QID exists: the needed identity could be absent from the linked inventory or blocked by a type rule, or the model could reject it.

The 100-page runtime was 1,970.592 seconds (32m50.6s), from 03:47:45.932 to 04:20:36.524 Asia/Jerusalem. Three-page runtime: 33.154s; ten-page runtime: 148.855s. The CPU pilot reached its 900s cap at 902.094s elapsed, during reverse; it was not a complete result. Runtime is elapsed execution, not measured active work. Existing old forward scalars were not reused: new contexts, options and bindings were scored explicitly. Each staged scope was a separate verification run.

The [VM/budget receipt](../../Data/external/filtered_matching_20261030/budget_after.json) records 03:33:03.660 start and 04:23:47.593 stop Asia/Jerusalem. New VM time: 3,043.933s (50.73min), under 90min. Aggregate: 18,871.944s (5.242h), under 6h. Conservative aggregate estimate: US$7.3422, under US$10; actual billing is unknown. The estimate carries the prior allowance unchanged and uses US$1/hour for new compute. The existing stopped VM/disk remain; no deletion occurred. Automatic restart is disabled.

Run issues and adjustments: two capacity failures before the existing VM started; the remote environment lacked imports already used by the project, so they were installed in its task environment; identical-output resume writing was corrected and tested; duplicate test module names required pytest importlib collection. A direct copy of an actively growing score file failed in PuTTY; it remains marked partial and was not used as final verification. Final transfer used a completed immutable archive. Model/checkpoint/thresholds were unchanged. Active-work, approval-wait and environment-wait durations are unknown unless separately measured; no incompatible Epoch actual was invented.

Final outcome/subset audit and final documentation checkpoint are recorded below. No paid BigQuery, collection, retraining, Geography, Event data regeneration, or assignment promotion occurred. Code/report protection is a local Git checkpoint only; ignored experiment data are local and unpushed.

## Final cohort and subset audit

The [final outcome audit](../../Data/external/filtered_matching_20261030/scope_100_outcome_audit.json) verifies 19 unchanged input bindings. Forward and reverse selected occurrences are disjoint. Every nonempty job has complete, finite option scores and one STOP; no independent model-score replay is claimed. All 128 three-page proposal links and all 1,040 ten-page links exactly match their full-run subsets by occurrence, QID and direction.

| Cohort | Input occurrences | Forward proposals | Reverse proposals | Still unselected |
|---|---:|---:|---:|---:|
| Newly admitted | 7,277 | 3,086 | 3,252 | 939 |
| Prior unresolved | 5,852 | 0 | 4,540 | 1,312 |
| Total | 13,129 | 3,086 | 7,792 | 2,251 |

| Daniel type | Distinct occurrences with proposals | Still unselected |
|---|---:|---:|
| LOC | 3,769 | 912 |
| MISC | 3,448 | 93 |
| ORG | 2,284 | 787 |
| PER | 1,377 | 459 |
| Total | 10,878 | 2,251 |

All 285 multiple-QID occurrences are forward selections, producing 527 extra links; reverse makes one choice per group in this experiment. Multiple identities remain permitted by the data model, but the maximum of 18 proposals requires source review. The saved summary field proposal_occurrences_by_type counts links; the table above counts distinct occurrences.

The filters reduce workload, but the source audit shows valid ship/class candidates can be blocked by Daniel type labels. Both model directions also show ranking errors with the source-supported QID available. The reversed direction and its stop sentence were not trained. These findings prevent treating the selection counts as verified resolution. Before any promotion, review the type policy and model decisions against reference examples. No policy, model or assignment was changed automatically.

Delivery includes code commit `3a90a0a`, this report, the execution plan and the local artifacts linked above. Final documentation is committed separately after review. Backup status: **Local checkpoint only**. Nothing was pushed, and ignored experiment data are not covered by the Git commits.
