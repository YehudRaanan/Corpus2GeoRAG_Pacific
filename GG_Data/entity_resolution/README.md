# Entity matching runs

## One-time automatic matching of all Daniel's rows

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
