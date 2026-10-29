# QID matching and seven-table delivery: 3, 10, then 100 pages

> Implementation: use Superpowers subagent-driven-development or executing-plans. Root owns integration, GPU/cloud operations and the shared cost ledger. This document updates the previous chat plan; it does not start execution.

**Goal:** Complete a small end-to-end delivery, verify it, then expand using the same model and code.

**Architecture:** Reuse the existing hundred-page matching pipeline and native-data table pipeline. Use one entry file per component, ordinary functions, existing dependencies and necessary boundary checks. No new scheduler, framework or tracker.

**Spec:** This plan incorporates the OWNER's 29 October 2026 decisions in this session. The existing training/input specification is `2026-10-28-hundred-page-decision-pilot.md` in this directory. Existing ERD/S2T documents describe the old implementation; update their changed contracts before new population.

## 1. Fixed scope and rules

- Frozen input: the saved 100-page sample, 132 used revisions, 40,070 original mention rows and 7,350 passages. Verify counts and hashes from the input manifest before execution. Never replace difficult pages based on results.
- Nested deliveries: choose three pages by stable page-ID/hash order from the previously used ten-page sample; retain those ten and then the frozen 100. Confirm actual page-ID inclusion before starting. Keep every used revision for each page.
- OWNER confirmed Geography is last WITHIN the first three-page delivery. Complete its policy discussion, population and final checks before expanding to ten. Apply the agreed policy to later deliveries.
- Preserve all original mention fields and rows. Matching remains page-and-revision scoped. Linked QIDs only; no new extraction of unlinked names or dates.
- Exact acceptance: identical official name, only one Daniel type for that literal name, and only one QID with that official name on the same page/revision. Aliases/case folding are not exact acceptance.
- Remaining matching: same-page trigram retrieval, then a shared independent-option JEV-style scorer. One choice per decision, repeated for each QID until the stop sentence wins. A group can match several QIDs and a QID can match several groups.
- The stop sentence is exactly: `None of the remaining mention groups refers to this entity.` Stop wins ties. A stop does not revoke earlier accepted pairs.
- Candidate K is based on measured memory, coverage, throughput and remaining budget, not an invented architectural limit. Preserve the existing K=80 preparation where compatible; do not repeat completed experiments. Record excluded candidates. A stop only covers evaluated options.
- Final Entity identity is `(QID, Daniel type)`. DATE is an ordinary Entity type; native Wikidata classes remain separate.
- A mention with no accepted QID links to a provisional Entity shared dataset-wide by literal `(word, entity_group)`. A match elsewhere does not propagate to unresolved occurrences.
- Wikidata only for Event/Relation enrichment. Retain every Entity, including MISC, DATE and unresolved. No invented QID assertions for provisional entities.
- Events: native occurrence recognition plus links to at least two distinct matched corpus QIDs, after mapping/exclusions. No relevance gate. Endpoints are matched corpus QIDs plus selected Events; no recursive population expansion.
- Keep all valid in-scope relations. Existing relevance, MISC, date-preference and mutual-top-20 policies are audits only. Missing legacy measurements are `NOT_EVALUATED`, without a full-corpus recomputation.
- Store forward and derived reverse rows for non-self relations; one row for a self-link. Both directions share one source assertion identity. Independently sourced reverse assertions stay separate. No typed-node Cartesian product.

## 2. Seven-table contract

| Table | Row key and content |
|---|---|
| Wiki Pages | `(wiki_site, wiki_page_id, revision_id)`; title/language, revision time and URL, content hashes, source/retrieval evidence |
| Entities | `(entity_id, type)`; QID or stable dataset-namespaced provisional ID, official and observed names, native classes, resolution status and complete native-record provenance |
| Mentions | Stable `mention_id` from input identity and original row index; all original columns, source row lineage, exact page/revision FK |
| MentionEntityLinks | `(mention_id, entity_id, entity_type)`; valid FKs, accepted matching method, decision/evidence references and run identity |
| Events | Event QID; separate EVENT Entity row, source event data, dates/precision, recognition and inclusion evidence |
| Relations | Unique directed row ID; shared base assertion ID, QID endpoints, mapped predicate, dates/raw qualifiers, native statement identity, derived direction and source row link |
| Geography | LOC identity; geometry reference/hash, CRS and source metadata, uncertainty or unresolved reason |

