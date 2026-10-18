# Entity matching runs

## Wikipedia dump import into BigQuery — 18 October 2026

[Current run, evidence scope, saved data, and resume command](WIKIPEDIA_DUMP_RUN_2026-10-18.md).
English/Japanese bulk downloads are running. Automatic continuation imports the
needed page links into BigQuery and then matches all 309,864 Daniel mentions.
The first real Japanese redirect table is imported. The 80% matching rule stays
fixed. Final full-data counts are not available yet.

## Full run moved to BigQuery — 18 October 2026

[BigQuery run status, saved data, and resume command](BIGQUERY_RUN_2026-10-18.md).
This earlier page-API worker is superseded by the dump import above. It replaced
the delayed Wikidata API worker. All Daniel rows
and accepted matching rules remain in scope. Query results are stored locally
for reuse. Final full-data counts are not available yet.

## Full direct-Wikidata run — 18 October 2026

[Run status and files](FULL_DIRECT_RUN_2026-10-18.md).
Started for all **309,864 mentions / 428 source titles**, with the accepted
80% threshold and unchanged three-pass/type/date/synthetic-ID rules. The report
is updated automatically on completion. Large run files and page evidence are on C:
because D: is nearly full. No article-name extraction or canonical graph update.
Reference responses are saved and reused across runs. Offline replay verified
303 saved responses with zero network requests; see the report's saved-data
section for paths, the hash inventory, and reuse limits.

## Quick threshold test — 18 October 2026

[Report](THRESHOLD_TEST_2026-10-18.md) · [Comparisons](runs/threshold_sensitivity_20261018/comparison.csv)

Page matching only, all 324 non-date mentions from the same three-page pilot.
75% gives 270 assignments, 80% gives 263, and 90% gives 258. Lowering adds both
correct and wrong matches; raising loses a correct Roosevelt match and retains
wrong exact-name homonyms. Keep 80% provisionally. Full-workflow assignments and
the canonical graph remain unchanged; the test is not an accuracy estimate.

## Current single-type trial and page audit — 18 October 2026

[Report](TYPE_AND_PAGE_LOOKUP_AUDIT_2026-10-18.md) · [Rows](runs/direct_wikidata_single_type_20261018_v2/matches.csv) · [Page audit](runs/direct_wikidata_single_type_20261018_v2/page_lookup_audit.csv)

Offline replay of the same 362 mentions: 269 QID assignments, 37 calendar dates,
56 unresolved. When no compatible candidate exists, one clear mapped Wikidata
type can replace Daniel's type, with both types and P31 evidence recorded in row
metadata. Yale's excluded-branch bug is fixed. Some new assignments are wrong;
counts are not accuracy. The report explains missing page links and unused
anchor names. No canonical graph update.

## Earlier direct Daniel-to-Wikidata small run — 18 October 2026

[Report](DIRECT_WIKIDATA_SMALL_RUN_2026-10-18.md) · [All result rows](runs/direct_wikidata_small_20261018/matches.csv)

Same three pages, all **362 mentions**: **258 Wikidata matches**, **37 normalized
dates**, **67 separate unresolved mention IDs**. No notebook or independent
article-name extraction. Candidate lookups use Daniel's names directly; source
page IDs and direct English/Japanese hyperlinks provide page references.
Page-only space/symbol cleanup is applied. All DATE mentions use calendar
normalization/validation. Original input and older runs remain unchanged.
The existing type filter still rejects Yale despite retrieving its correct QID;
known wrong trigram matches also remain. See the report before interpreting counts.

## Earlier bilingual pilot — 18 October 2026

[New pilot report](BILINGUAL_PILOT_REPORT_2026-10-18.md) · [Executed notebook](BILINGUAL_PILOT_STEP_BY_STEP.ipynb) · [Results](runs/bilingual_pilot_20261018_v1/report.html)

Three pages, all **362 mentions** and all five types: **244 automatic matches**,
**118 distinct synthetic mention IDs**. English and Japanese articles were read
when a Japanese counterpart exists. Matching uses compatible types, the highest
trigram Dice score at least 0.80, and seeded random ties. The final pass uses a
fresh 103,235-ID Wikidata query, not the old graph. No manual match overrides.

