# Reference coverage correction

**Status: completed and verified.** All 309,864 mentions were rerun automatically
with the completed reference. There are **149,483 suggestions** and **160,381
unresolved mentions**. These are suggestions, not verified correct identities.
Earlier runs are preserved as historical trials.

## Confirmed defect

The mapped reference graph contains **144,990 Wikidata entity IDs**. The earlier
name cache had no metadata for **92,461** of them. Another **427** graph IDs had
metadata without an English label. It was therefore incorrect to interpret the
earlier unresolved count as a measurement of Daniel's extraction quality.

The name cache came from articles in `Category:World_War_II_task_force_articles`.
This population does not include every entity referenced by those articles or
by the other structured graph sources. The missing graph metadata included Q17
Japan, Q30 United States, Q183 Germany, and Q145 United Kingdom.

## Verified reference coverage

The reference completion finished at **18:11 Asia/Jerusalem on 18 October 2026**.
All 1,858 planned batches and all 92,888 target IDs were saved and checked.

| Coverage measure | Before | After |
|---|---:|---:|
| Graph IDs with metadata | 52,529 | **144,990** |
| Graph IDs with an English label or alias | 52,298 | **141,776** |
| Graph IDs without an English label or alias | 92,692 | **3,214** |
| Graph IDs without metadata | 92,461 | **0** |

The supplement contains 89,674 records with English names and 3,214 explicit
`NO_ENGLISH_NAME` records. Of its usable records, 196 already had an English
alias but no English label in the earlier snapshot. Thus it adds usable English
names for **89,478** previously unnamed graph IDs. No entity was reported missing
by the API. The 3,214 remaining name gaps are fully listed in the saved summary.

[Coverage summary](runs/graph_reference_v0.1.0_20261018/summary.json) ·
[Reference manifest](runs/graph_reference_v0.1.0_20261018/run_manifest.json).

## Correction and fixed scope

The reference completion requests every graph ID that lacks an English label:
**92,888 IDs**, in deterministic batches of at most 50. It uses the existing
frozen mapped graph to define the population, not Daniel's words or manually
selected examples. Existing entities with saved English labels are preserved.
No new graph entity or edge is created.

The supplement stores English labels, aliases, direct P31 types, Wikidata entity
revision IDs, original requested IDs, and canonical API IDs. Redirected IDs keep
their original graph ID; this step does not merge graph nodes. Explicit missing
entities and entities without English names get separate saved statuses.