Retain existing data-file formats, including geometry GeoParquet. Store Wikipedia revision provenance separately from Wikidata snapshot/retrieval provenance. A containing revision is evidence of matching text, not proof of Daniel's original extraction revision.

Count importance from unique original mention IDs per identity and distinct original source pages, not revision rows. Deduplicate mention/entity pairs across typed rows when calculating shared QID-level importance. Count relation evidence by base assertion ID, never by directed row count. Page co-occurrence counts remain separate from native factual assertions.

## 3. Task breakdown, ownership and acceptance

For every code task: add the smallest meaningful regression case, implement the minimal change, run the focused checks, review the output and create a local checkpoint. Do not stage unrelated user changes.

| Task | Owner/component | Dependencies | Work and measurable exit |
|---|---|---|---|
| P0 | Root: manifest/contract | Saved inputs | Verify nested page sets and source hashes; document new seven-table keys, policy/version and output paths. Original inputs remain unchanged. |
| M1 | Root: model readiness | Training completion evidence | Verify warmup stability, encoder tuning, selected checkpoint, hashes and final validation/held-out metrics. Produce pass/fail readiness metadata. |
| M2 | Matching owner: inference gate | M1 | Existing inference rejects absent/failed/stale readiness. Bind checkpoint, tokenizer/encoder revision, code/input schema, training manifest and stop definition. Focused test covers mismatched checkpoint and unfinished training. |
| D1 | Worker A: Wiki Pages | P0 | One entry file imports used revisions and their evidence. Unique triple keys; no unused recovery revisions promoted into the business table. |
| D2 | Worker C: candidate preparation | P0, saved QID collection | Reuse exact pairs and trigram jobs; retain all occurrence indices, revision scope, candidate exclusions and source hashes. No accepted learned assignment yet. |
| M3 | Root GPU operator: slice inference | M1, M2, D2 | Score active-slice options; run each QID's remove-and-select loop; save scores, pairs and stop traces. Every expected job completes once. Reuse unchanged pair scores; do not train again for each slice. |
| D3 | Worker A: Entity population | M3, exact-pair audit, E1 native-record branch | Build typed QID and provisional rows from accepted pairs only. Reuse complete native records; preserve explicit source-missing statuses rather than dropping identities. Candidate-only QIDs remain acquisition evidence. Shared provisional-ID logic lives here. |
| D4 | Worker C: Mentions and Links | D1, D3 | One component writes both tables. Original rows/values preserved; accepted pairs expanded to their original occurrences; unresolved rows linked; no duplicate links or broken FKs. |
| E1 | Worker B: native/Event acquisition | M3 accepted-pair QID inventory | Derive QIDs directly from accepted pairs, without waiting for Entity population. Reuse full records and compatible discovery evidence; fetch missing data. Release the native-record branch to D3 while Event discovery continues. Remove old MISC/relevance SQL and local retention gates. Record exact scope and snapshot completeness. |
| E2 | Worker B: Event population | E1, D3 | Apply native occurrence recognition and two-corpus-QID rule; write Events and EVENT Entity extension in a new stage directory. Base Entity rows stay unchanged. |
| R1 | Worker B: Relation population | D4, E2 | Retain all valid mapped in-scope source assertions, existing exact exclusions and raw temporal evidence. Unknown native predicates stay explicit, not silently discarded. |
| R2 | Worker B: direction/export compatibility | R1 | Store stable `base_id::REVERSE` rows with swapped endpoints and exact inverse lookup. Export stored rows once; disable second reverse generation under the new policy. |
| Q1 | Worker C, root review: controls/EDA | D1-D4, E2, R2 | Source-preservation, keys/FKs, lineage, population coverage, counts and relation-direction tests pass. Report uncertainty with full denominators. |
| G1 | Root + OWNER: Geography decision | First three-page Q1 | Explain current 45/30/15/7/3 ranking, zero-score selections, context and geometry evidence. Agree the rule here, without silently applying the old rule. Re-estimate only affected work if changed. |
| G2 | Geography component, one writer | G1, current LOC rows | Reuse existing geography preparation/acquisition/ranking/population. Each LOC, including provisional LOC, has geometry or an explicit unresolved reason. |
| Q2 | Root: completed delivery | G2 | Re-run full checks; publish seven-table bundle, manifest, EDA, runtime/problem/cost report and exact status. Only then start the next-size production run. |

