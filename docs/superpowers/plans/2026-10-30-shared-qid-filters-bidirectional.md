# Shared QID filters and bidirectional comparison implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Apply the same article-content and type rules before exact, normal and reverse matching, then compare experimental proposals on the saved 100 pages.

**Architecture:** One shared filter step writes a scoped QID inventory and source/type evidence. Pair compatibility is shared by both model directions and the final assignment validator. Existing source parsing, type metadata, checkpoint and scoring code are reused; saved assignments are immutable.

**Tech Stack:** Existing Python environment, PyArrow, mwparserfromhell, pytest, PyTorch/LUKE; no new dependencies.

**Spec:** Current OWNER request: try the proposed type mapping and exclude QIDs supported only by excluded article regions in both directions. Content filtering must apply throughout the pipeline.

## Global constraints

- OWNER approved the corrected sequence on 2026-10-30, execution resumed 03:10:58 Asia/Jerusalem. The preceding unfiltered reverse run was declined and is superseded, not resumed.
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
4. Use native P31 plus cached P279 traversal. Record both snapshots: hierarchy cache 2026-10-18 and inventory native metadata retrieved on2026-10-25 and2026-10-29. These are retrieval snapshots, not historical type proof. The hierarchy cache has 544,375 records, SHA256 `0032e97cf9af90f56dae231071dbdd2bed8d9c379708a029c4a53b407a9378f8`.
5. Feed the filtered inventory into exact matching before uniqueness checks, normal candidate preparation before trigram/protection/coverage, reverse pools, and final accepted-pair validation. Previously saved decisions cannot restore banned pairs.
6. Exact matching retains the agreed literal-name/one-QID/one-Daniel-type rule. Changes caused by filtering are reported separately; no historical assignment is overwritten.
7. CORRECTED SEQUENCE: normal direction runs ONLY the 7,277 newly admitted review occurrences (QID query, compatible mention options, existing trigram policy and iterative stop rule). Reverse population is the 5,852 prior unresolved occurrences PLUS only new forward failures. Reverse uses every compatible QID on the exact page/revision, no trigram cutoff. Never reverse all 13,129 up front. Preserve direction-specific proposals and all previous assignments.
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
- [x] Run independent type-count diagnostics. One gives 1,009,027 candidate-plus-stop scores (43.64% reduction); a second, corrected to start from inventory P31, gives 1,004,481. These disagree by 4,546 scores and are provisional, not an agreed final count. The inventory coverage check found 981 records with missing/incomplete type data; these must remain eligible.
- [x] Complete source-only count: 599 of 13,470 page/revision/QID records excluded; 12,871 retained (12,707 KEEP and 164 REVIEW_KEEP). Distinct QIDs decrease from 5,072 to 4,874. Verified 132 revision files, raw hashes, source offsets and page-own supports; no unknown source-support gaps were found.
- [x] Complete combined pool counts and persist the case-level exclusion ledger during implementation.
- [x] Freeze input hashes, cohort definitions and estimate basis in the new output manifest.

### 2. Shared filtering — implementation owner A; depends on task 1
Create `GG_Data/entity_resolution/hundred_page_pilot/filter_qid_inventory.py` and `test_filter_qid_inventory.py`.
Interfaces: `filter_inventory(entities, evidence, raw_root, type_metadata)` produces retained rows plus source/type audit; `compatible(entity, mention_type)` returns a boolean; the enriched inventory and case ledgers retain the evidence and reasons. Use existing records/dicts, not a new framework.
- [x] Add failing tests for mixed body/reference support, excluded-only support, unknown evidence, template anchors, page identity, complete/incomplete ancestry, overlapping categories and broad MISC.
- [x] Run focused pytest, implement minimal functions and CLI, rerun tests.
- [x] Write fresh filtered inventory and ledger; compare each removal against raw evidence. Check independently labelled examples and report any conflict before promotion.