The notebook reproduces every saved assigned ID. **Some automatic matches are
clearly wrong**, including Mayforce → Layforce and Alfred Curtis → Wilfred Curtis.
Article candidate collection and the broad type map remain incomplete. Read the
report's limits before interpreting match counts as identity quality.

The current run fixes calendar-month typing and excludes properties from QID
candidates. The initial pilot is preserved separately. Previous full-run sections
below describe earlier methods; their unknown-entity deferral is superseded only
for this new pilot by the user's approved three-pass and synthetic-ID rules.


## Reference coverage correction

**Completed and verified:** [reference coverage correction and full rerun](REFERENCE_COVERAGE_FIX_2026-10-18.md).
The earlier name cache lacked metadata for **92,461 of the graph's 144,990 IDs**.
It also lacked English labels for another 427 graph IDs. The previous unresolved
counts do not measure Daniel's extraction quality. A separate supplement has
been verified: all 144,990 graph IDs have metadata, and 141,776 have English
names. The other 3,214 explicitly lack English names in Wikidata. All **309,864
mentions** were rerun with the same matching rules: **149,483 suggestions** and
**160,381 unresolved**, compared with 63,922 and 245,942 in the previous wide
trial. All input rows and graph assertions were preserved. Clear wrong links
remain, including nationality words mapped to languages and Roosevelt mapped
to Theodore Roosevelt in a paragraph about Franklin D. Roosevelt. Accuracy is
not measured. Historical outputs remain preserved; no suggestions were promoted
into the canonical graph.

```powershell
python GG_Data/entity_resolution/run_notebook_matching.py --wide-search --page-map GG_Data/entity_resolution/runs/source_pages_v0.1.0_20261018/page_map.json --metadata-supplement GG_Data/entity_resolution/runs/graph_reference_v0.1.0_20261018/entity_metadata.jsonl.gz --output GG_Data/entity_resolution/runs/all_types_completed_reference_v0.2.1_20261018
```

Use a new output directory for another run. The saved supplement must pass its
manifest and graph-coverage checks before matching starts.

## Wider-search trial

**Completed:** [full-reference trial report and examples](WIDE_SEARCH_RUN_REPORT_2026-10-18.md).
All 309,864 mentions were processed automatically: **63,922 suggestions** and
**245,942 unresolved results**, compared with 9,555 and 300,309 in the resolved-page
baseline. Search now covers all English names in the same saved reference
snapshot, with the existing 0.80 name threshold and person-type check applied
before graph ranking. The page remains context rather than a hard search limit.

```powershell
python GG_Data/entity_resolution/run_notebook_matching.py --wide-search --page-map GG_Data/entity_resolution/runs/source_pages_v0.1.0_20261018/page_map.json --output GG_Data/entity_resolution/runs/all_types_wide_search_v0.2.0_20261018
```

This is a separate trial. It adds 54,724 suggestions, removes 357, and changes
453 suggested IDs. The report includes both repaired examples and clear wrong
links. Accuracy is not measured; compatibility beyond explicit person types is
still assumed, and dates have no separate parser. No output was promoted into
the canonical graph. The default runner and original notebook rules remain
available. All earlier run outputs are preserved.

## Rerun using resolved source pages

**Completed:** [resolved-page matching report](RESOLVED_PAGES_RUN_REPORT_2026-10-18.md).
All 309,864 mentions were processed: **9,555 automatic suggestions** and
**300,309 unresolved results**, adding 1,517 suggestions. Results for all
192,220 mentions from the original 239 resolved pages are identical.

```powershell
python GG_Data/entity_resolution/run_notebook_matching.py --page-map GG_Data/entity_resolution/runs/source_pages_v0.1.0_20261018/page_map.json --output GG_Data/entity_resolution/runs/all_types_resolved_pages_v0.1.0_20261018
```

This separate run applies the same fixed matching rules to all five extraction
types. It uses the verified page map and rebuilds direct incoming/outgoing page
pools from the same frozen mapped graph. Names and person types come from the
same saved Wikidata snapshot. No new reference data is fetched. Previously
resolved page identities, pools, and cached names/types must agree before
matching starts.

