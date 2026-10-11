# Common relation map from observation overlap

Date: 2026-10-11

## Result

The map keeps all **1,520 source relation rows** and groups them
under **1,099 common Level 2 relation IDs**. The earlier map had
**1,106 IDs**. Observation overlap added
**7** provisional source-to-common mappings and reduced the
common ID count by **7**.

No source relation or source data was changed. Direction stays explicit.

Of the common IDs, **403** connect
more than one source: **399** connect two sources and
**4** connect all three sources.

## New provisional mappings

| Source predicate | Common Level 2 | Direction | Max shared pairs | Contexts |
|---|---|---|---:|---:|
| `http://dbpedia.org/ontology/award` | `wd:P166` | same | 719 | 1 |
| `http://dbpedia.org/ontology/battle` | `wd:P607` | same | 7,178 | 2 |
| `http://dbpedia.org/ontology/nonFictionSubject` | `wd:P921` | same | 22 | 1 |
| `http://dbpedia.org/ontology/origin` | `wd:P495` | same | 209 | 1 |
| `http://dbpedia.org/ontology/restingPlace` | `wd:P119` | same | 76 | 1 |
| `http://dbpedia.org/ontology/usedInWar` | `wd:P607` | same | 507 | 1 |
| `http://yago-knowledge.org/resource/hasWonPrize` | `wd:P166` | same | 409 | 1 |

## Decision rule

1. Use repeated pairs whose endpoints have the same Wikidata IDs.
2. Keep only context winners with at least 20 shared pairs, at least five held-out
   pairs, at least five targets, 90% pair coverage, 80% coverage after the
   largest target, and 80% held-out coverage.
3. Require a score lead of at least 15 points over the next candidate.
4. Merge a source predicate only when all accepted contexts select the same
   Wikidata relation and direction.
5. Preserve an existing mapping when the observation winner points elsewhere.
   Record that result for review instead of replacing it.

## Important limits

- A provisional mapping is strong repeated-use evidence. It is not proof that
  the source definitions are identical in every context.
- Source occurrence sums can contain the same fact in more than one source.
- A missing overlap keeps the source relation separate.
- Level 1 stays `UNRESOLVED` when the full map has only a ranked Level 1 option.

## Files

- `common_relation_source_map.csv`: every source predicate and its common ID.
- `common_relation_groups.csv`: one row per common Level 2 ID.
- `observation_mapping_evidence.csv`: accepted observation contexts and actions.
- `summary.json`: validation totals.