### 3. Pipeline wiring — root, depends on task 2; test preparation can run in parallel
Modify `match_exact.py`, `prepare_candidates.py`, the existing workflow entry points and `GG_Data/pipeline/post_qid_entities.py` only where needed. Reuse existing tests in `test_revised_input_candidates.py`, `test_source_candidates.py` and `GG_Data/pipeline/test_post_qid_entities.py`.
- [x] Add failing tests: incompatible exact pair rejected, filtering before ranking, coverage cannot restore banned pair, final validator rejects stale banned pair, unknown remains eligible, REVIEW admitted and DATE deferred.
- [x] Wire the common inventory and predicate, with an explicit manifest policy version. No independent per-direction rules.
- [x] Run focused pytest and installed lint/format checks on touched files.

### 4. Bidirectional experiment — root sole GPU owner; depends on tasks 2–3 and approval
Reuse normal scorer/decision loop and the reverse ordering in `decision_model/probe_reverse.py`. Add one focused batch experiment runner if existing orchestration cannot express both directions safely.
- [x] Build immutable normal/reverse jobs from remaining-only groups. Verify exact page/revision boundaries and counts; distinguish empty pools from model rejection.
- [x] Prove exact-text forward reuse where possible; record reused versus newly scored counts. Never resume an old changed-hash job manifest.
- [x] Check current VM state, disk/model inputs, aggregate budget and STOP limit; restart only within approved bounds.
- [x] Run retained three-page slice, verify proposals/provenance and resource rate, then expand to 10 and 100 within the same approved limits. Report revised runtime before expanding if measurements differ materially.
- [x] Save all candidate/stop scores and direction-specific proposals, transfer and verify results, stop the VM. On a cap, save progress and report remaining work; do not claim completion.

### 5. Compare and report — independent reviewer plus root; depends on task 4
- [x] Report counts by direction, type and old/new cohort: source removals, type removals, unknown retained, exact changes, offered groups, selected proposals, stop decisions and no-compatible-QID cases.
- [x] Compare common proposals, direction disagreements, multiple-QID possibilities and source-supported examples. Selection rate is not accuracy.
- [x] Preserve current assignments and list possible previous assignments affected by the new filters; do not silently remove them.
- [x] Review targeted diff, commit only relevant code/docs, report local backup status. No push without standing permission.

## Estimate and checkpoints

First diagnostic's provisional type-only score counts, before source exclusions (candidate scores plus one stop per group); the two implementations are not yet reconciled:

| Daniel type | Groups | Before | After |
| --- | ---: | ---: | ---: |
| LOC | 3,063 | 735,380 | 412,747 |
| PER | 1,527 | 298,180 | 57,082 |
| MISC | 2,153 | 398,975 | 398,975 |
| ORG | 2,273 | 357,852 | 140,223 |
| Total | 9,016 | 1,790,387 | 1,009,027 |

All groups retain candidates in this type-only check. There are 133,588 candidate pairs retained because type evidence is incomplete. Groups containing prior-eligible occurrences: 3,856, scoring 731,578 -> 413,688. Newly-admitted-only groups: 5,160, scoring 1,058,809 -> 595,339. These group cohorts partition 9,016; occurrence cohorts remain 5,852 and 7,277 because 386 groups contain both kinds of occurrence.

Second diagnostic: corrected inventory-P31 plus cached-P279 gives type-only 1,004,481 and source-plus-type 967,222 (958,206 candidates plus 9,016 stops). It retains 99,666 unknown-type pairs after source filtering. Neither result is final until shared-predicate tests reconcile the 4,546 type-only difference. An earlier 1,038,805 combined result is withdrawn: it incorrectly started from older cached P31. No inference was based on any diagnostic. Next task is one reproducible predicate with per-pair reasons; report the exact difference rather than select a convenient number.

Time basis: total elapsed execution hours, including current preflight; approval_wait and environment_wait excluded. Active work is tracked separately and remains unknown unless measured.

Shared Superpowers breakdown supplied to Epoch: preflight 15 min; implementation/tests 45–80 min; scoring 30–65 min; verification/report 20–35 min. Parallel evidence and test review; integration/scoring are dependent and GPU has one owner. Proposed total range **2–4 hours**. This is model-derived, not a calibrated confidence interval. GPU estimate uses the previous measured 410 pairs/sec only as a reference; current reverse throughput is unmeasured.

Epoch invoked once for this scope: PERT optimistic 2 h, most likely 3 h, pessimistic 4 h; expected 3 h; estimate ID `3988c3d5-f114-4992-868c-ac9378db4a4f`. Its displayed calibration fields conflict with each other, so they are not used. Scope, dependencies, units and execution-time basis agree with the breakdown above; no second iteration is needed unless the completed source count changes them.

