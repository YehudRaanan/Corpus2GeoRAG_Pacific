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
- Keep all EventKG source provenance available in the corpus subset. Existing EventKG files were filtered to 53,857 WWII QIDs; do not claim coverage outside that scope without a successful source query.
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
- [x] Verify 74,339 nodes, 147,548 node/page pairs, 43,449,334 page-pair contributions, 425 pages and 545 unresolved input rows. Reconcile weights to sparse membership and sampled explicit page intersections.
- Outcome: full graph B files and verified statistics.

### 3. Reference collection and graph A (depends on 1, owner /root)

- [x] Index all saved parse responses by exact page/revision; fetch only missing revisions; preserve request evidence.
- [x] Collect article hyperlink titles/anchors; attach QIDs and native direct types from cached BigQuery and explicit API responses where needed. Keep unresolved targets and missing types as separate audit records.
- [ ] Filter cached EventKG resources/types/provenance to corpus QIDs and audit filter scope. Try corpus-scoped endpoint queries for out-of-cache coverage if available; save failure evidence and exact limits without silently treating missing cache entries as absent in EventKG.
- [ ] Export A graph using same page weighting and native labels/types, with EVENT only in A. Keep source-specific nodes and QID associations.
- Outcome: graph A artifacts plus explicit source coverage, version semantics and any exact external blocker.

### 4. Independent verification and handoff (depends on 2/3, owner /root)

- [ ] Verify original/V3 hashes unchanged, graph denominators, edge counts and all membership/weight invariants; inspect final changed files.
- [ ] Save manifest hashes, README, run summary and recovery metadata. Code/docs local checkpoint only; no push authorization requested unless needed at handoff.
- [ ] Final review, focused reruns only for findings, report exact outputs, limits and backup state.

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
