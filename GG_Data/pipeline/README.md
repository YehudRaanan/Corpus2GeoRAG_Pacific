# Daniel pipeline POC

Contract order: [population S2T](../../docs/SOURCES_TO_ENTITY_DATA_MODEL_S2T.md),
[ERD](../../docs/ENTITY_DATA_MODEL_ERD.md), then
[model-to-graph S2T](../../docs/ENTITY_MODEL_TO_AGENT_GRAPH_S2T.md).

## Implemented first step

`poc.py` selects 10,000 original row positions without replacement (fixed seed
20261018), verifies pinned input and matching artifacts, and copies unchanged
saved matching decisions into Mentions. It retains resolved English/Japanese
Wiki Pages and failed page requests. Original text is evidence only; no text
extraction, rematching, splitting, combining, network request, or new identity
is performed. Synthetic rows retain their original IDs and use Daniel's type
when the saved resolved type is null. Saved type metadata stays unchanged.

Any unexpected count, field, source hash, ID, score, page conflict or missing
artifact raises an error. Stop and discuss the exact case with the user before
changing a rule. No automatic repair or retry is implemented.

**Output on D: was approved on 20 October 2026.** Step 1 ran successfully in
`outputs/poc_10k`. Do not rerun into that directory; existing output is protected.
The original invocation was:

```powershell
C:\Users\User\anaconda3\python.exe -B -m GG_Data.pipeline.poc --output D:\Projects\GeoAI\GG_Data\pipeline\outputs\poc_10k --output-approved
```

The output directory must be new; existing output is never overwritten. The
manifest marks only `STEP_1_ONLY`. Partial files without that manifest are not
a completed step. Its marker covers Mentions and Wiki Pages only. The separate
Entities step establishes membership for Wiki Pages `about_entity_id`. Events,
Relations, Geography, final graph export and Agent integration remain pending.
This is not a six-table release, a fresh matching run or a completed 10K POC.

### Verified first-run results — 20 October 2026

The run reused the completed matching decisions; these are sample counts, not
new matches or an accuracy estimate. The 10,000 sampled source positions are
recorded in `outputs/poc_10k/manifest.json`.

| Saved outcome | Mentions |
|---|---:|
| Page/direct Wikidata match | 7,429 |
| Already-matched pool | 215 |
| Fresh WWII pool | 48 |
| Normalized date | 952 |
| Existing unresolved synthetic ID | 1,356 |
| **Total** | **10,000** |

There are 7,692 QID-assigned mentions covering 4,712 distinct QIDs. The 1,356
synthetic mentions comprise 813 name-threshold failures, 175 type mismatches,
78 unknown types and 290 invalid/unsupported date values. These are preserved
baseline outcomes, not new failures introduced by table population.

The sample covers 419 source requests: 415 resolved and the four already-known
missing requests. Those four account for 29 mentions with null page keys.
Resolved requests deduplicate to 691 Wiki Pages rows: 404 English and 287
Japanese. Request counts and distinct page counts have different denominators.

Verification passed: every output hash, exact original raw rows and sampled
positions, unique mention/page keys, page foreign keys, distinct per-mention
synthetic IDs and separate NER/match scores. Output size is 23,087,187 bytes.
No new input or matching exception was raised. The completion marker remains
`STEP_1_ONLY`; later stages above have not run.

Resolution-manifest SHA-256:
`86e60c17a99d1aaecbd87dbda7c7d69a0dee8c41cd15d30c3393b13d164d2db4`.
Outputs are ignored data artifacts on D:, not protected by a code commit.

## Entities step

`entities.py` consumes the completed first step, without changing its files.
It populates one row per existing `(entity_id, entity_type)` pair and connects
Wiki Pages subjects only where an entity already exists. Normalized dates stay
in Mentions. There is no new extraction, rematching or type inference.

The user approved **newer saved Wikidata names** on 20 October 2026. English
still precedes Japanese, then Daniel's name. When saved labels differ, revision
IDs determine the newer supplied label; both source versions remain in
`raw_reference`. This rule changes display names only. Equal-revision conflicts,
missing revision evidence needed for a choice, and ambiguous Daniel fallbacks
stop the run before model output. For the two pinned cases Q132537 and Q1771928,
the user also approved older English labels where newer full records contain
only Japanese. Each selected name records `2026-10-20_KEEP_OLDER_ENGLISH`. Other
such missing-label cases still stop for discussion (population S2T section 6).

Complete native envelopes are reused from the verified saved archive. Missing
full records are retrieved as the complete BigQuery `item` field through the
existing GCP CLI wrapper and pinned matching snapshot. SQL, dry-run evidence,
job statistics and untouched results are cached in `outputs/wikidata_full_cache`.
The compact matching metadata remains separate evidence; it is not a complete
claims source. Labels, descriptions, native claims and unknown fields are
retained. Compact search names have unknown original kind/language and are
marked `matching_reference_name`, rather than presented as native aliases.

