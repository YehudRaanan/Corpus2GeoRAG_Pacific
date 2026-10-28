# Native corpus graphs implementation plan and execution ledger

> Execute inline with Superpowers executing-plans. This file is the task state.

**Goal:** Build local graphs A (Wikipedia-linked Wikidata/EventKG native types) and B (Daniel name/entity_group), using the saved V3 page/revision assignments.

**Architecture:** Reuse saved Wikipedia parse evidence, the saved BigQuery Wikidata projection, EventKG 3.2 filtered source files, and existing request/evidence helpers. Build a binary entity/page incidence matrix and compute exact undirected shared-page counts with installed SciPy sparse multiplication. Export nodes, page/revision membership, partitioned Parquet edges, unresolved records and source evidence. Never map the two graphs' entities or types.

**Tech stack:** Existing Python, PyArrow, pandas, SciPy, requests, BeautifulSoup, pytest; no installation.

**Spec:** User-approved rules in this document, reflecting the current conversation.

## Binding rules

- Identity is exact entity name + source-native type. No case folding or alias merging of names. QIDs are metadata, not graph B matching keys.
- Graph B uses `word` + `entity_group`; preserve `subtype` as metadata.
- Graph A uses native Wikidata P31 QIDs and EventKG RDF types, not PER/LOC/ORG/MISC mappings. Keep all supplied direct types. Never substitute MISC for an unknown type.
- A obtains page presence from internal article hyperlinks in saved exact-revision HTML, plus each article heading. This is structured-link coverage, not a new NER extraction of unlinked words. Keep target title, anchor text, source page/revision, evidence path, identity/type source and dates.
- QID/title association is metadata retrieval, not alignment to Daniel's entities. Resolve redirects explicitly; ambiguous/missing association stays unresolved. Current Wikidata/EventKG snapshots do not imply types as of each historical article revision.
- Each edge weight is the count of distinct Wikipedia page IDs containing both endpoints. Union membership across the saved revisions of that page; never count revision IDs as additional pages. Record this union policy explicitly.
- Read the 309,864 existing rows for aggregation only. Do not repeat extraction or source-page matching. Input V3 SHA256 is 5378e8124979f04be6eca62a62a7f104fb2fdb88d5c0ba378ebf8d3db86f5bb7.
- Keep all 545 unresolved rows unchanged; exclude them from page weights. Keep their name/type nodes and identify unresolved-only isolates.
- Include EVENT in A only, as a native source type; do not infer or extract EVENT for B.
- Keep all EventKG source provenance available in the corpus subset. The old 53,857-QID WWII filter is insufficient; the completed official full-archive scan supplies final corpus coverage.
- No graph comparison, cloud infrastructure, paid queries, model inference, overwrite, deletion, push or merge. Cached BigQuery is preferred. No new chargeable query without explicit bounded-cost approval.

## Resources and approval

Owner for all tasks and mutable files/processes: /root. Existing isolated worktree D:/Projects/GeoAI-source-page-ids-20261026, branch data/native-corpus-graphs-20261028. Data under its ignored Data/external/native_corpus_graphs_20261028. Code under GG_Data/entity_resolution. Other worktrees remain untouched.

90–180 elapsed minutes approved explicitly by OWNER on 28/10/2026, after the duration request. Latest expected completion 04:15 Asia/Jerusalem UTC+02. First checkpoint 01:20, then 5–10 minutes; progress messages at most 60 seconds apart while actively working. Behavioral schedule, not a mechanical timer.

Ponytail full: reuse data and helpers; no frameworks or dependencies. Superpowers breakdown below was sent to Epoch twice (limit reached). Epoch refs b031bdc4-5e9f-4ae1-aff6-269d0309feb8 and af7541ae-986f-4b05-b8d5-19c5ffc15ff8 retain 1.5/2/3 elapsed-hour assumptions and task order. Agreement is about scope, units, dependencies and elapsed basis; do not present model ranges as calibrated P80. Active_work unmeasured; approval_wait unmeasured; measure request environment_wait separately where possible. Current start reference 28/10/2026 01:12 Asia/Jerusalem.

## Tasks and verification

### 1. Inputs and graph builder (owner /root, no dependency)

- [x] Locate immutable V3, validate recorded counts, available space and clean isolated branch.
- [x] Write failing checks for exact name/type identity, per-page deduplication across revisions, unresolved-only nodes, native multiple types, namespace/fragment link handling and wrong revision evidence.
- [x] Implement `native_corpus_graphs.py` using sparse products and partitioned Parquet.
- [x] Run focused pytest plus existing source-page tests, formatting and lint.
- Outcome: runnable builder passes deduplication and provenance checks.

