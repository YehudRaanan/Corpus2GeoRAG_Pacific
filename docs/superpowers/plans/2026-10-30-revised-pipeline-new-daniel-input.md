# Revised Pipeline and New Daniel Input Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Implement tasks in order of dependencies, with exclusive file owners. Execution approved by OWNER on 30 October 2026; current status is recorded in the SDD progress ledger and versioned run status.

**Goal:** Implement the accepted six-stage pipeline and compare a new experimental run on the same saved 100 pages with the earlier results.

**Architecture:** Reuse the current isolated worktree and existing stage files. Preserve immutable input and old outputs; save each checked stage under a new run ID. Training remains separate. Use local table exports, not a new database or framework.

**Tech Stack:** Existing Python 3.12 environment, PyArrow, pytest, source-text-v3 cleaner and fixed LUKE decision checkpoint. No new dependency is planned.

**Spec:** `docs/superpowers/plans/2026-10-29-revised-entity-pipeline.md`, accepted by OWNER, and the request to update the code and run the latest Daniel file on the same 100 pages.

## Verified input and resource evidence

- Active worktree: `D:/Projects/GeoAI-luke-pilot-20261028`, branch `experiment/luke-decision-pilot-20261028`.
- New public input: `Data/georag_selected_v2_qid.parquet`, pinned repository commit `3124f58f2a170cc66087841ed1ade18271fe1bf8`, published 29 October 2026. Local copy: `Data/external/daniel_qid_input_20261029/georag_selected_v2_qid.parquet`.
- SHA256: `47141678ff0f67ef16c070b4beb58bb8b1273a1635d25fea875e241e48bdd006`; 63,002,540 bytes; 2,235,432 rows; nine original columns.
- Independent full-row comparison verified every column except `Source` equals the saved original input. `Source` changed from article title to page QID. It is neither a Wikipedia numeric page ID nor the mentioned entity's QID.
- The saved sample has exactly 40,070 unchanged occurrence rows, 100 Wikipedia page IDs and 132 saved revisions. New input adds no revision identifiers. Reuse saved revision evidence after hash checks; do not repeat full-corpus page matching.
- Receipt: `Data/external/daniel_qid_input_20261029/input_comparison_preflight.json`.
- Latest saved VM stop: 29 October 2026 16:03:36 Asia/Jerusalem. This is not live state verification. VM `geoai-luke-pilot-20261028`, project `geo-hagai-ndvi`, zone `us-central1-c`, one L4, g2-standard-4, 100GB boot disk.
- Saved aggregate VM runtime 13,233.644 seconds leaves 8,366.356 seconds (139.439 minutes) under the six-hour aggregate ceiling. The new run will use at most 90 minutes, with a corrected per-start STOP guard and no automatic restart.
- Saved compute/query estimate is $2.676334645 plus a $2 reserve. Actual remaining dollars are unknown: billing, disk, IP and transfer costs need verification. The aggregate OWNER budget remains $10, not $10 additional. No paid action if the cap cannot be supported conservatively.

## Global constraints and shared interfaces

- New run root: `Data/external/revised_pipeline_20261030/`. Never overwrite old baseline, corrected, cleaner or inference outputs. Exclusive writer for each stage directory.
- Preserve every original row and its nine source values. Keep new raw `Source` as supplied. Store readable `source_title` and page-QID metadata separately. Reuse frozen `source_row_index` for old/new comparison.
- Stable occurrence identity derives from the new input hash and global source row index. It must not change with cleaning or group-name repair. Across input versions compare by verified row lineage, not assumed identical occurrence IDs.
- Stage-2 rows carry `Text_clean`, `clean_start`, `clean_end`, `word_original`, the working `word`, cleaner/source policy and explicit eligibility/reason. Original text/offsets remain available. Do not pair cleaned offsets with original text.
- Eligibility requires verified page/revision, accepted source scope and usable mapped clean span. Excluded, review, page failure and deferred DATE remain distinct and cannot enter model inference.
- Exact matching uses an identical official name, one Daniel type for that name on that page/revision, and one QID for that label there. Retain the existing restriction against strict-exact promotion of repaired names. No alias or guessed type rule.
- Resolved entity identity is QID + Daniel type. Preserve many-to-many links. Within a QID loop remove only the selected group from that QID's candidates.
- Reuse existing same-page trigram candidate limits and protected source-supported candidates. No new graph blend, thresholds or model training. Save actual candidate counts and input format checks.
- Exact and decision matches are accepted processing outcomes, not independently verified truth. Stop text remains `None of the remaining mention groups refers to this entity.` Stop wins ties.
- Model checkpoint SHA256 `51246b874d6346bf2769077e0067f99f20cb28f6c7a09a02ee78f1c30a2fad20`. Training remains under `GG_Data/entity_resolution/decision_model/`. Use the same pair formatter and pinned tokenizer; perform a current restore/compatibility check and bind experimental approval to new jobs and run hashes.
- Public held-out diagnostics: 551/608 correct choices, 278/311 stop precision, 245/296 complete sets. Stop precision misses 90%; no claim of Daniel accuracy. A new experimental execution needs an explicit run-bound exception.
- Use cached article entities/native records first. Missing records may use bounded public API checks within the approved run; no paid BigQuery, new corpus extraction, Geography, retraining, database loading or full-corpus matching.
- Events must be linked in retained content of the saved revision. Keep raw link evidence for audit, but do not admit citations/navigation solely because a raw link exists. Relations remain directed with explicit provenance for derived inverses; require valid endpoints.
- Write pending mentions after cleaning; exact entities and links together after stage 3; model entities and links after stage 4; provisional identities only for eligible unmatched groups when stage 5 closes. Write Events/Relations after valid endpoint entities exist. All snapshots bind to one run manifest.

