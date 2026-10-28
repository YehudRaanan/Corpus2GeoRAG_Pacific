# Same-page cluster example implementation plan

> Execute inline with Superpowers executing-plans. Owner: /root for all files and processes.

**Goal:** Export two small, complete entity graphs from the same three saved Wikipedia pages and revisions.

**Design:** Reuse the existing node/page memberships, native metadata, sparse edge builder and independent verifier. Select the strongest three-page overlap among pages with 50–350 A nodes and 10–160 B nodes. Rank triples by the harmonic mean of their weakest pairwise Jaccard overlap in A and B. This is a deliberately cohesive example, not a representative sample. No cross-source entity matching occurs.

**Scope:** All native nodes on the selected pages; local weights count these pages only. Keep parent node IDs and parent-level counts clearly named. Restrict A QID/type/source arrays to QIDs linked on the selected pages. Reuse saved revision evidence. Export Parquet, CSV, GraphML, a page-overlap preview, report and checksum ZIP. No source retrieval, full edge scan/rebuild, raw mention processing, alignment, type mapping, deletion, overwrite or push.

**Resources:** Existing isolated branch data/native-corpus-graphs-20261028 at D:/Projects/GeoAI-source-page-ids-20261026, clean at start; about 99 GB free. Parent artifacts stay immutable. New outputs under ignored Data/external/same_page_cluster_20261028.

**Estimate:** 10/15/20 elapsed minutes, model-derived, start reference 28/10/2026 02:54:44 Asia/Jerusalem UTC+02. Superpowers tasks below and Epoch 307d434a-ce5d-49eb-ae58-92aeb01c0b0b use the same scope, dependency order and elapsed-hour inputs 1/6, 1/4, 1/3. Raw PERT point is 15 minutes. Generic reference-class and empirical interval displays are not adopted as a scoped estimate or a P80 claim. Active_work, approval_wait and environment_wait unmeasured. Checkpoint 03:05; upper completion 03:14:44. No new approval is required for this bounded local task under 20 minutes.

- [x] Inspect memberships and select pages (3–5 minutes; root; no dependency). Outcome: 20 candidate pages, 623 connected triples; top triple Cape Engaño (Luzon), San Bernardino Strait, Surigao Strait; 468 A nodes and 84 B nodes.
- [x] Export full same-page subsets using existing helpers (4–7 minutes; root; depends on selection). Outcome: both complete graph datasets with exact page/revision inventory and native provenance.
- [x] Verify every local edge, parent membership/identity fidelity, selected QID scope, GraphML/CSV round trips and package hashes; save preview/report/checkpoint (3–8 minutes; root; depends on exports). Outcome: downloadable checked example; local checkpoint only.

Review focus: prevent global page counts from becoming local weights; exclude non-selected revisions/pages; preserve exact native identity and parent node references; avoid parent-wide QID/source claims in the subset; state selection bias and preview semantics. Existing functional edge tests plus complete subset checks cover these risks.

Ruling: select and build directly within the user's requested example scope; no separate design approval for routine reversible choices. Native source types and the existing page-weight policy were already agreed. Retain all nodes in the exports; the preview shows page overlap, not a pruned entity graph. A and B need not have equal entity counts.

## Execution ledger

- 02:58 Selected triple is the highest scoring valid triple (score 0.0622222), with all three page pairs sharing native identities in both graphs. Parent membership tables suffice; the 1.5-billion-edge parent A dataset is not read.
- 03:03 Export complete: A 468 nodes / 70,245 edges; B 84 nodes / 1,782 edges. All 72,027 weights checked independently. Weight sums A 88,476 and B 1,836 match the per-page pair denominator. GraphML nodes and weighted edges round-trip exactly. Exact saved oldids: Cape Engaño 1380836780, San Bernardino 1366623426, Surigao 1366772287.
- 03:04 Additional read-only verification passed: reversed local node IDs reproduce every selected parent page/revision membership; selected revision pairs are identical in A and B; CSV edges equal Parquet; A native assertion subset and QID arrays are exact; all consumed parent input hashes remain unchanged. All 35 manifest entries match both disk and ZIP. ZIP 719,925 bytes, SHA256 ca229469797ccbeac5c79c82ece3b39d9e6a92fe895edef3d50ca36d18d6b867. PNG visually checked; circles are pages, not entity nodes.
- 03:04 Validation: 11 existing graph helper tests passed; ruff, black, isort and py_compile passed. Read-only final review assigned to existing native_graph_review agent; no shared resource mutation allowed. No full graph build, source retrieval or raw mention processing was run.
- 03:04 Final reviewer: no findings. Confirmed same page/revision scope, all local weights, native identity/QID scope, portable evidence and clear report limits. Validation completed in about 10 elapsed minutes, within the 10–20 minute estimate. Epoch actual recorded as auto_wallclock against estimate 307d434a-ce5d-49eb-ae58-92aeb01c0b0b; this is not focused effort. Active_work, approval_wait and environment_wait remain unmeasured. Handoff: local Git checkpoint for code/plan; ignored data ZIP remains local and unprotected by GitHub.