### 2. Graph B (depends on 1, owner /root)

- [x] Aggregate V3 rows; export nodes, node_page_presence, node_revision_presence, edges and unchanged unresolved rows with source row index.
- [x] Verify 74,339 nodes, 147,548 node/page pairs, 43,449,334 page-pair contributions, 425 pages and 545 unresolved input rows. Reconcile every edge to independent page-set intersections.
- Outcome: full graph B files and verified statistics.

### 3. Reference collection and graph A (depends on 1, owner /root)

- [x] Index all saved parse responses by exact page/revision; fetch only missing revisions; preserve request evidence.
- [x] Collect article hyperlink titles/anchors; attach QIDs and native direct types from cached BigQuery and explicit API responses where needed. Keep unresolved targets and missing types as separate audit records.
- [x] Filter the full official EventKG archive to corpus QIDs, keeping all six native metadata sources and provenance. Save bounded endpoint failure evidence and explicit full-archive coverage per QID.
- [x] Export A graph using same page weighting and native labels/types, with EVENT only in A. Keep source-specific nodes and QID associations.
- Outcome: graph A artifacts plus explicit source coverage, version semantics and any exact external blocker.

### 4. Independent verification and handoff (depends on 2/3, owner /root)

- [x] Verify original/V3 hashes unchanged, graph denominators, edge counts and all membership/weight invariants; inspect final changed files.
- [x] Save manifest hashes, README, run summary and recovery metadata. Code/docs local checkpoint only; no push authorization requested unless needed at handoff.
- [x] Final review, focused reruns only for findings, report exact outputs, limits and backup state.

## Review focus

1. Two revisions of one page must count only once, including entities seen in different saved versions; document union semantics.
2. Same name with different type remains separate; same name/type with different QIDs follows the requested name/type identity and retains all QIDs as collision metadata.
3. Unknown QID/type and missing API/cache evidence must stay visible, not become invented nodes/types or an assertion of source absence.
4. Article links are not complete named-entity extraction; retain nonlinked coverage limitation and nonhistorical type snapshot dates.
5. EventKG global co-mention counts and explicit relation predicates must never be used as corpus/revision-specific page weights.

## Execution log

