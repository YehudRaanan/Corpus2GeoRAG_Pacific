# One-time automatic matching: all Daniel extraction types

Completed **18 October 2026, 15:41 Asia/Jerusalem**. Run ID:
`matching-3ea16641deda7f74ed5e`.

All **309,864 raw mention rows**, from **428 pages** and **34,893 paragraphs**,
received a result. No type was deferred. The method produced **8,038 automatic
suggestions** and **301,826 unresolved results**. Suggestions are unvalidated
outputs, not confirmed identity links. The canonical graph was not changed.

## Complete denominators

| Daniel type | Input mentions | With candidates | Suggested | Unresolved |
|---|---:|---:|---:|---:|
| PER | 48,230 | 6,464 | 1,477 | 46,753 |
| LOC | 89,846 | 11,774 | 2,596 | 87,250 |
| ORG | 47,680 | 7,787 | 1,448 | 46,232 |
| MISC | 85,676 | 18,522 | 2,475 | 83,201 |
| DATE | 38,432 | 739 | 42 | 38,390 |
| **Total** | **309,864** | **45,286** | **8,038** | **301,826** |

There are **195,118 mention-candidate pairs**. Candidate coverage is 14.6% of
all raw mentions; suggestions cover 2.6%. These are coverage figures, not recall,
precision, or accuracy. Of the suggestions, 5,098 passed the single-candidate
name rule and 2,940 passed the multiple-candidate graph/name/gap rule.

The unresolved results are fully accounted for:

| Reason | Mentions |
|---|---:|
| Page absent from the saved identity snapshot | 117,644 |
| No name candidate in the resolved page pool | 146,934 |
| Name score or graph separation too weak | 37,248 |
| **Total unresolved** | **301,826** |

Page resolution remains **239 resolved / 428 pages**; **189 pages** are missing
from the snapshot. Every mention from those pages is retained as unresolved.

## Fixed unattended method

1. Verify Daniel's pinned upload, original graph inputs, and first-run page/name
   cache by SHA-256. The upload is from commit
   `43e35453421b032fc67d426d7d16fe436574b0fa`.
2. Use the page identity and direct incoming/outgoing neighbours as candidates.
   Compare saved English labels/aliases with normalized character-trigram Dice
   similarity, retaining scores at least **0.35**.
3. Combine candidates within each paragraph, add the page anchor, and expand
   **one outgoing graph step**. Keep real directed links; duplicate assertions
   contribute one HITS pair. Replay relation-map-v2.1.0 after restoring original
   endpoints and applying the **14 approved record exclusions**.
4. Run **20 HITS rounds** from equal initial weights. Rank by authority, then
   name similarity and deterministic entity ID order.
5. Apply the notebook's unchanged suggestion rule: name score at least **0.80**;
   for multiple candidates, also require a positive relative authority gap of
   at least **0.20**. Otherwise leave unresolved.

All five types use this route, including DATE. PER retains the notebook's
explicit saved `P31=Q5` person check. Type compatibility for LOC, ORG, MISC,
and DATE is **assumed**, following the agreed scope. DATE uses names and graph
context; this run does not add temporal parsing or a date ontology.

There were **zero training labels, model calls, live lookups, manual match
selections, threshold changes, or new entities**. Unknown-entity policy remains
open. The notebook and batch command share the same HITS and decision functions.

## Observed errors retained in the output

The fixed method has clear limitations. These results were inspected after
matching and were **not corrected, removed, or used to tune the run**.

| Source / Index | Raw mention | Automatic suggestion | Observation |
|---|---|---|---|
| Attack on Pearl Harbor / 10 | DATE `1941` | `Q207482`, *1941* | The paragraph says “By 1941, American planners…”. The saved entity is a **1979 film**, direct type `Q11424`. Exact name similarity 1.0 therefore produces a wrong identity when type is assumed. |
| 26th Indian Infantry Division / 3 | ORG `14th Indian Infantry Division` | `Q4632442`, *26th Indian Infantry Division* | The paragraph distinguishes the two divisions. The only candidate scores 0.9231 and passes the single-candidate rule despite the different division number. |

The first error's mention ID is
`mention-2420459041247c637f97ebcd8302f15b126c5e3d443c1782dd7780ffbdac0938`.
The second is
`mention-efdd3f360c543275a8af9c1e5e081d1d7887677a2a64b168a5db845e4fcdd051`.
The film ID is proposed for 22 DATE rows; this is not an accuracy estimate.
The observed errors show why software verification alone cannot validate these
suggestions for production use.

## Verification and files

- Five focused software tests passed, covering all five name-search groups,
  directed graph expansion, HITS against independent matrix updates, ties,
  weak winners, source aliases, and stable mention IDs.
- All nine notebook code cells executed. Against the original notebook, all
  eight example paragraphs and 16 person decisions retained the same results.
- Every saved raw row, mention ID, candidate name/score/page membership,
  person check, graph authority reference, and final decision was rechecked.
- An independent comparison confirmed unchanged candidate sets for **all
  271,432 non-date mentions** from the first run. DATE adds 820 candidate pairs.
- All frozen input/code hashes remained unchanged during execution. All four
  manifest output hashes were independently rechecked after completion.

[Run manifest](runs/all_types_notebook_v0.1.0_20261018/run_manifest.json) ·
[Full summary](runs/all_types_notebook_v0.1.0_20261018/summary.json) ·
[Independent checks and examples](ALL_TYPES_VERIFICATION_2026-10-18.json)

[All raw mentions, rankings, and decisions](runs/all_types_notebook_v0.1.0_20261018/mention_matches.jsonl.gz) ·
[HITS contexts](runs/all_types_notebook_v0.1.0_20261018/graph_contexts.jsonl.gz) ·
[Mapped assertion evidence](runs/all_types_notebook_v0.1.0_20261018/mapped_graph.jsonl.gz)

The mapped evidence contains **700,876 assertions** and **590,160 distinct
directed pairs**. It is a context snapshot for matching, not a promoted canonical
graph release. The manifest references the unchanged first-run page pools and
entity metadata, with exact hashes. Use the README for commands and joins.

Backup status: **Local checkpoint only**. The code, report, verification data,
and run outputs are committed locally; nothing was pushed in this task. The
large original snapshots under ignored `Data/external` are not in Git.
