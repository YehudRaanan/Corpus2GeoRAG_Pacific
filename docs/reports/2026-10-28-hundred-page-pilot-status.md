# 100-page pilot: prepared, GPU capacity blocked

Status checked: 28 October 2026, 23:56 Asia/Jerusalem (UTC+02).
This is a preparation checkpoint, not a completed model experiment.

## Verified results

| Item | Result |
|---|---:|
| New source Parquet rows | 2,235,432 |
| Selected original rows | 40,070 |
| Selected source pages | 100 |
| Distinct copied passages | 7,350 |
| Matched passages | 7,350 |
| Used saved revisions | 132 |
| Distinct linked QIDs | 4,522 |
| Page/revision/QID records | 12,371 |
| Direct raw-link occurrences | 17,443 |
| Page-own-QID occurrences | 132 |
| Daniel name/type groups per page/revision | 24,408 |
| Strict exact pairs | 3,456 |
| Remaining QID questions | 12,342 |
| Pair scores with up to 80 candidates per question | 778,389 |
| Pair scores with all available candidates | 4,588,995 |
| Frozen source-supported positive reference pairs | 4,301 |
| Combined CPU regression tests | 20 passed |

Original nine columns, original global row indices and raw span offsets were
verified unchanged. A passage can occur in more than one historical revision;
the recorded revision proves saved raw containment, not the original extraction
date. All used revisions have raw API evidence and verified timestamps.

Exact matching uses the owner's clarified rule: identical literal official
label, one Daniel type for that name and one QID with that label on the same
page/revision. Native Wikidata P31 classes remain separate. No guessed type
mapping, alias or case folding is used to accept exact pairs.

Linked entities and the page's own QID are included. Unlinked names/dates and
expanded template content are not newly extracted. Historical article text and
current/cached QID metadata have separate provenance. There are 16 distinct QIDs
without an English label, affecting 29 page/revision records; these remain
explicit and do not become fabricated model questions. Native metadata covers
all collected QIDs: 4,448 from BigQuery and 74 from Wikidata API.

## Training preparation

Pinned encoder: `studio-ousia/luke-base`, revision
`7438924defd9f3c2018d63c16073bf4bcb6a70aa`.
The existing CLS scalar head is reused. Encoder warmup is frozen first; encoder
tuning is required after the approved stability rule. No new GPU training has
run, and no CUDA throughput or memory result is available.

Corrected `training_k80_v2` preserves all original public source-page splits and
questions. It has 5,060 training, 607 validation and 608 held-out diagnostic
states, from 260, 32 and 33 source pages respectively. Pilot source IDs and
detectable copied text were excluded. Unique encoded pairs are 111,212 / 13,425 /
10,590. Two full training epochs require 450,358 state-pair evaluations.

Validation trigram retrieval at K=80 recovers 303 of 304 labelled positive groups.
This is candidate coverage, not model accuracy. K=80 is provisional until the
bounded GPU benchmark proves the complete workload fits the remaining allowance.
The largest available pilot pool has 1,907 groups. With K=80, 8,433 questions have
excluded groups, totalling 3,810,606 unevaluated query/group pairs. A stop decision
will apply only to its evaluated pool.

The 100-page reference was frozen before predictions. It contains complete
raw-link anchors at unique passage placements. It is positive-only and cannot
establish overall precision, stop precision or the 90% targets on Daniel's data.
Public labels are also incomplete; terminal states mean no labelled positive
remains, rather than exhaustive negative truth.

## Problems found and changes made