The new run saves its own `page_context.jsonl.gz` and `entity_metadata.jsonl.gz`.
Use these files for its candidate evidence joins; its `mapped_graph.jsonl.gz`
contains the supporting assertion records. A resolved page ID does not imply
that names, types, or usable graph context are available. Earlier run outputs
are preserved.

## Source-page identity lookup

**Completed:** [source-page lookup report](SOURCE_PAGE_LOOKUP_2026-10-18.md).
The live Wikipedia lookup resolved 424 of Daniel's 428 source titles, compared
with 239 in the frozen reference join. This separate page map was applied to
the resolved-page matching run and the wider-search trial described above.

```powershell
python -m pytest -q GG_Data/entity_resolution/test_resolve_source_pages.py
python GG_Data/entity_resolution/resolve_source_pages.py --output GG_Data/entity_resolution/runs/source_pages_v0.1.0_20261018
```

Use a new output directory for another lookup. The saved API responses provide
the original title normalization, redirects, page IDs, Wikidata IDs, and lookup
times. Missing pages, disambiguation pages, and identity conflicts remain
unresolved. These are current page identities, not proof of the page revision
used for extraction. Graph coverage is checked separately.

**Open follow-up with Daniel:** ask for the source URL, Wikipedia page ID,
language/site, and exact revision ID (or permanent revision URL) in future
exports. Keep `Source` and `Index` for backward compatibility. This request is
recorded for later; no message has been sent.

## One-time automatic matching of all Daniel's rows

**Completed:** [all-type run report](ALL_TYPES_RUN_REPORT_2026-10-18.md).
All 309,864 mentions were processed: 8,038 automatic suggestions and 301,826
unresolved results. The report records observed false matches; the output has
not been corrected or promoted to verified identities.

```powershell
python -m pytest -q GG_Data/entity_resolution/test_generate_candidates.py GG_Data/entity_resolution/test_notebook_matching.py
python GG_Data/entity_resolution/run_notebook_matching.py --output GG_Data/entity_resolution/runs/all_types_notebook_v0.1.0_20261018
```

This command applies the notebook's fixed name, HITS, and suggestion rules to
every raw row, including **PER, LOC, ORG, MISC, and DATE**. It uses no training
labels, model calls, manual choices, threshold tuning, or live lookups. The
verified first run below supplies a reusable page/name cache. All original
input and cache hashes must still match. The existing outputs are preserved.

The fixed settings are name similarity 0.35, outgoing graph depth 1, 20 HITS
rounds, suggestion name threshold 0.80, and relative authority gap 0.20 for
multiple candidates. Candidate sets are combined within each Source/Index
paragraph. Graph direction and the 14 approved record exclusions are retained.
The notebook and batch command import the same `notebook_rules.py` functions.

The notebook's person check remains explicit P31=Q5. For LOC, ORG, MISC, and
DATE, type compatibility is **assumed**, following the agreed scope. This is
not an implementation of a new type classifier or temporal normalization.
DATE gets the same English label/alias search and graph rules as other
mentions; no date parser, synthetic date nodes, or broader date index is added.
Missing pages or candidates remain unresolved. No new entity is created.

New run outputs:

| File | Contents |
|---|---|
| `mention_matches.jsonl.gz` | Every raw mention, ranked candidates, name evidence, final HITS authority, automatic suggestion or unresolved reason |
| `graph_contexts.jsonl.gz` | Each distinct paragraph seed set, graph size/hash, and final seed authority/hub values; contexts can be shared by paragraphs |
| `mapped_graph.jsonl.gz` | Complete replay of mapped assertions, with original endpoints and source records; rebuild any context from its seeds and outgoing depth 1 |
| `summary.json` | Complete denominators and decisions by type and page |
| `run_manifest.json` | Completion marker, fixed rules, frozen input/code/cache/output hashes and verification results |

Use `input_row_number` to recover the original input order. `graph_context_id`
joins mentions to graph contexts. Candidate `page_context_id` joins to the
first run's page evidence. Entity IDs join to its saved entity metadata.
The candidate and suggestion scores are not probabilities. Suggestions are
unvalidated automatic outputs, not verified identity truth. Unknown-entity
handling remains open, and the canonical graph is not changed.

## First full candidate-only run

This stage keeps Daniel's raw mentions and proposes existing entity IDs. It does
not select identities, run HITS, create unknown entities, extract relations, or
change the graph.

