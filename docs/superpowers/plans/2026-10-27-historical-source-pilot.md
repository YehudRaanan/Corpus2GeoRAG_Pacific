# Historical source pilot

Goal: test full copied passages against older Roosevelt and Oceania article revisions.
Owner: root, exclusive API and output owner. Started 27/10/2026 08:13:25 Asia/Jerusalem (UTC+02).
Approved scope: the proposed two-article pilot; no baseline edits, full-corpus run, installs, push, or cleanup.
Estimate v1: 10-18 elapsed minutes, model-derived PERT, reference 9408820b-dccb-40d7-9091-2d033184bdbc. Checkpoint 08:23; upper end 08:31:25.
Active work and environment wait not separately measured; approval wait zero after user instruction.

Reuse WikiClient, normalization, HTML rendering, matching, evidence serialization. No production code changes.
Ruling: execute the authorized research pilot inline; preserve the existing worktree and all baseline evidence. No additional implementation approval is needed for this bounded investigation.

- [x] Select the two previously documented changed passages; collect all unresolved passages on these two articles, including Roosevelt aliases.
- [x] Query latest revision at/before eight dates from October 2026 back to January 2023. Parse each distinct revision and compare full passages; cap at 40 API requests and 8 minutes execution. Save metadata, rendering, raw wikitext, full decisions and URLs separately.
- [x] Independently reconcile matches to raw rows, negative current-snapshot comparison, evidence identity, original hashes; record results and exact limitations.

Completed: 16 snapshots, 32 successful requests, 107 matched pairs / 71 distinct texts / 2,707 raw rows of 3,584 selected rows. Retrieval/matching process 130.890 seconds; summed request time 108.595 seconds. Full input and 2,138 baseline file hashes unchanged. Separate raw-row reconciliation and fresh read-only review passed. No Parquet changes or pending operations.

Delay record: next verified clock after user continuation was 09:12:17; substantial interruption was not separately timed. Reported the expired 08:23 checkpoint, then revised to 09:16 and 09:18. Wall-clock elapsed is not active work. No estimate reset or scope expansion. Report contains exact limitations and protection status.

Files: ignored Data/external/source_page_ids_history_pilot_20261027/ (script, evidence, results, verification); committed docs/SOURCE_PAGE_IDS_HISTORY_PILOT_2026-10-27.md.
Review focus: correct revision/page identity; complete passage rather than phrase match; count aliases without deduplication; no claim that sampled absence proves historical absence; no claim that matching revision proves extraction revision.