Preflight started 2026-10-30 02:56:25 Asia/Jerusalem (UTC+02); local check checkpoint 03:05. Implementation requires OWNER duration approval. After approval: first checkpoint ten minutes later; regular reports identify completed work, next step, uncertainty, resource consumption and waits. Read this state after compaction; do not repeat completed preflight.

## State

COMPLETED EXPERIMENTAL, corrected scope executed and verified. See final report for identity conflicts and limits. Pre-existing unrelated working-tree changes are preserved. Root owns plan, integration, experiment runner and GPU; worker A owns shared inventory/type filter and tests; worker B owns exact/candidate/final-validator wiring and tests; independent reader owns count reconciliation/review. Disjoint implementation files permit parallel work per OWNER's explicit parallelism request.

Execution estimate version 2: Epoch `1cf52ee8-52f2-4f78-98e9-ecf68e6a404e`, 2/3/4 elapsed hours O/M/P. Same task breakdown/dependencies/time basis as above, corrected populations and sequential forward-to-reverse dependency. The scope and basis agree; calibration fields are not used. First absolute checkpoint 2026-10-30 03:21 Asia/Jerusalem. Track approval_wait separately; active_work remains unknown unless measured. Ruling: reuse existing isolated worktree and this tracked plan as the ledger; no new tracker or framework.


### Execution checkpoint 2026-10-30 03:34 Asia/Jerusalem

- Shared inventory written and independently checked: 13,470 input rows; 12,871 retained; 599 excluded; 1,208 retained rows have incomplete native-type ancestry. Original rows and assignments remain unchanged.
- Count reconciliation: 29 empty-English-label rows have saved title fallbacks. Dropping these explained exactly 4,546 provisional scores. Final code also correctly treats metadata `missing:true` as incomplete evidence; old provisional totals are not final totals.
- Frozen populations: 7,277 forward occurrences, 5,852 previous unresolved. Forward has 5,546 groups and 367,361 compatible candidate pairs; 10,644 nonempty questions add 10,644 stops, for 378,005 actual scores. All groups have exposure. Worst-case reverse if every forward occurrence fails: 978,727 candidate-plus-stop scores. Actual reverse population depends on forward results.
- Focused runner/integration verification: 60 tests pass. Independent static review cleared launch blockers. Existing worker suites also passed (433 pilot tests and 94 caller tests; overlapping suites, not additive totals).
- Run checks now bind exact revision scopes, formatting helpers, tokenizer vocabulary/BPE/backend assets, package versions and full derived job texts. Orphan scores fail. Runtime history is append-only; aggregate cloud limits belong to the root launcher and VM STOP guard.
- Two L4 starts failed with ZONE_RESOURCE_POOL_EXHAUSTED_WITH_DETAILS; third request issued. Existing VM only. No alternative VM authorized. Capacity wait is environment_wait, not active_work.
- Three-page CPU stage started 03:31 while waiting: 85 forward plus 67 previous occurrences. Fixed checkpoint, no training, no cloud cost. Output scope_3_cpu; 900-second local execution cap. Full 100-page run still pending.
- Existing saved-link audit: 1,489 of 9,833 distinct occurrence/QID/type links would fail new policy (74 source exclusions; 1,415 type conflicts), across 1,213 occurrences. These are policy conflicts, not verified identity errors. Do not change assignments. 469 affected occurrences also have a passing saved link; 744 have only failing links.
- Review found a downstream Event bypass beyond this proposal-only run. Add a minimal article-bound assembly guard and make Event article evidence consume the same scoped inventory. Disjoint owners: worker B post_qid_run + its test; worker A post_qid_events + its test. Interface scoped_qid_inventory={path,sha256,policy_version}. Root integrates. Dependencies: shared inventory -> core binding -> Event evidence -> final assembly; GPU scoring independent.
- Incremental Event guard estimate: 8-15 elapsed execution minutes, in parallel with capacity wait/CPU smoke. Epoch PERT 0.13/0.20/0.25 hours, expected0.20h, feedbackRef ccfa1910-ec8c-4e0a-87c9-261aa1fccc18. Model-derived, no empirical calibration. Same approved filter-throughout objective; total approved 2-4h unchanged. Workers checkpoint03:45. Next root status03:40.
- active_work unknown; elapsed execution and environment_wait are recorded by timestamps, not invented active hours. No model acceptance count is an accuracy result.


