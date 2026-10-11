# Full Level 1 to Level 2 relation map

Date: 2026-10-11

## Result

The map contains all **1,106 distinct Level 2 relations** in the
current local relation inventory. It represents all **1,520
eligible source relation rows**. No eligible source relation is absent.

The source meanings remain separate. In particular, Wikidata `P17` country,
`P495` country of origin, and `P8047` country of registry are three Level 2
relations. They share only the `COUNTRY_ASSOCIATION` non-failure group for
project evaluation.

## Assignment status

- 229 Level 2 relations retain their existing Level 1 family.
- 877 Level 2 relations have ranked family options and require
  review.
- 0 Level 2 relations are missing from the output.
- The ranker does not accept or merge a relation.
- No entity-pair relation classifier was run.

The four-fold check on the existing assignments produced
**84.7% exact family accuracy** and **95.6%
top-three family coverage**. These figures measure how well the ranker repeats
the existing catalog rules. They do not prove that those rules are correct.

## Level 1 statistics

| Level 1 family | Existing | Ranked review | Total options |
|---|---:|---:|---:|
| AFFILIATION_STATUS | 27 | 59 | 86 |
| AWARD_RECOGNITION | 4 | 4 | 8 |
| CAUSAL | 10 | 45 | 55 |
| CONFLICT_AFFILIATION | 6 | 3 | 9 |
| CREATION_AUTHORSHIP | 16 | 111 | 127 |
| EDUCATION_EMPLOYMENT | 8 | 11 | 19 |
| FAMILY_PERSONAL | 15 | 70 | 85 |
| FORMATION_DISSOLUTION | 9 | 16 | 25 |
| ORGANIZATION_HIERARCHY | 7 | 16 | 23 |
| OWNERSHIP_CONTROL | 4 | 1 | 5 |
| PARTICIPATION_ROLE | 47 | 137 | 184 |
| PART_WHOLE_HIERARCHY | 9 | 32 | 41 |
| SPATIAL | 61 | 366 | 427 |
| TEMPORAL_SUCCESSION | 6 | 6 | 12 |

## Source coverage

| Source | Predicate rows | Eligible relations | Excluded | Canonical Level 2 IDs |
|---|---:|---:|---:|---:|
| EventKG | 826 | 808 | 18 | 801 |
| WarSampo | 165 | 111 | 54 | 111 |
| Wikidata | 670 | 601 | 69 | 601 |

The Wikidata scope is 53,857 World War II task
force QIDs. EventKG maps 38,517 of those QIDs
and uses all local relation files. WarSampo uses the full local release.

## Files

- `level1_level2_map.csv`: one row per Level 2 relation, with its current or
  proposed Level 1 family and full provenance.
- `level1_candidate_rankings.csv`: all 14 family options for every
  relation that still needs family review.
- `level1_statistics.csv`: counts and occurrence totals per Level 1 family.
- `source_statistics.csv`: source inventory and coverage counts.
- `evaluation_acceptable_options.csv`: non-failure options kept separate from
  the semantic catalog.
- `summary.json`: machine-readable totals and validation statistics.

## Use rule

The complete catalog prevents an observed source relation from disappearing.
The ranked Level 1 family can order review work, but it cannot remove a Level 2
option from later relation selection. An unknown future predicate must enter a
new review row instead of being forced into an existing relation.