Each batch records the request IDs, retrieval times, response size and original
response hash. To limit disk use, it saves the projected fields, rather than the
full API response. A response hash alone cannot reconstruct the full response.
The saved projected fields are sufficient to reproduce this matching input.
API fields follow the [official wbgetentities reference](https://www.wikidata.org/w/api.php?action=help&modules=wbgetentities).

Before matching, every planned batch and its hash must verify; every graph ID
must have an existing record or an explicit supplement record. A missing English
name is reported and never replaced by an invented label. The graph population
hash must agree with the actual graph loaded by the matcher.

## Rerun

```powershell
python GG_Data/entity_resolution/complete_graph_reference.py --output GG_Data/entity_resolution/runs/graph_reference_v0.1.0_20261018
python GG_Data/entity_resolution/run_notebook_matching.py --wide-search --page-map GG_Data/entity_resolution/runs/source_pages_v0.1.0_20261018/page_map.json --metadata-supplement GG_Data/entity_resolution/runs/graph_reference_v0.1.0_20261018/entity_metadata.jsonl.gz --output GG_Data/entity_resolution/runs/all_types_completed_reference_v0.2.1_20261018
```

The reference command can resume its own unfinished directory when its saved
request plan and inputs agree. Completed directories are not overwritten.

The matching run uses all **309,864 mentions** and all five extraction types.
The previous wide-search matching rules remain fixed: trigram name similarity
at least 0.80, explicit human P31=Q5 for PER, paragraph HITS ranking with 20
iterations and a 0.20 positive relative authority gap for multiple candidates.
LOC, ORG, MISC, and DATE type compatibility remains assumed. Dates, titles,
short names, and adjectives receive no new special rules in this correction.

Repeated mentions may link to the same reference ID any number of times.
Unknown-entity creation remains deferred. Suggestions are not promoted into
the canonical graph. A higher suggestion count is not an accuracy measurement.

## Completed matching results

The run finished at **18:51 Asia/Jerusalem on 18 October 2026**, with run ID
`matching-495d808b6158060973a4`. It processed all five types, all 428 source
pages, and all 34,893 source paragraphs. Source-page lookup remains unchanged:
424 resolved pages and four missing or invalid pages.

| Type | Input mentions | Previous wide-trial suggestions | Completed-reference suggestions | Still unresolved |
|---|---:|---:|---:|---:|
| DATE | 38,432 | 2,643 | 8,679 | 29,753 |
| LOC | 89,846 | 21,480 | 53,737 | 36,109 |
| MISC | 85,676 | 17,171 | 53,238 | 32,438 |
| ORG | 47,680 | 15,563 | 23,930 | 23,750 |
| PER | 48,230 | 7,065 | 9,899 | 38,331 |
| **Total** | **309,864** | **63,922** | **149,483** | **160,381** |

The net increase is **85,561 suggestions**. The before/after transitions are:

| Transition | Mentions |
|---|---:|
| Previously unresolved; now suggested | 94,772 |
| Same suggested ID | 40,592 |
| Changed suggested ID | 14,119 |
| Previous suggestion now unresolved | 9,211 |
| Still unresolved in both runs | 151,170 |
| **Total** | **309,864** |

More available names can create ambiguity or change the graph winner. Therefore
the number of additional suggestions is greater than the net increase.

Of the **160,381 unresolved mentions**, **113,041** have no candidate that passes
the current name and person-type rules. The other **47,340** have eligible
candidates but fail the graph separation rule. These counts do not show that
Daniel's extracted entities are wrong or absent from the real world.

The 144,990 graph IDs all have metadata. Separately, 71 source-page context IDs
outside the structured graph still lack metadata. They are not missing records
within the verified graph population.

[Run summary](runs/all_types_completed_reference_v0.2.1_20261018/summary.json) ·
[Run manifest](runs/all_types_completed_reference_v0.2.1_20261018/run_manifest.json) ·
[Full comparison](COMPLETED_REFERENCE_COMPARISON_2026-10-18.json).

## Real examples and remaining failures

These examples were inspected after the automatic run. They did not change any
decision or rule. The saved example artifact includes the original paragraph,
mention ID, row number, top candidates, scores, and target metadata.

| Source / paragraph Index | Mention | Current suggestion | Interpretation |
|---|---|---|---|
| 1943 Cairo Declaration / 0 | United States | Q30, United States | The restored country record is now available and selected. |
| Attack on Pearl Harbor / 10 | 1941 | Q5231, 1941 | Previously unresolved; now selects the year record. |
| 14th Indian Infantry Division / 2 | Japanese | Q5287, Japanese language | Wrong: the paragraph says the Japanese captured Rangoon; it does not refer to the language. |
| Air warfare of World War II / 15 | Roosevelt | Q33866, Theodore Roosevelt | Wrong: the same paragraph explicitly identifies Franklin D. Roosevelt. |
| Allied leaders of World War II / 40 | Germany | Q188, German language | Wrong: the paragraph refers to appeasement of Germany. |

The failures are not rare isolated reference gaps. All **9,485 suggested MISC
mentions exactly named Japanese** link to the language ID. All **1,148 suggested
PER mentions exactly named Roosevelt** link to Theodore Roosevelt. Their
correctness cannot be assumed; the inspected Roosevelt paragraph is clearly
wrong. Of the LOC mentions exactly named Germany, 107 link to the language ID.

All 837 PER mentions exactly named Hitler remain unresolved. The saved Adolf
Hitler record has no aliases, and the current literal name rule does not infer
surname aliases. Date ranges and titles also have no special normalization.

The next method change should address type compatibility and local paragraph
identity evidence before treating additional suggestions as correct matches.
No such change was made in this reference-only correction. Unknown-entity
handling remains an open issue.

[Saved examples and metadata](COMPLETED_REFERENCE_EXAMPLES_2026-10-18.json).

## Verification and backup

Ten focused tests pass, including missing-entity responses, redirects,
reference coverage, preservation of frozen named records, and the matching
rules. Black, isort, Ruff, and Git whitespace checks pass for the changed code.
The run rechecked every candidate and decision and verified that its inputs
remained unchanged. An independent streaming comparison checked all 309,864
rows: raw extraction fields, mention IDs, row numbers, and source-page results
are identical between the two runs. Both runs' output hashes were verified.
The decompressed mapped graphs are identical: 700,876 assertions, with the same
14 source-record exclusions. No relation mapping, graph entity, or edge changed.

There were zero manual match overrides, training labels, model calls, threshold
changes, or new entities. The reference-fetch step used the public Wikidata API;
the matching run used only the saved inputs and made no live lookups.

Backup status: **Local checkpoint only** for code and saved run artifacts.
No GitHub push has been made.
The original frozen inputs under `Data/external/` remain ignored by Git.
