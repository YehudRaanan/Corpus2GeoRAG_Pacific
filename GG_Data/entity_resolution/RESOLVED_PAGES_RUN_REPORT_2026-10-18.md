# All-type matching with resolved Wikipedia source pages

Completed **18 October 2026, 16:25 Asia/Jerusalem**. Run ID:
`matching-bec29744c3df8b2b7680`.

All **309,864 mentions**, from **428 source titles** and **34,893 paragraphs**,
were processed with the unchanged notebook rules. The run produced **9,555
automatic suggestions** and **300,309 unresolved results**. It adds **1,517
suggestions** to the original run. These are unvalidated suggestions, not
confirmed entity identities. The canonical graph was not changed.

## Before and after

| Measure | Original run | Resolved-page run |
|---|---:|---:|
| Raw mentions processed | 309,864 | 309,864 |
| Source titles with resolved page identity | 239 | 424 |
| Mentions with at least one candidate | 45,286 | 59,660 |
| Mention-candidate pairs | 195,118 | 220,638 |
| Automatic suggestions | 8,038 | 9,555 |
| Unresolved mentions | 301,826 | 300,309 |

All **8,038 original suggestions remain identical**. No original suggestion
was removed or replaced. All **192,220 mentions from the original 239 resolved
pages** have exactly the same candidate names, name scores, authority scores,
decisions, and suggested IDs. The 1,517 additional suggestions come from
previously unresolved source pages.

## Complete denominators by type

| Type | Raw mentions | With candidates | Suggested | Unresolved | Additional suggestions |
|---|---:|---:|---:|---:|---:|
| PER | 48,230 | 8,622 | 1,703 | 46,527 | 226 |
| LOC | 89,846 | 17,336 | 3,021 | 86,825 | 425 |
| ORG | 47,680 | 9,855 | 1,863 | 45,817 | 415 |
| MISC | 85,676 | 23,006 | 2,925 | 82,751 | 450 |
| DATE | 38,432 | 841 | 43 | 38,389 | 1 |
| **Total** | **309,864** | **59,660** | **9,555** | **300,309** | **1,517** |

## Why most mentions remain unresolved

| Reason | Mentions |
|---|---:|
| Source page remains unresolved | 768 |
| No name candidate in the resolved page's pool | 249,436 |
| Candidates exist but name/graph decision rules reject them | 50,105 |
| **Total unresolved** | **300,309** |

Resolving a source page makes its existing reference pool available; it does
not supply missing reference entities, names, types, or assertions. Of the 185
newly resolved source titles, 71 have no direct neighbours in the saved graph.
There are 77 such titles across all 424 resolved pages. Across all page pools,
9,410 distinct entity IDs occur, and 1,352 have no entity metadata in the
frozen Wikidata snapshot. Even where names exist, the strict page pool and
fixed similarity rules can exclude an appropriate candidate.

The earlier page-lookup failures are now mostly classified by the actual
matching outcome. The larger no-candidate count does not mean the rerun lost
earlier candidates: every result from the original resolved pages is identical.
These counts do not establish a defect in Daniel's raw extraction.

## What changed and what stayed fixed

The runner accepts the verified saved `page_map.json`, follows its resolved
identities, and rebuilds the page-plus-direct-incoming/outgoing candidate pools
from the same frozen graph. Names and explicit person types come from the same
saved Wikidata snapshot, including names needed by the additional page pools.
No fresh graph or Wikidata data was fetched for this matching run.

All five extraction types use the same unattended method: trigram Dice score
at least 0.35 for candidate retrieval, one outgoing graph expansion step,
20 HITS rounds, and a suggestion name score at least 0.80. Multiple candidates
also require a positive relative authority gap of at least 0.20. PER requires
saved P31=Q5; compatibility for other types remains assumed. DATE has no added
date parser or date ontology. There are no model calls, training labels,
manual selections, threshold changes, or newly created entities.

The known wrong film/year and division-number suggestions from the
[original run](ALL_TYPES_RUN_REPORT_2026-10-18.md) remain unchanged. This rerun
tests the page-identity improvement, not an accuracy improvement or a change
to the matching method. Unknown-entity handling remains open.

## Verification and artifacts

- Seven focused tests passed, including directed graph expansion, independent
  HITS matrix checks, fixed decision rules, page-map pools, missing metadata,
  inconsistent/duplicate identities, and Wikipedia title/redirect handling.
- Every output row was checked against Daniel's raw row and stable mention ID.
  Every candidate's page membership, saved name, exact similarity, person-type
  check, graph authority reference, and decision was rechecked.
- An independent comparison checked all 309,864 raw rows/IDs and proved exact
  result equality for the original 192,220 resolved-page mentions.
- The decompressed mapped graph is byte-for-byte identical to the original
  run. All frozen input/output hashes were checked. Every output from both
  earlier matching/candidate runs remains unchanged.

[Independent comparison](RESOLVED_PAGES_VERIFICATION_2026-10-18.json) ·
[Run manifest](runs/all_types_resolved_pages_v0.1.0_20261018/run_manifest.json) ·
[Full summary](runs/all_types_resolved_pages_v0.1.0_20261018/summary.json).

The new run directory also contains `mention_matches.jsonl.gz`,
`graph_contexts.jsonl.gz`, `mapped_graph.jsonl.gz`, `page_context.jsonl.gz`,
and `entity_metadata.jsonl.gz`. Use the new run's page/metadata files for
candidate evidence joins; do not join its added candidates to the old cache.

The pending request to Daniel for source URLs, page IDs, language/site, and
exact revision IDs remains recorded in the README. No message was sent.

Backup status: **Local checkpoint only** after the accompanying commit.
Original source/cache files under `Data/external/` remain ignored inputs.