Each component has one entry file and one writer. Reuse existing helpers in `prepare_pages`, `match`, `report`, `entities`, `event_population`, `event_model`, `relations`, `graph_export`, `geography_population` and the existing runner. Do not rewrite existing algorithms merely to reduce the visible file count. Mentions and its bridge share one entry file. Controls and packaging share one component. Existing mapping/exclusion assets remain authoritative and versioned.

## 4. Model readiness and inference rules

The model is JEV-inspired, not a proprietary JEV reproduction. Train one shared CLS scalar head over the pinned LUKE encoder, frozen warmup followed by encoder/head tuning as already approved.

Readiness requires:

1. Final training artifacts and a successful restore/finite-score check using the same inference loader.
2. Actual encoder optimizer updates; a benchmark or configured unfreeze alone is insufficient.
3. Proof that the SELECTED inference artifact contains tuned encoder weights. Current selection code can choose `frozen_best.pt`; if it does, stop the model-dependent branch and report the conflict. Do not silently select a different checkpoint or change the selection policy.
4. Validation-based checkpoint selection, held-out diagnostics, candidate coverage and the agreed 90% selection/90% stop-precision pilot targets reported with denominators. If targets fail, report them and obtain a disposition before promoting model decisions; no automatic new training or spend.
5. Hash-bound readiness metadata and tests for stop, many-to-many decisions, restart and stale inputs.

Technical readiness and demonstrated accuracy are separate statuses. The existing Daniel reference is positive-only; it cannot establish full Daniel precision or stop precision. Missing negative truth stays unknown. Do not report full-pilot 90% accuracy from supported-positive recovery alone.

Within each active slice: strict exact pairs -> same-page trigram options -> model inference/removal loop -> pair audit -> original-row export -> table population. Exact/candidate preparation may run before model readiness; learned accepted assignments may not.

Reuse one immutable checkpoint across 3, 10 and 100 pages. A changed checkpoint invalidates affected inference; do not mix model versions. Preserve the existing 100-page jobs manifest and complete its slice subsets. Unchanged pair scores can be reused with verified input/checkpoint identity even when the slice job-file hash changes.

## 5. Parallel resources and agile deliveries

Read-only local inventory on 29 October: 12 logical CPU processors, 39.6 GiB RAM total, 23.5 GiB available, 88.8 GiB free on D:. These values must be refreshed at execution start.

- Root plus three worker agents. Root owns cloud/GPU, shared cost ledger, final integration and stage promotion.
- Initial total local CPU budget: ten threads, at most three per worker and one for coordination. Include library/OpenMP/data-loader threads in that total. Reduce load if other work consumes resources; increase work only when measurements show spare capacity.
- One approved GPU: no competing trainers/inference processes. Finish training, verify readiness, then infer. CPU development, candidate preparation and source validation can proceed while training uses the GPU.
- Worker A: pages then entities. Worker B: native/Event/Relation logic. Worker C: matching integration, Mentions/Links and DQ. Worker C designs Q1 while dependencies are unfinished. Files and output directories have exclusive owners.
- Root owns API/BQ launch and spend decisions; workers prepare requests and inspect saved responses. Retain existing request limits and backoff. Avoid three separate full-source BQ scans: reuse proven complete compatible source supersets and recompute local scope selections.
- Keep resources busy with useful independent work; do not keep a GPU running without useful scheduled work. Do not add VMs or exceed the approved budget to increase utilisation.
- Development for later slices may proceed in parallel. Production population/inference expands only after the current slice's Q2 passes.

Deliveries:

1. **Three pages:** full matching, seven tables, EDA, Geography discussion/population and verified report.
2. **Ten pages:** extend the same run with the existing ten-page set; reuse completed work; repeat complete checks.
3. **One hundred pages:** extend to the frozen set; verify all 40,070 original rows and 132 revisions; complete final report.