| Problem | Change and evidence |
|---|---|
| Self-closing `nowiki` consumed the rest of an article | Match self-closing protected tags first. Six collector tests and a full recomputation of 132 revisions passed. Recovered 99 link occurrences on Landing Ship, Tank revision 1379267177; no old links removed. |
| A fixed positive-removal order allowed premature stop with almost zero loss | Added deduplicated singleton-positive states while retaining original sequences. The collapse probe loss changes from approximately 0 to 5; every retained positive has a singleton state. |
| Memory benchmark omitted AdamW moments | Added one real isolated full-stage optimizer step before measurement. Actual CUDA verification remains pending. |
| Interrupted feature-cache write could block restart | Shared atomic temporary-file replacement keeps the previous complete artifact valid. Interrupted-write regression passed. |
| Old model output could attach to rows with changed revision IDs | Verify input hashes, canonical group identities, row tuples and query/candidate references before export. Stale-input regression passed. |
| Partial final score write could block resume | Preserve complete original bytes, then recover only the incomplete final record; reject malformed completed/interior records. Regression passed. |
| Resumed throughput mixed cached pairs with current invocation time | Separate new, cached and total pairs; record invocation times and mark unmeasured interrupted history unknown. Mocked restart regression passed. |
| GPU could not start | Three GCP operations completed with RESOURCE_POOL_EXHAUSTED. No model substitution or extra resource was started. |

Independent scoped reviews accepted the collection, training and matching fixes.
Ruff, Python 3.10 syntax checks and `git diff --check` passed. These checks do not
replace a live GPU run.

## Runtime and cost evidence

Preflight began at 23:00:54; execution approval was applied at 23:15 on 28 October,
Asia/Jerusalem. The last VM check was at 23:56. These are wall-clock points;
focused active work and approval wait were not independently measured. Parallel
stage durations must not be added as if they were serial elapsed time.

- Page preparation process time: at least 418.047 seconds across interrupted and
  resumed runs; exact first-stop time is unknown.
- Corrected collection rebuild: 33.484 seconds, four new API calls, zero failures.
- Candidate preparation: 109.891 seconds.
- GPU capacity attempts: 23:35:57, 23:40:52 and 23:55:04. All failed in
  `us-central1-c`; no new successful GPU start is recorded.
- BigQuery job `geoai_hundred_metadata_20261028_c5ca36bdb5e4b8cc3d11` billed
  13,723,762,688 bytes. Estimated scan charge is US$0.07801 using an assumed
  US$6.25/TiB rate, before any free allowance. This is not an invoice.
- New successful GPU runtime: zero. Existing retained disk cost remains outside
  this zero-compute statement; the pilot forecast reserves US$2 for other costs.
- Authorised new-task budget: US$10; aggregate new GPU ceiling: six hours.

The VM is verified `TERMINATED`, with automatic restart disabled, six-hour
maximum runtime and termination action `STOP`. Earlier GCP errors suggested
`us-central1-a`; the latest error no longer lists an available alternative zone.
Capacity in another zone is therefore not guaranteed. Approval to create and
later clean up a temporary copy is pending; none has been created.

## Files and restart point

Project: `D:/Projects/GeoAI-luke-pilot-20261028`.
Data: `Data/external/hundred_page_pilot_20261028`.

Use `collection_v2`, `training_k80_v2`, `matching_k80_v2` and
`source_link_reference_v2.jsonl`. The first versions remain unchanged for audit.
`pilot_status.json`, `runtime_cost_ledger.jsonl`, `vm_capacity_blocked.json` and
the individual stage manifests contain machine-readable status and hashes.

Next: obtain GPU capacity; run the isolated real-optimizer benchmark; confirm
candidate count and cost fit; train frozen warmup then encoder tuning; select by
validation; run the 100-page decisions; export matched/unresolved Parquet; report
metrics and cost; verify VM shutdown and local output copies. No trained pilot
checkpoint or final model-matched Parquet exists yet.

Code map and commands:
`GG_Data/entity_resolution/hundred_page_pilot/README.md`.
Upload bundle: `cloud_bundle_v2.tar.gz`, SHA256
`902ce02527dd8ec29c737953e551403ec9466620399a418c9f289e12867ee3c4`.

Backup: **Local checkpoint only**. Code fixes are committed as `f3ab2fb`.
Ignored data and checkpoints have no verified off-device backup. No push or
deletion was done. The pre-existing `luke_pilot/evaluate.py` user change remains
unstaged and untouched.