- Preflight: original worktree is dirty/diverged; no edits there. Existing source-page worktree is clean and isolated; created local graph branch.
- Input: 309,864 rows; 309,319 resolved; 545 unresolved; 425 pages; 571 revisions. B: 74,339 nodes; 147,548 memberships; 43,449,334 pair contributions. About 121 GB disk free, 22 GB RAM available.
- Cached BigQuery snapshot: bigquery-public-data.wikipedia.wikidata, captured 18/10/2026, 544,375 projected entities. Exact table metadata retained with source cache.
- Ruling: reuse the existing isolated worktree and append new files only, rather than copy large evidence into another checkout. Existing prior exports remain immutable.
- 01:17 Graph B built: 38,229,483 edges, weight sum 43,449,334, maximum weight 300, 116 unresolved-only isolates. Output approximately 79 MiB.
- 01:21 Independent packed-page-set verification passed for all 38,229,483 B edges; all 545 unresolved rows and original row indices unchanged. This is stronger than a sample-only check.
- 01:23 Exact revision collection completed: 571/571, zero failures; 279 cached responses reused, 292 new oldid parse calls; 385,425 link records, 79,367 distinct targets.
- 01:24 Review found cached-disambiguation and incomplete-cache absence checks. Both fixed with regression tests. Existing EventKG source manifests are complete. Added source graph/schema/VoID hashes.
- 01:27 Reference collection: 63,544 exact BigQuery title associations (disambiguation guard included); 15,823 remaining titles explicitly checked through Wikipedia. 1,819 missing Wikidata entities requested from the public API; collection in progress.
- 01:27 EventKG endpoint returned HTTP 500 during read-only investigation. To avoid the old 53,857-QID filter limit, download the official 7,807,417,165-byte EventKG 3.2 N-Quads archive from Zenodo, validate published MD5, and stream-filter native metadata in two passes. Four independent HTTP ranges at a time; retained archive plus ranges require less than 16 GB. No paid API, no installation, no source overwrite. Task 3 fallback estimate 30–90 additional elapsed minutes within the approved 90–180-minute total; active work remains unmeasured. Archive filter tests cover source ordering and failed range responses.
- Next status checkpoint: 01:30 28/10/2026 Asia/Jerusalem UTC+02. Graph B complete; A reference collection and archive transfer pending. No source-page matching rerun.
- 01:29 Wikidata collection finished: 71,098 corpus QIDs, all with saved metadata; 8,039 lack direct P31 and remain explicitly audited. Title statuses: 63,417 accepted BigQuery exact sitelinks, 15,764 explicit Wikipedia QIDs, 169 disambiguation targets, 14 no QID, 3 missing/non-article. Zero fetch failures. 1,819 new Wikidata entity records and 59 type-label requests completed.
- 01:30 checkpoint: B and all revision parsing complete. A waiting on EventKG transfer. Official archive download 6.9% at 01:29:21. Next checkpoint 01:40 Asia/Jerusalem. Review of fallback confirmed two-pass source ordering; added an archive rehash gate and selected-output hashes to prevent reuse after byte changes. Focused tests: 18 passed including existing source-page tests.
- 01:31 Local code checkpoint 6f041ff. No push; all graph data remains local and ignored. 59,035 corpus QIDs are outside the old EventKG filter; 12,063 are inside, so the full-archive fallback is necessary.
- 01:36 Download 24.1% at 01:35:43, no reported failures. The N-Quads parser successfully read all 811,820 existing filtered native metadata assertions across six sources; manifests passed. This is parser/cache verification, not a substitute for the new full corpus scan. Prepared independent A native-name/type/QID and revision-membership verification, native type-label retention, and a portable ZIP packager. These A/package steps have not run yet. Estimate and 01:40 checkpoint unchanged.
- 01:40 checkpoint: B, all 571 revision links, and all Wikidata metadata complete. EventKG archive transfer 34.4%; no errors. Remaining work is archive scan, A build, full verification and package. Revised remaining elapsed estimate 40–80 minutes, within the approved total. No scope change. Next checkpoint 01:50 28/10/2026 Asia/Jerusalem UTC+02. Root remains the sole resource owner; no active worker other than the archive downloader. Code checkpoint 80e4a60; data local only.
- 01:50 checkpoint: archive 56.7%, no reported errors; other completed work unchanged. Remaining elapsed estimate 30–60 minutes. Next checkpoint 02:00 28/10/2026 Asia/Jerusalem UTC+02. Two short clock waits returned late (114.2 and 87.9 seconds for 45-second requests); reported as soon as control returned. These waits do not provide a mechanically enforced reporting timer. Full archived global sources are about 216.7 GB uncompressed; a 1 GiB local decompression probe took 1.34 seconds, supporting the remaining estimate without a cloud run. Task definition unchanged.
- 01:51 Archive 63.6%. Simplified corpus filtering: first pass reads explicit QID assertions, second pass selects all six metadata sources by the resulting resource IDs. It no longer assumes entity assertions are contiguous. A new noncontiguous-label fixture failed under the old group filter and passed after the change; all 18 focused/existing tests pass. No additional archive pass or scope change.
- 02:00 checkpoint: archive 84.2%; estimate 20–45 remaining elapsed minutes; next checkpoint 02:10. Final read-only review found four validation/provenance gaps, all corrected before the full scan: sameAs must be the actual predicate and object URI; A verification checks the complete source-native assertion set plus each node's QID/source/resource/label sets; package verification counts and exact file hashes must agree; raw EventKG type-label evidence and original BigQuery projection are copied and indexed for portable provenance. Added targeted regression fixtures. The BigQuery file is provenance context, not additional graph scope.
- 02:01 All 38,229,483 B page-set intersections passed again and were bound to graph file hashes for packaging. This checked graph files only; no 309K mention matching or extraction was run. B original row/unresolved proof remains from the initial full verification. Archive 87.7%; no errors.
- 02:11 checkpoint (after resume): EventKG archive assembled and published MD5 verified; SHA256 9c8b9929182f6e6026d4834d98cac8a0c2d8c39853811d578d7de900ffca6845. Download plus assembly elapsed 2662.407 seconds, overlapping other work. Started two-pass corpus filter. Remaining estimate 15-35 elapsed minutes; next checkpoint 02:20 28/10/2026 Asia/Jerusalem UTC+02. Scope and owner unchanged; no paid queries or matching rerun.
- 02:20 checkpoint: archive identity scan is CPU-active but slower than estimated. Stdlib inspection shows a 4 MiB compressed stream buffer becomes a large decompressed remainder copied on each line-buffer read. Root owns a bounded two-minute read-only 16 MiB identical-content benchmark comparing this setting with the stdlib default before any fix. Remaining estimate 25-60 elapsed minutes; next checkpoint 02:30 Asia/Jerusalem. Scope unchanged, all graph inputs and completed B outputs remain immutable.
- 02:22 Bounded buffer probe confirmed identical 16,777,331 bytes / 85,285 lines / SHA256 0c61043e4a53129bf50bba136ab07f3d8d9091c2596d5111f400a0d5234b0272: 4 MiB compressed tar buffer took 35.875 seconds; stdlib default took 6.5 and 7.5 seconds. Removed the custom buffer size. All 11 native tests and Ruff pass. Confirmed process 38072 command and empty corpus output directory before stopping its read-only scan; no output was overwritten. Resume with a new log, existing verified archive, unchanged QID input, and same scope.
- 02:30 checkpoint: full identity pass completed at 02:29:05 with 53,416 explicit-QID EventKG resources (46,088 entity assertions, 7,328 event assertions). Second pass started at 02:29:08 and is saving all six native metadata sources. Remaining estimate 15-30 elapsed minutes; next checkpoint 02:40 Asia/Jerusalem. No scope change. The preceding buffer-fix log timestamp marked 02:22 is approximate; the verified corrected scan actually started at 02:21:16, first source at 02:21:26.
- 02:34 Full archive filtering completed at 02:34:04. All six required native metadata members found and selected-file hashes saved. Explicit-QID scope: 71,098 corpus QIDs checked, 53,416 found resources/QIDs, 17,682 absent from full event/entity identity scan. Loading selected native quads, then build A and verify every weight. No use of old WWII filter as coverage boundary.
- 02:40 checkpoint: full archive filter complete; selected N-Quads parser active, no reported error. Metadata parsing is CPU-bound (about 1.1 GB process memory at 02:39). A build, independent every-edge verification and package remain. Remaining estimate 15-30 elapsed minutes; next checkpoint 02:50 Asia/Jerusalem. Same approved scope and root ownership. Current elapsed since 01:12 reference is about 88 minutes; active work and approval wait remain unmeasured.
- 02:41 EventKG collection completed at 02:40:17: 1,638,717 source assertions, 53,416 found / 17,682 absent corpus QIDs; full official archive coverage true. Saved bounded endpoint probe HTTP 500 without automatic retry; archive is the successful fallback. A construction started after confirming a new graph_a output and available disk. No B rebuild.
- 02:44 Graph A built at 02:44:10: 323,100 nodes, 9,486 native types, 1,515,753,534 edges, weight sum 2,355,447,402, max weight 378; 1,106,751 node/page pairs over all 425 pages. 542,465 native name/type/QID/source assertions, 65,425 QIDs with typed nodes, 9,233 sem:Event name/type nodes, 1,976 name/type identities with multiple retained QIDs. Started independent A source/membership/every-edge verification. Graph B remains unchanged.
- 02:48 A verification completed at 02:48:16: all 1,515,753,534 edges independently checked, complete native assertion set and QID/source metadata checked, all 571 revisions and 425 pages supported; graph files SHA256-bound. Final read-only agent review found no blocking issue. Added explicit package disclosure of 5,673 linked QIDs without usable native type (audits retained), with no graph mutation. Latest 11 native tests, Ruff and Black checks pass. Packaging started; global archive/range copies remain local and outside corpus ZIP.
- 02:50 checkpoint: both graph verifications complete; corpus ZIP written (about 3.21 GB) and package integrity/hash checks still pending. Final package checks and local Git checkpoint remain; estimated 2-5 elapsed minutes, next checkpoint 02:55 Asia/Jerusalem. No scope change; no push; ignored data local only.
- 02:51 Final package complete: 2,052 ZIP files, 3,208,205,487 bytes, SHA256 8f29c6747d6a5a7eb29b0c2d3d1954a462d1b2f18fc9c1474f3f952b205e7996. ZIP CRC passed. Independent reading of every ZIP entry verified all 2,051 manifest SHA256 values and exact file inventory, input-copy hash and no-rerun/no-alignment flags. Both full graph weight proofs passed. Final README reviewed; 5,673 no-native-type QIDs explicitly disclosed. No required work remains apart from saving this closing local checkpoint and handoff.
- Actual basis: 99.2833 elapsed minutes through full package verification at 28/10/2026 02:51:17 Asia/Jerusalem UTC+02, from the documented approximate 01:12 start reference. Epoch actual recorded against final accepted estimate af7541ae-986f-4b05-b8d5-19c5ffc15ff8 with auto_wallclock provenance; first iteration superseded. Active_work and approval_wait unmeasured; archive transfer/assembly 2662.407 seconds overlapped work. Closing commit/handoff time excluded from that package-verification actual. Estimate was model-derived 90-180 elapsed minutes, not empirically calibrated P80. All processes started for graph work have completed or were explicitly stopped at the documented safe read-only boundary. Backup status: Local checkpoint only; ignored dataset/archive/ZIP remain local and unprotected on GitHub.