Event eligibility, importance and page-based counts depend on scope. Recompute each slice from reusable native evidence, then recompute the complete 100-page population. Do not union slice Event selections and call them complete. Stage-specific counts are labelled 3, 10 or 100; do not compare different denominators as quality changes.

## 6. Checkpoints, verification and time basis

At every stage boundary and every 5-10 minutes during active work, root reports in simple language:

> **Scope and time:** active delivery, date/time in Asia/Jerusalem.
>
> **Finished:** artifact names and verified counts.
>
> **Running:** operation and completed/expected units, when measurable.
>
> **Next:** next result and its dependency.
>
> **Problems or doubts:** evidence, impact and any required decision; write none if none.
>
> **Time and cost:** measured runtime, estimated/verified spend, remaining estimate and next absolute checkpoint.

Distinguish code ready, model ready, inference complete and data verified. If a call remains pending, say so; do not claim its outcome or duplicate it. Stop only blocked actions and continue independent authorised work. These checkpoints are operating instructions, not a guaranteed background timer.

Record active work, automated runtime, approval wait and environment wait separately; unmeasured values remain unknown. Use the existing ledger/task state. Record problems, adaptations and reasons, not only successful durations.

Required regression cases include multiple revisions, multiple QIDs per mention, multiple types per QID, shared provisional identity across pages, DATE identities, duplicate evidence, early stop, missing job scores, stale readiness, missing native records, old filtered discovery cache rejection, outside-period/top-20-overflow retention, inverse/self/independent reverse statements, date conflicts, and unchanged original fields.

Preserve date precision and raw qualifiers. Ambiguous scalar dates remain explicit, not a reason to silently discard a relation. Existing record-specific assertion exclusions and changed-content checks remain in force. The Agent spatial date-filter gap remains open and outside this scope.

EDA covers full denominators by page/revision/type/status/method; many-to-many assignments; provisional identities; candidate coverage; Events/Relations/source coverage; missing metadata and dates; exclusions; geometry source/type/uncertainty. Keep geometry coverage separate from correct identity.

## 7. Estimates, cost and protection

Original post-QID plan: model-derived parallel elapsed estimate 8-28 hours, most-likely about 15 hours, with compatible cached sources. It excluded model training/inference and external waits; it is NOT an estimate for this expanded end-to-end process.

Changed implementation tasks, O/M/P active-work hours:

| Addition | Optimistic | Most likely | Pessimistic | Epoch raw PERT |
|---|---:|---:|---:|---:|
| Model readiness + inference integration | 1 | 2 | 3.5 | 2.08 |
| Nested deliveries + checkpoint integration | 0.5 | 1 | 2 | 1.08 |
| Total added task-hours | 1.5 | 3 | 5.5 | 3.16 |

Superpowers breakdown and Epoch use the same scope and hours basis. These are model-derived, not project-calibrated estimates. No display-only correction factor is used. Task-hours are not automatically additional elapsed hours because independent work can overlap.

Before committing an execution completion time, verify live training progress, final model evidence, active-slice inference throughput, missing native-source coverage, remaining GPU allowance and budget. Measure the first bounded inference batch and forecast remaining questions/pairs. State a revised total elapsed range and absolute checkpoint in Asia/Jerusalem. Obtain OWNER duration approval for any new substantive execution beyond existing authorisation; this planning update does not start that execution.

The existing pilot limit remains US$10 and at most six aggregate new GPU hours. Do not reset it per delivery. Count prior training, setup, BQ and inference. No new paid retrieval/retraining/model substitution is implied by this plan. Record missing-source estimates and request approval where outside the remaining authorised budget.

Use new versioned output directories and atomic stage completion. Do not overwrite previous outputs or user changes. Create reviewed local code/plan commits at milestones. No GitHub push is authorised; report `Local checkpoint only` after a commit and disclose ignored data/checkpoints separately.

## Review record

- Parallel read-only reviews: model readiness and agile/resource dependencies.
- Model readiness is NOT verified by this planning review. Local status was last verified at 07:36:34 Asia/Jerusalem on 29 October and records unfinished training/inference; remote state was not checked.
- OWNER confirmed Geography belongs last within the first three-page delivery.
- No training, inference, cloud mutation or data population was started by this update.

