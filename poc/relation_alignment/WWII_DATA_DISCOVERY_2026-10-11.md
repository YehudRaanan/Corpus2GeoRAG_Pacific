# WWII source discovery: first local inventory

Status: preliminary, 11 October 2026. The EventKG V3.2 scan is still running.
This inventory uses only completed EventKG files. It describes available
relation data; it does not align predicates or import facts into the Pacific
graph.

## Frozen population and local sources

The Wikipedia World War II task force collection yielded **53,857 Wikidata
QIDs**. The local Wikidata snapshot contains all 53,857 requested item records.
This is the selected task force population, not a complete list of all WWII
items. The full WarSampo 2.1.0 archive is local. The earlier
[WarSampo–Wikidata audit](audit_2026-10-11/REPORT.md) inventoried 145 WarSampo
IRI-to-IRI predicates, but its cross-source pair check used a limited identity
crosswalk.

| Source | Current inventory | Interpretation |
| --- | ---: | --- |
| Wikidata item-valued statements on selected subjects | 573,273; 670 properties | Targets may be outside the selected QIDs. Counts include statements, not distinct endpoint pairs. |
| Wikidata statements with both endpoints in selected QIDs | 108,428; 274 properties | Candidate relation pairs for the selected population. This includes class and administrative properties. |
| EventKG resources mapped to selected QIDs | 38,517 | 2,467 events and 36,050 entities; no QID appears in both local maps. The other selected QIDs have no mapping in these files. |
| EventKG `sem:roleType` statements in completed relation files | 342,909 | Counts include source-specific named graphs and can repeat a relation. They are not distinct edges or verified alignments. |

Frequent Wikidata properties with both endpoints in the selected population
include `P607` (27,682 statements), `P361` (5,634), `P527` (2,402), and
`P710` (829). Frequency is a discovery aid, not evidence that these properties
have the same meaning as a WarSampo or EventKG predicate.

The completed EventKG relation files in this inventory are
`relations_events_other`, `relations_events_literals`, and
`relations_entities_temporal`. Their `sem:roleType` statements include 246,468
in EventKG's Wikidata named graph and 56,551 in its English DBpedia named
graph. The Wikidata graph uses Wikidata property IDs such as `P607`, so it is
source reuse, not independent confirmation. The English DBpedia graph has 146
observed role types, including `battle`, `commander`, and `usedInWar`; these
are candidates for cross-source mapping. Some other role types, such as
`strength`, point to literals and need separate attribute handling.

## Preliminary same-object overlap

For the two completed entity-valued reified relation files
(`relations_events_other` and `relations_entities_temporal`), 59,559 retained
EventKG relation groups had QIDs for both endpoints. Of these, 27,354 groups
had at least one role in a non-Wikidata named graph. The table counts distinct
directed QID pairs per candidate. A pair is counted once for a given role and
Wikidata property, even if multiple source statements use it.

| EventKG source and role | Wikidata property | Direction | Shared QID pairs | EventKG role pairs with both QIDs |
| --- | --- | --- | ---: | ---: |
| English DBpedia `battle` | `P607` | Same | 7,185 | 20,524 |
| English DBpedia `usedInWar` | `P607` | Same | 507 | 686 |
| YAGO `participatedIn` | `P710` | Reverse | 183 | 1,461 |
| English DBpedia `commander` | `P607` | Reverse | 320 | 3,732 |

These rows are **ranked candidates, not accepted mappings**. In particular,
`commander` and `P607` may connect the same conflict and person while describing
different roles. Review source definitions and endpoint types before using any
row as a type translation. EventKG's Wikidata named graph was excluded from
this overlap ranking because it repeats Wikidata property IDs.

## Next discovery step

When the remaining EventKG relation files finish, repeat the same-QID pair
count across them. Then add the verified WarSampo identity crosswalk, retain
each source graph, and review meanings, direction, and time attributes before
accepting a rule.
Counts from incomplete EventKG files must not enter a final coverage claim.

Local evidence: `Data/external/wwii_task_force/manifest.json`,
`wikidata_entities.jsonl.gz`, `wikidata_qids.txt`, completed EventKG
`manifest.json` and `part_*.nq.gz` files, and
`Data/external/warsampo/manifest.json`. The `Data/external/` directory is
ignored by Git.