```powershell
C:\Users\User\anaconda3\python.exe -B -m GG_Data.pipeline.entities --output D:\Projects\GeoAI\GG_Data\pipeline\outputs\poc_10k_entities_approved
```

The destination must be new. `ENTITIES_STEP_ONLY` is written last, after source
and population checks; it does not mark Events, Relations, Geography, graph
export or Agent integration complete. Failed runs can retain acquisition cache
files for reuse, but do not produce a completed Entities manifest.

### First Entities attempt — stopped in final validation

The attempt created 6,077 candidate rows: 4,721 QID/type pairs (4,712 distinct
QIDs) and the unchanged 1,356 synthetic identities. All full Wikidata records
are available: 506 reused envelopes and 4,206 complete `item` records acquired
from the pinned BigQuery snapshot. The CLI verified 4,206 returned rows; query
job `geoai_1c8841ce530789458d059e9f8b92254f` billed 1,561,930,498,048 bytes.
Its result is cached; correcting names does not require another query.

Output hashes, exact ID/type membership, raw reference IDs and source hashes,
mention foreign keys, synthetic names/types, and unchanged first-step files
passed checks. The copied Wiki Pages view has 197 existing entity subjects;
its other values are unchanged. This structural validation does not establish
identity accuracy or approval of every display-name choice.

Final inspection found two cases not covered by the approved version rule:
Q132537 (`Robert Oppenheimer`) and Q1771928 (`Why We Fight`) have older English
labels, but their newer full records have Japanese labels and no English label.
The attempt used older English. Work stopped for a user decision between older
English priority and newer-record Japanese fallback. The code raises on
unapproved cases instead of choosing. The user subsequently approved the older
English labels for these two exact saved name/revision combinations. See
population S2T section 6 for values and revisions.

`outputs/poc_10k_entities/manifest.json` is now
`BLOCKED_NAME_LANGUAGE_VERSION_RULE`, with `entity_output_state=DRAFT_NOT_ACCEPTED`.
The original attempt marker is retained as `attempt_manifest.json` for audit;
it is superseded by the current manifest and is not a release marker. No later
stage was included in that attempt. The first-step output remains valid and
unchanged. The blocked attempt is retained for audit; the approved rerun uses
a separate destination and reuses the full-record cache.

### Approved Entities rerun — 20 October 2026

The user approved the two older English names. The separate rerun in
`outputs/poc_10k_entities_approved` completed as `ENTITIES_STEP_ONLY` and passed
`validation_report.json`: **6,077 Entities rows**, comprising **4,721 QID/type
pairs across 4,712 QIDs**, plus **1,356 unchanged synthetic IDs**. All 691 Wiki
Pages remain; 197 subjects reference existing sample entities.

The run reused the 506 archive records and 4,206 cached BigQuery records.
The BigQuery CLI method was blocked during replay and its call count was zero;
no new query was made. Every first-step/output/source-file hash, entity key,
mention reference, native ID and preserved type passed checks. Relative to the
draft candidate rows, only approval metadata for the two name selections
changed. Q137378 still uses the newer `rōmusha` label. The in-memory suite has
19 passing tests; Ruff checks passed. Accepted manifest SHA-256:
`a4b967188c7247996309e53dba9851208d8d8e1e69c21d79f7afb1cc35c252e4`.

### Historical relation stop and approved native mapping rule

