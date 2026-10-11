# Relation catalog EDA before classification

Date: 2026-10-11

## Purpose

Build a source-derived list of possible Level 2 relations under broad Level 1
families. Accept only simple mappings with clear direction and scope. Stop
before any text classifier.

The run did not change Wikidata, EventKG, WarSampo, or the Agent contract.
Dates remain attributes of relations or events. They are not relation types.

## Source coverage

| Source | Local scope used | Relation inventory |
|---|---:|---:|
| Wikidata | 53,857 WWII task force QIDs; 53,857 records | 670 observed item-valued properties |
| EventKG 3.2 | 38,517 of those QIDs; all relation, type, and label files | 826 observed predicates |
| WarSampo 2.1.0 | Full local release; 71 Turtle files | 145 observed predicates plus 20 defined terms not observed |

Twelve of the 20 WarSampo terms that are defined but not observed are possible
Level 2 relations. The other eight are schema or support terms.

## Process

1. Read each source without changing it.
2. Remove type, identity, provenance, document, date, coordinate, quantity, and
   other basic attribute predicates.
3. Keep each remaining source predicate as a possible Level 2 relation.
4. Merge source predicates only when a scoped definition gives the same meaning
   and direction, or when all of these data rules pass:
   - the English labels are equal after simple normalization;
   - at least 20 endpoint pairs are shared;
   - at least 90% of co-connected pairs agree;
   - at least 80% still agree after the largest target is removed;
   - only one Wikidata property passes for that source predicate.
5. Put each canonical Level 2 relation in one Level 1 family. Keep uncertain
   cases in `UNASSIGNED_REVIEW`.
6. Stop before text classification.

## Main results

- 1,106 possible canonical Level 2 relations.
- 229 relations assigned to 14 named Level 1 families.
- 877 relations, 79.3%, remain in `UNASSIGNED_REVIEW`.
- 11 accepted cross-source predicate rows map to 9 canonical Wikidata
  relations.
- 7 accepted rows use scoped definitions. Four use repeated endpoint evidence.
- 58 same-label candidates remain unresolved.
- 476 EventKG predicates occur only in EventKG's copied Wikidata graph. They do
  not give independent support.

## Accepted simple mappings

| Source predicate | Canonical Level 2 | Direction | Basis |
|---|---|---|---|
| EventKG `author` | `P50` | same | 38 shared pairs; 97.4% agreement; 97.2% after the largest target |
| EventKG `manufacturer` | `P176` | same | 149; 96.8%; 96.1% |
| EventKG `militaryBranch` | `P241` | same | 3,611; 93.5%; 92.4% |
| EventKG `operator` | `P137` | same | 144; 97.3%; 94.5% |
| EventKG SEM `hasPlace` | `P276` | same | scoped definitions |
| EventKG SEM `hasSubEvent` | `P527` | same | scoped definitions |
| EventKG SEM `subEventOf` | `P361` | same | scoped definitions |
| WarSampo `hasConflict` | `P607` | same | scoped definitions |
| WarSampo CIDOC `falls within` | `P361` | same | scoped definitions |
| WarSampo CIDOC `had participant` | `P710` | same | scoped definitions |
| WarSampo CIDOC `took place at` | `P276` | same | scoped definitions |

## High-value unresolved cases

| Source predicate | Candidate | Evidence | Reason to keep unresolved |
|---|---|---|---|
| EventKG `battle` | `P607` | 7,178 shared pairs; 98.8% agreement | The source label can be narrower than the Wikidata property. Confirm the endpoint scope. |
| EventKG `usedInWar` | `P607` | 507; 100% | Strong data evidence, but the source meaning may be narrower. |
| EventKG `award` | `P166` | 719; 99.0% | Strong data evidence; confirm the definition and endpoint types. |
| WarSampo `hasUpperUnit` | `P361` or inverse `P527` | Both appear on shared pairs | The available local schema has no formal definition for this predicate. Direction and unit scope need review. |

## Level 1 counts

| Level 1 family | Level 2 values |
|---|---:|
| Spatial | 61 |
| Participation and role | 47 |
| Affiliation and status | 27 |
| Creation and authorship | 16 |
| Family and personal | 15 |
| Causal | 10 |
| Formation and dissolution | 9 |
| Part and whole hierarchy | 9 |
| Education and employment | 8 |
| Organization hierarchy | 7 |
| Conflict affiliation | 6 |
| Temporal succession | 6 |
| Award and recognition | 4 |
| Ownership and control | 4 |
| Unassigned review | 877 |

## What the EDA shows

The overlap can produce a small safe mapping automatically. It cannot yet
produce a complete classifier label list. Most source predicates need more
definition, domain, range, or endpoint-type evidence. EventKG copied Wikidata
claims must also be separated from independent evidence.

Before a classifier run, review the frequent unassigned predicates, add formal
ontology definitions and domain/range data for DBpedia and YAGO predicates, and
then freeze the allowed Level 2 values for each Level 1 family and endpoint type
pair.

## Output files

- `relation_catalog_eda/source_predicate_inventory.csv`: full source inventory
  with counts, scope, evidence, and exclusions.
- `relation_catalog_eda/level1_families.csv`: all Level 2 options per family.
- `relation_catalog_eda/level2_relations.csv`: canonical relation list.
- `relation_catalog_eda/accepted_easy_mappings.csv`: accepted mappings and
  evidence.
- `relation_catalog_eda/unresolved_mapping_candidates.csv`: candidates for the
  next review.
- `relation_catalog_eda/summary.json`: machine-readable run summary.

The run script uses the official Wikidata Query Service because the MediaWiki
API returned HTTP 429 during metadata retrieval. Cached property metadata makes
later runs reproducible and avoids repeated remote queries.