### Execution checkpoint 2026-10-30 03:52 Asia/Jerusalem

- Third existing-VM start succeeded. Verified lastStartTimestamp 2026-10-30 03:33:03.660 Asia/Jerusalem. 5400-second STOP guard remains set; root owns the sole VM. Conservative budget gate passes, actual billing unknown.
- Payload SHA256 verified remotely; fixed checkpoint SHA256 matches approved full_best.pt. Missing runtime imports found before scoring: installed PyArrow23.0.1, mwparserfromhell0.7.2, pandas2.3.3, beautifulsoup4.14.3 in the existing task venv. No training or model changes.
- Three-page GPU stage complete: forward35/85 occurrences; reverse93/117; 24 still unselected. All13 transferred file hashes checked. Ten-page stage complete: forward326/725; reverse702/866; 164 still unselected. All13 hashes checked; three-page proposals agree exactly within ten-page output.
- Reverse source audit found2 agreements and4 conflicts in six selected traceable cases. Urakaze/Hizen/Pacific had correct source QIDs offered yet lost. Kumano correctQID blocked by ORG type rule. This selected subset is not accuracy. No proposals are promoted; continue approved full100 measurement as experimental only.
- CPU three-page check reached900-second cap (actual902.094s) during reverse. Forward124questions complete, reverse44 complete. CPU/GPU forward choices differ in1/124questions; reverse differs in3/43commonquestions. Retain partialCPU evidence, do not claimCPUstagecomplete. BF16/float32 sensitivity noted, no threshold changes.
- A report/restart writer defect found on actual three-page replay was fixed: identical derived records are kept, changed ones rejected. Resume test passes; final GPU10/100 use corrected runner. Oldthreepage receipts/source hashes retained.
- Full100 GPU stage started after ten-page verification. Scope100 input7277forward+5852old. Rootresourcegate cap3946s available; passed3900s, leaving at least600s for transfer/STOP. No reverse scoring starts until allnewforward decisions complete.
- Complete affected-subsystem check: `pytest --import-mode=importlib GG_Data/entity_resolution/hundred_page_pilot GG_Data/pipeline -q`:902passed in37.71s. Default combined collection hadduplicate test_pipeline module names; importlib mode resolves collection without deleting files or changing code. Ruff touchedfiles clean.
- Eventsourcefilter bypass closed and independently reviewed: corebindsinventoryandusedrevisions; bothEventpathsusesharedsourceinventory; assemblyrequiresarticleboundphaseandmatchedinventory/revisions. 13 invalidguardcases plus validcase; unknown/REVIEW/template/pageown retained. NoEventdata run inthisexperiment.
- Pool audit final: reverseupperbound1790387 ->1706546sourceonly ->978727source+type; removals83841source+727819type;144382unknown-typecandidatepairsretained. 29titlefallbackrowsremain. Forwardactual378005scores. Saved artifacts pool_counts.json, source_audit_3, prior_assignment_audit. No assignmentschanged.
- Nextcheckpoint04:00Asia/Jerusalem. Pending: full100 scoring, transferhashverification, finalcase/outcomecomparison, STOP confirmation, report. No addedcloudresource or spendingapproval requested.

### Verified correction and code checkpoint 2026-10-30 03:56 Asia/Jerusalem

- `qid_filter/summary.json` type_unknown_rows=1208 is across ALL input rows; retained unknown-type rows=1149, excluded unknown-type rows=59. The 03:34 statement that1208 were retained is corrected here. The retained-pair count144382 is unchanged.
- Root reviewed staged paths, diff checks and credential-pattern check; committed only relevant17code/test/plan files as3a90a0a. 902tests passed before checkpoint. No push. Pre-existing unrelated changes remain unstaged. Backup status:Local checkpoint only; ignored experiment data remain local.
- Prior-assignment audit field corrected to has_passing_saved_qid_for_occurrence. Counts unchanged:9833links,8344pass,1489fail across1213occurrences. Cases SHA25664db7453a1a9f6d68b608fefed986b72eeb9987890ea105ddfc9dcbfeb6691eb; summary3be57415cb72f156bc17e9fb3b5b88995fa03717eb1a636a8cc74462d7a8d6a0. Original sources and assignments unchanged.
- Forward100 active; next formal checkpoint04:10. Final transfer, full100 validation, STOP and final report pending. Independent report drafting and type-filter caveat audit run locally in parallel; no additional cloud resource.