## Parallel tasks and exclusive ownership

Root owns shared contracts, integration, manifest, Git checkpoints, GPU/cloud access and final reporting. Three implementation workers may operate concurrently after the contract is agreed. Do not let separate workers share cloud state, files or output directories.

### Task A: Input, cleaning and candidate preparation

**Owner:** Worker A. **Depends on:** verified input receipt and shared fields above.

**Files:** `hundred_page_pilot/prepare_pages.py`, `prepare_candidates.py`, optional necessary cleaner adapter changes in `clean_source_text.py`; dedicated tests. Paths are under `GG_Data/entity_resolution/`.

- [x] Add focused failing checks for Source-QID input, frozen global row selection, unchanged raw fields and no duplicate supplied metadata columns.
- [x] Reuse the verified saved selection/revisions via an explicit new-input adapter; stop if occurrence lineage or revision evidence differs. No reselection by changed Source values.
- [x] Run the existing cleaner on the selected rows. Make candidate grouping consume the explicit cleaned view and common eligibility decision.
- [x] Expose strict exact matching as the meaningful stage `match_exact.py`, reusing the existing exact rule rather than copying it. Candidate preparation consumes exact pairs and creates only residual trigram jobs.
- [x] Preserve source-supported candidate evidence and original group lineage. Test literal uniqueness, repaired names, same revision, DATE/excluded/review blocking and clean-slice correctness.
- [x] Return the stage interfaces, tested fixtures and actual counts. Owner estimate: 40–70 minutes, model-derived.

### Task B: Mention/entity table write stages

**Owner:** Worker B. **Depends on:** shared fields; final integration consumes A's fixtures.

**Files:** `GG_Data/pipeline/post_qid_mentions.py`, `post_qid_entities.py`; dedicated tests.

- [x] Add focused checks for early pending rows, missing page/revision IDs, excluded/review states and zero invented provisional identities before finalization.
- [x] Adapt `populate`/`run` through minimal explicit stage/finalization arguments; retain compatible legacy behavior where tests require it.
- [x] Keep all original rows, working values and evidence. Commit consistent entity+bridge snapshots and preserve many-to-many links.
- [x] Create provisional identities only for final eligible unmatched groups. Validate stable occurrence IDs and all typed endpoint references.
- [x] Return tested fixtures and schema changes. Owner estimate: 35–65 minutes, model-derived.

### Task C: Article-bound enrichment and data checks

**Owner:** Worker C. **Depends on:** shared fields; final integration consumes B's fixtures.

**Files:** `GG_Data/pipeline/post_qid_events.py`, `post_qid_relations.py`, `post_qid_eda.py`; dedicated tests.

- [x] Test removal of hardcoded three-page assumptions using manifest-bounded 3/10/100 fixtures; do not remove the corpus boundary.
- [x] Reuse cached native records and article evidence. Separate raw inventory from retained-content link presence; retain historical Wikidata revisions for approved pre-merge identities.
- [x] Keep native relations directed and derived inverses explicit; reject missing endpoints and citation-only added Events.
- [x] Update data checks for legitimate missing page IDs and explicit raw-versus-working fields; retain strict unexplained integrity failures.
- [x] Return missing-cache evidence and tested enrichment functions. Owner estimate: 35–65 minutes, model-derived.

### Task D: Integration, readiness and comparative report

**Owner:** Root. **Depends on:** A/B/C for integration; independent manifest/tests can start first.

**Files:** `GG_Data/pipeline/post_qid_run.py`, `hundred_page_pilot/readiness.py`, `report.py`, integration tests and run documentation. Reuse `resolve_entities.py` unless a demonstrated integration defect requires a narrow fix owned by root.

- [x] Replace pinned old matching paths with explicit run-scoped stage inputs. Keep orchestration short and reuse stage callables.
- [x] Reuse the inference approval validator in the writer; do not implement conflicting quality exceptions. Do not mutate old archived receipts.
- [x] Save input, policies, checkpoint, jobs, code hashes and stage status. Fail stale-score reuse and inconsistent snapshots. Record runtime and issues per stage; keep active work separate from waits and mark unmeasured time unknown.
- [x] Preserve the old strict model-comparison function. Add a separately labelled workflow comparison that explains changed cleaning and eligibility, matched by verified source row lineage.
- [x] Run focused stage tests, combined affected tests/lint and pre-GPU synthetic integration plus real three-page pending/exact snapshots. The actual full three-page model delivery ran on CUDA and passed before ten-page expansion; it was not a pre-GPU real-model dry run.
- [x] Inspect live resource/budget evidence, install no new services, correct the STOP guard, and start only the existing approved VM after duration/quality approval. Root alone owns cloud actions.
- [x] Restore/check checkpoint and tokenizer, record input-format compatibility, run three pages end to end and check outputs. Continue to ten and then all hundred only after the preceding checks pass.
- [x] Limit total new running time to 90 minutes; reconcile aggregate runtime/cost and stop the VM in cleanup. If GPU availability or cost gate blocks inference, preserve completed local stages and report that exact blocker.
- [x] Save final tables, all-row status comparison, candidate/model evidence, enrichment coverage, examples and remaining uncertainty. Report changed eligible denominator separately from genuine matching gains.

