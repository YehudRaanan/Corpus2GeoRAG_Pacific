# Country relation data-availability audit

Date: 2026-10-11

## Question

Do the 600 unresolved pairs lack a relation, or did the earlier run lack
the data needed to observe it?

## Results

- Current Wikidata now has `P17` or `P8047` for **0** pairs.
- Another forward Wikidata property connects the same QIDs for **43** pairs.
- An inverse Wikidata property connects the same QIDs for **0** pairs.
- A Wikidata qualifier path connects the same QIDs for **8** pairs.
- A Wikipedia infobox field contains the object identity for **285** pairs.
- The complete article links to the object identity for **366** pairs.
- The complete article has a minimal sentence-to-paragraph span for **213** pairs.
- The earlier lead-only run had such a span for **154** pairs.
- A known structured Wikidata property resolves **43** pairs.
- **357** unresolved pairs have evidence for later classification.
- **200** unresolved pairs have no evidence in the checked sources.

These groups overlap. They are evidence-availability checks, not relation
labels. A direct Wikidata property resolves its own typed relation. Infobox
fields, links, qualifier paths, and text still need semantic classification.

## Primary availability status

| Status | Pairs |
|---|---:|
| `ALTERNATIVE_WIKIDATA_RELATION_OBSERVED` | 43 |
| `DATA_NOT_OBSERVED_IN_CHECKED_SOURCES` | 200 |
| `FULL_ARTICLE_ENTITY_LINK_OBSERVED` | 82 |
| `FULL_ARTICLE_TEXT_COOCCURRENCE_OBSERVED` | 11 |
| `INFOBOX_ENTITY_EVIDENCE_OBSERVED` | 259 |
| `LEAD_TEXT_COOCCURRENCE_OBSERVED` | 3 |
| `WIKIDATA_QUALIFIER_RELATION_OBSERVED` | 2 |

## Common alternative Wikidata properties

| Property | Label | Pairs |
|---|---|---:|
| `P495` | country of origin | 20 |
| `P945` | allegiance | 16 |
| `P27` | country of citizenship | 5 |
| `P1532` | country for sport | 2 |
| `P361` | part of | 2 |
| `P840` | narrative location | 1 |
| `P276` | location | 1 |
| `P137` | operator | 1 |

## Common matching infobox fields

| Field | Pairs |
|---|---:|
| `country` | 200 |
| `allegiance` | 73 |
| `garrison` | 15 |
| `operations` | 6 |
| `builder` | 4 |
| `death_place` | 4 |
| `image` | 4 |
| `birth_place` | 3 |
| `caption` | 3 |
| `battles` | 2 |
| `image_caption` | 2 |
| `office` | 2 |
| `captured` | 2 |
| `name` | 1 |
| `studio` | 1 |

## Common Wikidata qualifier paths

| Path | Pairs |
|---|---:|
| `P577/P291` | 3 |
| `P17/P518` | 3 |
| `P1411/P2453` | 1 |
| `P2142/P3005` | 1 |
| `P793/P12995` | 1 |
| `P793/P276` | 1 |
| `P17/P2348` | 1 |

## Interpretation

`RELATION_NOT_OBSERVED_IN_LOCAL_SNAPSHOT` replaces any claim that a relation
is missing. A direct alternative Wikidata property keeps its exact property
type and is resolved. `RELATION_SEMANTICS_UNRESOLVED` means that no direct
structured relation was observed. Qualifier paths, infobox fields, entity
links, and text spans are candidates for later semantic classification.

The classifier was not run.

## Examples

- **66th Division -> Empire of Japan**: `INFOBOX_ENTITY_EVIDENCE_OBSERVED`; country
- **Lötzen Infantry Brigade -> Nazi Germany**: `INFOBOX_ENTITY_EVIDENCE_OBSERVED`; allegiance
- **Ambra -> Kingdom of Italy**: `ALTERNATIVE_WIKIDATA_RELATION_OBSERVED`; P495
- **Come and See -> Soviet Union**: `ALTERNATIVE_WIKIDATA_RELATION_OBSERVED`; P495|P840
- **NMS Regele Ferdinand I -> Soviet Union**: `FULL_ARTICLE_ENTITY_LINK_OBSERVED`; Soviet Union
- **Curt Bruns -> Nazi Germany**: `INFOBOX_ENTITY_EVIDENCE_OBSERVED`; allegiance
- **61st Division -> Empire of Japan**: `INFOBOX_ENTITY_EVIDENCE_OBSERVED`; country
- **47th Division -> Empire of Japan**: `INFOBOX_ENTITY_EVIDENCE_OBSERVED`; country

## Files

- `country_data_availability_audit/pair_audit.csv`
- `country_data_availability_audit/summary.json`
