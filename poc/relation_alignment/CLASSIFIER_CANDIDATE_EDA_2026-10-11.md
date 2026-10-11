# Classifier candidate EDA

Date: 2026-10-11

## Scope

The EDA covers **371** unresolved pairs that have checked evidence.
It uses resolved structured pairs only to create possible Level 2 choices.
It does not select a relation and does not run a classifier.
The Wikipedia page QID defines the subject. A page-anchored evidence
sentence therefore needs to identify only the object in the article body.

## Candidate construction

- **2,564** unique structured seed assertions.
- **10** possible Level 2 relation values.
- Compare direct Wikidata `P31` endpoint types first.
- If no candidate exists, expand through `P279` for at most two levels.
- Stop at the first level that produces candidates.
- Keep all relations supported at that level; support count ranks them only.

## Main results

- **369** pairs have one or more type-matched candidates.
- **2** pairs have no type-matched candidate.
- **186** pairs have one candidate.
- **183** pairs have several candidates.
- **281** pairs match direct `P31` types.
- **88** pairs need broader `P279` types.

## Classifier gate

- **267** pairs have the required complete sentence or paragraph.
- **265** of them also have a type-matched candidate list.
- **130** text-ready pairs need the classifier to choose among several candidates.
- **113** text-ready pairs have one candidate with at least two seed examples.
- **104** pairs have only structured, infobox, or link evidence and are outside the text-classifier input contract.

## Evidence readiness

| Input status | Pairs |
|---|---:|
| `ENTITY_LINK_ONLY` | 4 |
| `INFOBOX_ONLY` | 98 |
| `LEAD_SPAN_READY` | 1 |
| `PAGE_ANCHORED_TEXT_READY` | 71 |
| `TEXT_SPAN_READY` | 195 |
| `WIKIDATA_QUALIFIER_ONLY` | 2 |

## Candidate review status

| Status | Pairs |
|---|---:|
| `MULTIPLE_CANDIDATES` | 183 |
| `NO_TYPE_MATCHED_CANDIDATE` | 2 |
| `SINGLE_LOW_SUPPORT_CANDIDATE` | 43 |
| `SINGLE_SUPPORTED_CANDIDATE` | 143 |

## Possible Level 2 values

| Relation | Label | Level 1 | Seed assertions | Candidate pairs |
|---|---|---|---:|---:|
| `P17` | country | `SPATIAL` | 1,376 | 305 |
| `P8047` | country of registry | `SPATIAL` | 1,140 | 129 |
| `P495` | country of origin | `SPATIAL` | 20 | 85 |
| `P945` | allegiance | `AFFILIATION_STATUS` | 16 | 93 |
| `P27` | country of citizenship | `AFFILIATION_STATUS` | 5 | 7 |
| `P1532` | country for sport | `SPATIAL` | 2 | 5 |
| `P361` | part of | `PART_WHOLE_HIERARCHY` | 2 | 2 |
| `P137` | operator | `OWNERSHIP_CONTROL` | 1 | 46 |
| `P276` | location | `SPATIAL` | 1 | 15 |
| `P840` | narrative location | `SPATIAL` | 1 | 2 |

## Limits before classification

- Type compatibility creates an allowed list. It does not prove a relation.
- A broad `P279` match can add unrelated choices.
- A candidate with one seed example is weak.
- A page-anchored sentence can discuss another entity on the page. The
  classifier must be allowed to return `UNRESOLVED`.
- An infobox field or entity link is not a complete co-appearance text span.
- `NO_TYPE_MATCHED_CANDIDATE` means that the seed data do not cover the type pair.

## Files

- `classifier_candidate_eda/cases.csv`
- `classifier_candidate_eda/type_pair_groups.csv`
- `classifier_candidate_eda/evidence_groups.csv`
- `classifier_candidate_eda/candidate_relations.csv`
- `classifier_candidate_eda/summary.json`
