# Classifier candidate EDA

Date: 2026-10-11

## Scope

The EDA covers **357** unresolved pairs that have checked evidence.
It uses resolved structured pairs only to create possible Level 2 choices.
It does not select a relation and does not run a classifier.

## Candidate construction

- **2,564** unique structured seed assertions.
- **10** possible Level 2 relation values.
- Compare direct Wikidata `P31` endpoint types first.
- If no candidate exists, expand through `P279` for at most two levels.
- Stop at the first level that produces candidates.
- Keep all relations supported at that level; support count ranks them only.

## Main results

- **355** pairs have one or more type-matched candidates.
- **2** pairs have no type-matched candidate.
- **177** pairs have one candidate.
- **178** pairs have several candidates.
- **268** pairs match direct `P31` types.
- **87** pairs need broader `P279` types.

## Classifier gate

- **216** pairs have the required complete sentence or paragraph.
- **214** of them also have a type-matched candidate list.
- **105** text-ready pairs need the classifier to choose among several candidates.
- **93** text-ready pairs have one candidate with at least two seed examples.
- **141** pairs have only structured, infobox, or link evidence and are outside the text-classifier input contract.

## Evidence readiness

| Input status | Pairs |
|---|---:|
| `ENTITY_LINK_ONLY` | 13 |
| `INFOBOX_ONLY` | 126 |
| `LEAD_SPAN_READY` | 22 |
| `TEXT_SPAN_READY` | 194 |
| `WIKIDATA_QUALIFIER_ONLY` | 2 |

## Candidate review status

| Status | Pairs |
|---|---:|
| `MULTIPLE_CANDIDATES` | 178 |
| `NO_TYPE_MATCHED_CANDIDATE` | 2 |
| `SINGLE_LOW_SUPPORT_CANDIDATE` | 43 |
| `SINGLE_SUPPORTED_CANDIDATE` | 134 |

## Possible Level 2 values

| Relation | Label | Level 1 | Seed assertions | Candidate pairs |
|---|---|---|---:|---:|
| `P17` | country | `SPATIAL` | 1,376 | 291 |
| `P8047` | country of registry | `SPATIAL` | 1,140 | 129 |
| `P495` | country of origin | `SPATIAL` | 20 | 85 |
| `P945` | allegiance | `AFFILIATION_STATUS` | 16 | 89 |
| `P27` | country of citizenship | `AFFILIATION_STATUS` | 5 | 6 |
| `P1532` | country for sport | `SPATIAL` | 2 | 5 |
| `P361` | part of | `PART_WHOLE_HIERARCHY` | 2 | 2 |
| `P137` | operator | `OWNERSHIP_CONTROL` | 1 | 46 |
| `P276` | location | `SPATIAL` | 1 | 13 |
| `P840` | narrative location | `SPATIAL` | 1 | 2 |

## Limits before classification

- Type compatibility creates an allowed list. It does not prove a relation.
- A broad `P279` match can add unrelated choices.
- A candidate with one seed example is weak.
- An infobox field or entity link is not a complete co-appearance text span.
- `NO_TYPE_MATCHED_CANDIDATE` means that the seed data do not cover the type pair.

## Files

- `classifier_candidate_eda/cases.csv`
- `classifier_candidate_eda/type_pair_groups.csv`
- `classifier_candidate_eda/evidence_groups.csv`
- `classifier_candidate_eda/candidate_relations.csv`
- `classifier_candidate_eda/summary.json`