## Run

From the repository root, using the existing Anaconda Python environment:

```powershell
python -m pytest -q GG_Data/entity_resolution/test_generate_candidates.py
python GG_Data/entity_resolution/generate_candidates.py --output GG_Data/entity_resolution/runs/first_candidates_v0.1.0_20261018
```

The output directory must be new. Existing files are never overwritten. A run is
complete only when `run_manifest.json` says `COMPLETED`. Local source snapshots
under `Data/external` and the existing legacy assertion CSV are required. Their
exact hashes are recorded in the manifest; these large inputs are not included
in this folder.

## Fixed first-run rules

1. Verify Daniel's parquet against its pinned Git blob from commit
   `43e35453421b032fc67d426d7d16fe436574b0fa`.
2. Resolve each page by an exact title in `article_qids.jsonl`, with an exact
   saved Wikidata English Wikipedia sitelink as a fallback. Leave missing or
   ambiguous page identities unresolved. No live lookup or fuzzy page matching.
3. Candidate scope is the page itself and its direct incoming/outgoing graph
   neighbours. Restore original assertion endpoints, apply approved exclusions,
   then apply relation-map-v2.1.0. Keep the source evidence and direction.
4. Compare English names and aliases using the notebook's Unicode normalization
   and character-trigram Dice similarity. Keep every entity with a best name
   score at least **0.35**. No candidate cap, title removal, or graph ranking.
5. For `PER`, require explicit saved Wikidata `P31=Q5`. For `LOC`, `ORG`, and
   `MISC`, generate lexical candidates and mark type checks **PENDING**. No type
   hierarchy or type mapping is introduced here. Preserve `DATE` rows as
   **DEFERRED_DATE**, without entity candidates.

The threshold is exploratory, not calibrated. Strict page scope can omit the
correct entity. Missing metadata or English names can also hide candidates.
No candidates does not mean that an entity is unknown. Unknown-entity handling
remains an open issue. Candidate counts measure retrieval coverage; they do not
measure candidate recall, linking accuracy, or match probability.

## Outputs

| File | Contents |
|---|---|
| `mention_candidates.jsonl.gz` | One record per input row, all nine raw fields, original row number, stable mention ID, page status, candidate IDs, matched names, scores, and evidence references |
| `page_context.jsonl.gz` | Page identity evidence, candidate pools, original and mapped assertion endpoints, source predicates, and source record IDs |
| `entity_metadata.jsonl.gz` | Candidate labels, aliases, direct types, saved Wikidata revision, or an explicit missing-metadata marker |
| `summary.json` | Full denominators by extraction type and page, missing-page cases, candidate counts, and exclusions |
| `run_manifest.json` | Completion marker, method parameters, input/code/output hashes, package versions, and verification results |

`mention_id` is SHA-256 of the ordered JSON array
`[Source, Index, start, end, entity_group]`, using UTF-8, unescaped Unicode, and
compact JSON separators. Changes to extraction confidence or input row order do
not change identity. Different or overlapping spans remain separate. Duplicate
mention identities cause the run to fail instead of silently removing rows.

Each candidate's `context_id` is `page_qid|entity_id`; it joins to that entity in
the page's `pool` in `page_context.jsonl.gz`. `entity_id` joins to the metadata
file. `run_id` joins each output to the manifest and its input/mapping versions.
There are no accepted or selected identity links in this output.

The script rereads every output row and verifies raw-input equality, IDs,
candidate counts, page-pool membership, matched names, exact scores, and the
person type rule. It also checks that all input/code hashes remain unchanged.

## Inspect a result

```python
import gzip
import json
from pathlib import Path

run = Path("GG_Data/entity_resolution/runs/first_candidates_v0.1.0_20261018")
summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
with gzip.open(run / "mention_candidates.jsonl.gz", "rt", encoding="utf-8") as rows:
    example = next(json.loads(line) for line in rows
                   if '"word":"Isoroku Yamamoto"' in line)
print(example)
```

For an interactive explanation, open `ENTITY_MATCHING_STEP_BY_STEP.ipynb`. Its
name functions are shared with this full-run script. Its later HITS and decision
cells remain a separate teaching example.