### Checkpoint 2026-10-30 04:00 Asia/Jerusalem

- Scope100 forward exceeds8800/10644questions; reverse still waits on forward completion. No resourcecapreached.
- Typefilter audit confirms Kumano source row1470383 is original DanielORG, expectedQ1791961 sourceKEEP, nativeP31Q898771heavycruiser, categories[], type_unknownfalse. Complete cached41nodeancestry has noapprovedORGroot; this is typepolicy mismatch, notmissingmetadata. No policychanged.
- Forwardsourcecheck found Brooklynshipclassmentions selectingBrooklyncity and Yugoslavian selectingYugoslavia ratherthanKingdomofYugoslavia. Cases/hashreport pending; no generalaccuracyclaim. Bothdirectionsremainexperimental.
- 3a90a0a localcodecheckpoint saved. Next formalcheckpoint04:10. Pending:full100scores, transfer/hashchecks, casecomparison, STOP/budgetreceipt, finalreport/commit. Alloriginalassignmentsunchanged.

### Forward completion 2026-10-30 04:02 Asia/Jerusalem

- Scope100 forward complete10644nonemptyquestions. Reverseprepared10043occurrences,6789groups,688201candidate-plus-STOPscores. Thusforwardselected3086of7277distinctoccurrences and4191newfailures; reversepopulation=5852prior+4191newfailures exactly.
- Forwardaudit completed10traceablemodelselectedoccurrences:7sourceagreements,3conflicts; notrandomsample/notaccuracy. TwoBrooklynshipclasstargetQ929294candidatesremovedbyDanielLOCfilter, modelselectedcityQ18419. YugoslavianexpectedQ191077wasofferedbutQ36704selected. EarlierdescriptionofBrooklynmodelerrorclarified:filterlossprecededchoice. Savedsource_audit_forwardcases/summarywith33hashes; noassignmentschanged.
- Typecaveataudit savedtype_filter_caveats.jsonwith12hashes. Next:reversecompletion,verifiedtransfer,STOP,finalcomparison. Nextformalcheckpoint04:10.

### Checkpoint 2026-10-30 04:11 Asia/Jerusalem

- Forwardlocalcopy:3086distinctoccurrences,3613occurrence/QIDlinks,2453group/QIDpairs (2448model+5exact). 285occurrences have multipleQIDs; max18. Counts and top10multiple-QIDgroups savedforward_100_checkpoint. Fullfinalremotehashpending.
- Partial reverseprogress snapshot contains2243completegroups/294398scores of688201 total; finalcountsnotclaimed. DirectSCPofgrowingreverse_scores triggeredPuTTYpscp assertion actuallen<=len; a partiallocalcopy exists and is explicitlylabelledPARTIAL_PROGRESS_NOT_FINAL_OUTPUT. No input or remoterunchanged. Finaltransfer must use completed immutable outputs, ideally a stablearchive and SHA256. No retry ofactive-scorecopy.
- A separate read-only progress SSHcommand was rejectedlocally due WindowsCLIquoting; no remoteactionoccurred. Normal scoringSSHsession57278 continues.
- Nextformalcheckpoint04:20Asia/Jerusalem; resourcecapandSTOPguardunchanged. GPUactualbillingunknown. No assignschanged.

### Checkpoint 2026-10-30 04:20 Asia/Jerusalem

- Scope100 reverse exceeds6350/6789groups; finalcandidate-richpages~0.6s/group inlast200groups. Remaining~440groups plus stabletransfer/hashchecks, STOP, finalreport. Expectedcompletion04:30-04:40Asia/Jerusalem; nextcheckpoint04:30. Sameapproved2-4hscope and90minVMcap; no addedwork.
- Codeverification and savedsource/typeauditcomplete. Sourcechecks show forward/reverseidentityconflicts; no generalaccuracyclaim. No assignsortrainingchanged. Partialgrowing-scorecopyisnotfinalresult andmustnotbeusedforoutputverification.
- Parallelworkersfinished; rootsoleownerGPUsession57278. active_workunknown; wallclockruntime notcalledactivework. Actualbillingunknown.