Root implementation/check estimate: 30–50 minutes, partly concurrent. Combined implementation critical path: 75–125 minutes. Staged execution/report: 55–90 minutes; prior measured corrected 100-page inference was 2,414.496 seconds for 818,378 pair evaluations. Cleaner took 13.625 seconds. These do not guarantee current GPU speed or availability.

## Delivery and review gates

- [x] **Three pages:** same saved three retained pages; complete stages 1–6 and table integrity checks before expansion.
- [x] **Ten pages:** same saved ten-page scope; compare candidate/run signatures and status counts.
- [x] **Hundred pages:** all 40,070 original occurrence rows represented; no source exclusions hidden as matching improvements. Compare with saved original baseline (13,627 matched; 7,372 DATE; 19,071 entity unresolved) and corrected source-name run (14,588 matched; 7,372 DATE; 18,110 entity unresolved). These old counts are comparison references, not new-run predictions.
- [x] Independent review of affected code and saved outputs; focused failures fixed within scope. Do not run new experiments to improve metrics silently.
- [x] Local Git checkpoint after verified milestones, excluding unrelated pre-existing evaluate.py/report changes and ignored data. No push without standing permission. State local checkpoint status honestly.

## Estimate, approvals and checkpoints

Planning uses Ponytail full for reuse, Superpowers writing-plans and parallel task review, and Epoch PERT. Shared scope: the entire implementation and staged experimental comparison, including preflight, with elapsed hours as units. Approval and unavailable-environment waits are excluded; active work is not inferred from wall time.

First Epoch estimate excluded preflight in its component arithmetic. Estimate v2 corrects that: O/M/P **2.5/3.1/4 hours**, raw PERT expected **3.15 hours**, feedback reference `3ed801d7-6c26-4900-8267-7c2311db119a`. Superpowers task review found no remaining scope, dependency, unit or time-basis conflict. Stop after these two estimate iterations. Use the **2.5–4-hour model-derived range**; do not present tool confidence fields as empirical calibration for this workflow.

Preflight checkpoint: **30 October 2026 00:07 Asia/Jerusalem (UTC+02)**. Execution requires OWNER duration approval because the total exceeds twenty minutes. If approved near 00:05, expected completion is approximately 02:20–03:50 after allowing for preflight already spent; shift these times with actual approval wait. First execution checkpoint is ten minutes after approval; then report every 5–10 minutes and at each delivery gate. These are behavioral checkpoints, not a claimed background timer.

Approval must cover this fixed model's experimental 3/10/100 execution with new run-bound evidence and at most 90 new GPU minutes within the existing aggregate $10 and six-hour ceilings. No paid start until the budget/resource gate passes.

## Review focus

- A page QID in `Source` must not become a numeric Wikipedia page ID or an entity assignment.
- A cleaned-away citation must remain in the audit denominator but never create a provisional graph node.
- Candidate group identity changes must not detach original occurrence lineage or remove valid many-to-many links.
- Experimental readiness must bind to the actual new jobs; old approval and inference receipts cannot be reused as authority.
- Enrichment must obey retained saved-revision content and close all endpoints for the exact same run version.

## Execution close — 30 October 2026

All saved3/10/100 scopes completed; all40070 original rows retained. Final100:7387matched,5852eligibleunresolved,14980sourceexcluded,7918sourcereview,3933deferredDATE. Bothfinalworkflow comparisons passed lineage; corrected-run same-eligible matched7088→7387 (+421new/122lost). Structural/source/hash/typed-endpoint controls passed; scientific accuracy and optional Event/Relation semantics/completeness remain unevaluated. Three Japanese/MISC occurrences each received27QIDs and are explicit review cases, not silently changed.

VM verifiedTERMINATED:00:50:35.329→01:33:49.696Asia/Jerusalem,2594.367newseconds/15828.011aggregateseconds. Aggregate conservative estimate including$2reserve$6.50, actualbillingunknown. TemporaryVMapprovalunused; no temporary resources existed. No paidBQ/training/Geography/database load. Root final verification and63fresh focused tests passed. Report:docs/reports/2026-10-30-revised-pipeline-comparison.md.

Measured execution wallclock is recorded in status.json; full approved task basis includes unmeasured preflight and excluded waits, so full-task actual,activework,approvalwait and critical-path environmentwait remain unknown. No incompatible numeric actual was submitted to Epoch. Local Git checkpoint only; ignored run/model outputs remain unprotected on GitHub.
