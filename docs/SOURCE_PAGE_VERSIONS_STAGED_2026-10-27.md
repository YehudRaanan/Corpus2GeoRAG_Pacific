# Staged Wikipedia revision Parquet versions — 27/10/2026

Created two separate local Parquets from the existing enriched baseline. No entity extraction, full-corpus matching, text rematching, or new historical search was run. The original raw Parquet was not reopened or reprocessed. Reading/copying the saved enriched rows was necessary to write and verify the new files.

| Output | Page-ID rows | Revision-metadata rows | Unresolved rows |
|---|---:|---:|---:|
| Existing baseline | 301,235 | 0 in Parquet | 8,629 |
| V1 historical recovery | 303,942 | 2,707 | 5,922 |
| V2 revision metadata | 303,942 | 303,942 | 5,922 |

Both new files retain **309,864 rows**, all nine original columns/values/duplicates/order/schema metadata, and all **301,235** previously accepted page IDs. Only the **2,707** previously null rows already verified in the historical pilot receive new page IDs. These rows represent 107 Source/Text pairs and 71 distinct passages; their complete metadata is identical between V1 and V2. The remaining unresolved denominator is **414 Source/Text pairs and 5,922 raw rows**.

## Files

Directory: `Data/external/source_page_versions_staged_20261027/`.

- `georag_selected_v2_full_n36335_r345732948_20261024_v1_historical_recovery.parquet` — 10,974,348 bytes; SHA-256 `4052c27dabfb53530a4a861a4319a915da5e43d6f2bc84cf3312856b80e28f30`.
- `georag_selected_v2_full_n36335_r345732948_20261024_v2_revision_metadata.parquet` — 11,030,677 bytes; SHA-256 `d511db45ae67f257ceb03fd87143b3d45f944d6085b15e438a06ed9b0ad2e20a`.
- `revision_metadata.json`, nine saved API responses, `summary.json`, `verification.json`, `remaining_unresolved_rows.csv`, `verify_staged.py`, `README.md`, `manifest.json`.

V1 is immutable. V2 adds revision metadata for the earlier accepted rows without changing IDs or the recovered rows' metadata. The baseline Parquet remains unchanged at SHA-256 `0b34290f0f74cc060dad325ca5fe32a9505acfe2ae84cca3dd0768ad2ec48cd1`.

## Metadata and evidence

Both versions add these typed columns: `wiki_page_title` (string), `wiki_revision_id` (int64), `wiki_revision_timestamp` (timestamp in UTC, microseconds), `wiki_revision_url` (permanent oldid URL), `wiki_match_method`, `wiki_match_status`, `wiki_revision_evidence`, `wiki_text_sha256`, `wiki_baseline_status` (strings). Each row has a status, text hash and prior decision status. Other values remain null where no accepted evidence exists.

V1 adds full metadata only on historical recovery rows. Its earlier accepted rows have status `BASELINE_PAGE_ID_METADATA_PENDING`. V2 fills those from the **34,254 saved accepted passage decisions and 425 distinct revision IDs**. Nine batched MediaWiki revision-metadata requests supplied revision timestamps and independently confirmed page/revision identity. All succeeded; summed request time was **3.969 seconds**. No repeated text search or matching call was made.

V2 statuses are `VERIFIED_HISTORICAL_SAVED_EVIDENCE` (2,707 rows), `VERIFIED_BASELINE_SAVED_EVIDENCE` (301,235 rows), and `UNRESOLVED_NOT_SEARCHED_IN_THIS_EXPORT` (5,922 rows). A saved matching revision is not proof of the extraction revision. Different paragraphs from an article can point to different matching versions. Baseline metadata retains the prior audited decision and evidence; it is not described as a newly repeated revision-rendering audit.

The evidence field points to the historical parsed API response, or to baseline page evidence plus the new revision metadata response. Baseline `page_evidence` paths are relative to `Data/external/source_page_ids_20261026/`; timestamp evidence and historical response paths are absolute local paths. Saved baseline decisions retain their complete source text and page/revision assignment. Keep all evidence directories with the output if moving the deliverable; the Parquet alone is not a complete evidence archive.

## Verification

- Fresh projection comparisons proved all original columns/metadata and row order unchanged.
- Every non-null baseline ID was preserved. Raw row-index reconciliation proved exactly 2,707 pilot rows changed null IDs and all other unresolved rows stayed null.
- Every recovered row, including all metadata, is equal between V1 and V2.
- Every backfilled revision ID, page ID, timestamp, title and match method reconciles with its saved decision and API metadata. No inferred timestamp or unknown revision was filled.
- All **2,138 baseline manifest files** and **38 pilot manifest files** passed hash checks. The exporter now enforces both manifests before reading saved decisions. A review found this missing guard; a failing regression test reproduced the gap, the guard was added, and it passed. Current inputs were independently verified unchanged; neither existing output was overwritten after the guard addition.
- **12** focused/regression checks passed. Ruff, Black and isort checks passed. Independent read-only review confirmed counts, raw preservation, V1/V2 identity preservation, and the evidence-guard fix; no material findings remain.

## Continuation and limits

This delivers the requested immediate staged starting files. It does not cancel or complete the earlier objective to search other historical revisions for the remaining **5,922 rows**. That work should use only the **414 unresolved Source/Text pairs**, existing caches and accepted revision evidence. Do not rerun extraction or matching on previously resolved rows. Save further results in another new output; never overwrite V1 or V2.

The pending broader historical search remains subject to explicit OWNER approval for tasks longer than 20 minutes. The earlier 90–180 minute proposal included broad revision verification of resolved rows and is superseded for metadata backfill by the completed cached procedure. A revised history-only estimate is recorded in the task plan before requesting approval. No remote push, model call, installation, graph rebuild, cleanup, or identity remapping occurred. The `what_happened_at` issue remains open and was not evaluated.

## Task record and protection

Started 27/10/2026 **22:18:52**, Asia/Jerusalem UTC+02. Model-derived estimate **8–18 elapsed minutes**, Epoch `230f2504-c512-4470-8f26-38175f9a47b4`. First checkpoint **22:28**. Root owns files, API and terminal; reviewer was read-only. V1 saved **22:21:30**; V2 saved **22:21:39**. Active work and environment wait not separately measured; approval wait zero for this authorized short staged export. Final elapsed duration is recorded at handoff, not as focused effort.

Code, tests, plan and report: **Local checkpoint only**. Ignored Parquets and evidence: **Unprotected** local files. No off-device backup was made or verified.
