# Reference coverage correction

**Status: reference completion verified; all-row matching in progress.** Earlier
runs are preserved as historical trials.

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

## Verification and backup

Ten focused tests pass, including missing-entity responses, redirects,
reference coverage, preservation of frozen named records, and the matching
rules. Black, isort, Ruff, and Git whitespace checks pass for the changed code.
All-row and before/after checks will be recorded after the run completes.

Backup status: **Local checkpoint only** for code. No GitHub push has been made.
The original frozen inputs under `Data/external/` remain ignored by Git.