### Verified completion checkpoint 2026-10-30 04:28 Asia/Jerusalem

- Scope100 complete1970.592s elapsed,03:47:45.932–04:20:36.524. Forward3086selectedof7277,4191newfailures. Reverseinput10043=5852prior+4191newfailures,6789groups,688201scores. Reverse7792selected,2251STOP,0emptycompatiblepools. Total10878distinctoccurrenceswithproposals,11405occurrence/QIDrecords. Selectionnotaccuracy; no assignmentschanged.
- Stablearchive33456143bytes SHA256d2267bc15b93cf24bf73ec336e545138308374d15dae563786b5311d02d8c43e. All13remote/localfilehashesverified. Forwardcheckpointbyteidentical. Localreportreplaypreservesall13files. Original13poolinputhashesunchanged. Savedtransfer/integrityreceipts.
- VMverifiedTERMINATED. Start03:33:03.660,stop04:23:47.593Asia/Jerusalem,3043.933seconds/50.73minnew; aggregate18871.944seconds/5.242h. ConservativeaggregateUS$7.3422,notbilling. LimitsUS$10,90newmin,6aggregatehpass. Automaticrestartfalse;existingdisk/VMretained,no deletion.
- Independentfinalreaderrehashedall13filesandcounted1066206scores. Correctedreportmetadataprovenance:11850retainedBigQueryrows snapshot2026-10-25 retrieved2026-10-28;943APIrows2026-10-29;78APIrowsretrieved2026-10-28withnullsnapshot. HistoricalarticleversiondoesnotprovehistoricalWikidatatype.
- Existingoldforwardscalarreuse0. Scoresrecomputedfornewcontexts/options/bindings. Staged3/10/100runsareseparateverificationoutputs,notadditivepopulations. Sourceaudits/CPUcomparisonremainbounded,notgeneralaccuracy.
- Pending:independentfullcohort/subsetoutcomeaudit,finalreportappend/localdoccommit. Nextcheckpoint04:30. Activework/approvalwait/environmentwaittotalsunknown; do notsendincompatibleEpochactual. VerifiedmodelruntimeandVMtimeareseparateelapsedmeasurements.


### Final outcome audit and handoff 2026-10-30 04:29 Asia/Jerusalem

- Outcome audit verifies all 19 input bindings and complete finite option/STOP coverage. Old cohort: 4,540 reverse proposals, 1,312 still unselected. New cohort: 3,086 forward plus 3,252 reverse proposals, 939 still unselected. Selected sets are disjoint. Full total: 10,878 distinct occurrences, 11,405 links, 2,251 still unselected.
- Distinct selected/remaining by type: LOC 3,769/912; MISC 3,448/93; ORG 2,284/787; PER 1,377/459. All 285 multiple-QID occurrences are forward, 527 extra links, maximum 18. Summary proposal_occurrences_by_type counts links; final audit/report provide distinct counts.
- Three-page 128 proposal links and ten-page 1,040 links exactly match full-run subsets. This is output consistency, not accuracy. Existing assignments remain unchanged. DATE/source exclusions unchanged.
- No remaining execution task. All outputs experimental. Source/type policy conflicts and model ranking errors remain research findings, not hidden failures. No retraining, paidBQ, collection, Geography or Event data run.
- Model-derived Epoch total estimate version2 was2–4h elapsed execution excluding approval/capacity waits. Resume03:10:58 to this handoff about78min wall time; preflight started02:56:25. Exact comparable active_work, approval_wait and environment_wait totals are unknown. Actual model and VM elapsed times are separately verified. Do not fabricate calibrated accuracy or incompatible actual feedback.
- Final report: docs/reports/2026-10-30-filtered-bidirectional-100-page.md. Root owns final documentation checkpoint. Code commit3a90a0a; no push. Backup status Local checkpoint only. Ignored local data are not Git-protected. Existing unrelated changes preserved.