A cache-only check of Daniel-QID/Daniel-QID statements stopped at its first
missing mapping, after 191 eligible non-excluded statements had been checked.
This is a partial check, not a total of all sample assertions or missing keys.
The v2.1.0 catalog had no `(Wikidata, wd:P2341)` entry. The exact case is
`Q105969841` (Poles) -> `Q36` (Poland), statement
`Q105969841$8D05BA41-C448-45B5-93EA-A37877F5140D`, normal rank.
Wikidata names P2341 [indigenous to](https://www.wikidata.org/wiki/Property:P2341).

Evidence is in `outputs/poc_10k_relations_preflight/first_exception.json`, with
raw statement, record provenance and catalog/source checksums. Status is
`BLOCKED_RELATION_MAPPING`. This historical report remains unchanged. No
Relations/Events/Geography/graph output was generated by that check.

On 20 October 2026, the user approved the general rule in population S2T
section 8: existing mappings take priority. For a missing source mapping, use
an actual direct Wikidata statement between the same included QIDs. Add its
native property unchanged at Level 2 to the mapping parameters; leave Level 1
`UNRESOLVED` / `NOT_ASSIGNED`. Without a source statement, create no relation.
Conflicting mappings still require consultation. No entity extraction or
matching decision changes are authorized by this rule.

[Native parameters](../mapping/ADDITIONAL_NATIVE_RELATION_RULES_2026-10-20.csv)
and [source evidence](../mapping/NATIVE_RELATION_EVIDENCE_2026-10-20.json)
now supply P2341 to the existing catalog builder. The separate
[v2.1.1 mapping](../mapping/RELATION_MAPPING_TABLE_v2.1.1.csv) has 1,596 source
keys. It reuses the existing P2341 Level 2 and reverse definition, so the
1,064 Level 2 definitions and 2,097 direction lookup rows are unchanged in
count. Reusing the historical EventKG definition does not import EventKG facts.

`build_relation_mapping_v2_1.build(native_rules=..., version=..., output=...)`
accepts these supplemental parameters. Native additions require a new version;
use a separate output destination when rebuilding for review. All 27 tests and
2 subtests passed, including byte-for-byte reproduction of the historical
v2.1.0 CSVs. No new query was made. The broader relation check and population
have not rerun; discovery and parameter updates must be connected to the
Relations stage before this is an automatic pipeline fallback.

### Relations source gate — historical stops resolved

`relations.py` implements the strict source gate for the next stage. It verifies
the accepted Entities manifest, output hashes, original sample lineage and
pinned mapping; it reads full records from Entities without retrieval. Typed
rows are checked once per QID. The 14 guarded exclusions precede mapping;
deprecated ranks remain eligible. The source gate does not yet populate
Relations or connect automatic native-parameter additions.

The first real-data check stopped in
`outputs/poc_10k_relations_20261020/first_exception.json`:

- Subject: Joachim von Ribbentrop (`Q101886`).
- Relation: member of political party (`wd:P102`).
- Object: Nazi Party (`Q7320`).
- Statement: `Q101886$6AB5CB76-32AE-412D-A84C-F3B49B990BB6`, normal rank.
- Two P580 start qualifiers: `+1930-00-00T00:00:00Z` (year precision 9)
  and `+1932-05-01T00:00:00Z` (day precision 11).

This source cannot supply one selected start date without a choice. The gate
stopped at this case; it is not an all-sample conflict count. Both native snaks,
their calendars/precision and provenance are retained in the exception and
unchanged Entities. No relation table, new mapping parameters or completed
Relations manifest was written, and no query was made.

The user approved `relation-date-selection-v1.0.0`: earliest supplied start from 1900; if all starts precede 1900, derived year 1900 (precision 9); latest end. Exclude a relation whose latest end precedes 1900, preserving the raw record and reason. Missing dates stay missing. Point-date conflicts and remaining reversed intervals still require consultation. This policy does not select Event dates. See population S2T section 8.

The next Prague source case (1804-1867) is resolved by the pre-1900 end exclusion. An overstrict P53 mapping guard was also corrected to honor the existing native-retention decision; no catalog rule changed. Historical exception directories remain unchanged.

Replay `outputs/poc_10k_relations_date_scope_check_20261020` passed the source gate: 4,712 QIDs; 213,277 raw claims; 10,501 in-scope statements; 34 pre-1900-end exclusions; 10,467 retained statements (10,053 normal, 363 preferred, 51 deprecated). Retained time statuses: 9,349 NONE, 662 PARTIAL, 451 DIRECT, 5 MULTIPLE. Status is `DANIEL_RELATIONS_SOURCE_CHECK_ONLY`. No populated Relations, event acquisition or graph exists from this check. No new query occurred.

Focused tests cover preserved raw statements, typed-row deduplication, all ranks, native-retention mapping guards, date selection/floor/precision, pre-1900-end exclusion (including negative years), latest-end and missing-end behavior.

## Approved graph interfaces

`graph_contract.py` provides small interface helpers:

- Distinct QID/type nodes use `QID::type`, keeping `wikidata_id` separately.
  Existing per-mention synthetic IDs stay unchanged.
- A QID endpoint index returns all its separate typed node IDs. Relations and
  source assertion counts are not expanded across these nodes.
- `geometry_ref` is null or `{file, place_id, sha256}`. The referenced GeoParquet
  must contain exactly one valid nonempty geometry for the place and known CRS.
  `load_geometry(pointer, artifact_root)` returns its Shapely object. Broken
  pointers fail explicitly. No GeoJSON conversion or CRS transformation occurs.

These helpers are not yet connected to the current Agent engine. Its full query
path and spatial CRS requirements must be verified before graph acceptance.

Run the in-memory checks (no Daniel data output):

```powershell
C:\Users\User\anaconda3\python.exe -B -m pytest -q -p no:cacheprovider GG_Data/pipeline/test_pipeline.py
```