## Approved execution amendments, 29 October 2026

- OWNER approved using the three old titles present in the new frozen sample, then adding seven pages from the saved sample in its original order. The 100-page membership is unchanged. Three pages contain 535 original mentions and four used revisions; ten contain 3,785 mentions and 13 revisions; 100 contain 40,070 mentions and 132 revisions.
- The selected tuned checkpoint passed candidate selection, 551/608 (90.625%), but stop precision, 278/311 (89.389%), missed the 90% target. OWNER approved an experimental THREE-page run with this fixed model. Keep quality status failed, preserve all evidence, and do not extend this exception to ten or 100 pages or retrain without approval.
- Full-native BigQuery retrieval was dry-run only: the 1.56 TB estimate would cost approximately US$8.88 before free allowance, which is unverified. The query was not executed. The 32 missing corpus records were obtained with the Wikidata API; 22 whole cached records were reused. Per-record source, revision and retrieval metadata records this mixed temporal basis.
- Public SPARQL is a bounded alternative for incoming Event discovery; retain exact query/response bytes and failures. Include all native corpus outgoing targets locally, apply the accepted pinned occurrence class list, then verify full-record eligibility. Do not claim a common snapshot across old cache, API and SPARQL observations.

## Historical lookup recovery approval, 29 October 2026

OWNER approved using the last full original-QID record before each merge, with explicit revision metadata, for three redirected Event lookup IDs. Retain original QIDs and all failed acquisition evidence. The saved five-revision windows select Q7699410/revision2498684180 (2026-05-28T11:30:02Z), Q13107770/revision2421525115 (2025-10-25T00:06:01Z), and Q13196750/revision2453815519 (2026-01-11T01:31:14Z). Revision info fields are derived from MediaWiki revision metadata and labelled as such. This does not change Daniel assignments or establish a common snapshot.

Geography remains discussion-only. OWNER requested discussion of sufficient evidence before deciding. The proposed same-place acceptance rule is not yet approved; no geometry population is authorised.

## Approved Event boundary refinement, 29 October 2026

OWNER chose to require presence in a saved article revision for added Events. Preserve all existing matched corpus QIDs. An added Event must have RAW_DIRECT_LINK evidence on an exact revision used by the current slice, checked against its saved wikitext and collection output hash. Page-own presence alone does not add an Event outside the matched corpus. The existing native occurrence/type and at-least-two-corpus-QID rules remain required; article presence is an additional condition. Rebuild closed-endpoint Relations after filtering. Keep the broad637-Event result separately for provenance. Current/cached title-to-QID mapping remains labelled as such; the linked text is revision-pinned, but the QID mapping is not a historical snapshot. No matching rerun or paid collection is needed.

On conflicting relations, preserve separate source assertions, raw qualifiers, revision/source metadata and dates; do not silently select one or combine evidence across versions. Generated reverse rows remain directions of the same assertion, not independent support. This discussion adds no new conflict-resolution scoring policy. Geography acceptance remains pending discussion.

## Verified three-page checkpoint after Event boundary refinement

Historical recovery is complete with original QIDs/revisions retained. The new article-bound stage retains11Events:9already accepted corpusQIDs and2added direct-linkedEvents (Q217145Guadalcanal campaign, Q263142BattleoftheJavaSea).626broadEvents are excluded. Recomputed Relations contain120sourceassertions and239stored/exporteddirectedrows, includingone selfassertion. Rawpresence, sourcehashes, closedendpoints andexportdirections passed independent checks.

Combined local tables contain4page/revisionrows on3pages,317typedEntityrows,535originalMentions,536bridges,11Events and239Relations. Geography and final acceptance remain pending. Experimental model quality status remainsfailed; source/DQcoverage does not establish matchingaccuracy. Rawlinks234total:191mappedQIDoccurrences,43unmapped. Current/cachedtitle-QIDmapping is not historicalidentityproof. Broadandnarrowversions bothremainavailable. No paidcollection/GPU restart was used for these changes.
