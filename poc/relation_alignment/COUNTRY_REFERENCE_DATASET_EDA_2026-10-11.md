# Country relation reference dataset EDA

Date: 2026-10-11

## Scope

This run separates structured, resolved Wikidata assertions from unresolved
EventKG `country` pairs. It does not run the text classifier.

## Counts

- Source pairs: **3,099**.
- Resolved pairs: **2,499**.
- Resolved relation assertions: **2,517**.
- Unique resolved relation edges: **2,516**.
- Resolved assertions with at least one Wikidata reference block: **1,735**.
- Unresolved pairs: **600**.
- English Wikipedia subject pages retrieved: **584 of 584**.
- Pairs where the subject page contains a known subject name: **522**.
- Pairs where the subject page contains a known object name: **169**.
- Pairs where both names occur somewhere in the page: **154**.
- Unresolved pairs with at least one minimal complete text span: **154** (25.7%).
- Extracted text spans: **154**.
- Pairs without a complete span: **446**.

## Resolved assertions

The resolved table has one row per Wikidata statement. It contains 2,516
unique subject-relation-object edges and 2,517 statement rows because one
edge has two Wikidata statements. Of these statements, 1,735 (68.9%) have
at least one Wikidata reference block; 782 have no cited reference block.

## Text rule

For each subject page lead paragraph, the extractor keeps the shortest
contiguous set of complete sentences that contains an alias of both QID
endpoints. It never crosses a paragraph boundary. Wikidata labels, aliases,
and English page titles provide the allowed names.

A text span is `COOCCURRENCE_ONLY`. It does not prove a relation. The later
classifier can select `P17`, `P8047`, both, or neither.

## Finding

The subject article lead supplies a usable co-mention span for only the
reported share of unresolved pairs. Most EventKG `country` values come from
structured DBpedia/Wikipedia data and may not be stated with both entity names
in the lead. A lead-text classifier alone therefore cannot cover this group.

The extraction uses exact Wikidata labels, aliases, and page titles. It does
not resolve pronouns or unnamed descriptions. These cases need link-aware text,
the source infobox field, another page, or an explicit abstention.

## Coverage by graph-context suggestion

The suggestion is a routing hint, not a text label.

| Suggestion | Pairs | Pairs with span | Coverage |
|---|---:|---:|---:|
| `P17` | 464 | 105 | 22.6% |
| `P8047` | 136 | 49 | 36.0% |

## Span levels

| Span level | References |
|---|---:|
| `multi_sentence` | 43 |
| `paragraph` | 8 |
| `sentence` | 103 |

## Examples

- **NMS Regele Ferdinand I -> Soviet Union** (`multi_sentence`): NMS Regele Ferdinand was the lead ship of her class of two destroyers built in Italy for the Romanian Navy in the late 1920s. After the Axis invasion of the Soviet Union on 22 June 1941 (Operation Barbarossa), she was limited to escort duties in the western half of the Black Sea during the war by the powerful Soviet Black Sea Fleet which heavily outnumbered Axis naval forces in the Black Sea.
- **47th Division -> Empire of Japan** (`sentence`): On 13 June 1944, a 12th detachment comprising three infantry battalions and mountain artillery battalion was separated from the 47th division and sent to Luzon, where it was expanded to the 58th Independent Mixed Brigade and fought in Battle of Luzon until surrender of Japan 15 August 1945.
- **44th Division -> Empire of Japan** (`sentence`): The surrender of Japan on 15 August 1945 had happened before the 44th Division could engage with the enemy.
- **Pećanac Chetniks -> Government of National Salvation** (`multi_sentence`): During World War II, the Pećanac Chetniks, also known as the Black Chetniks, were a Nazi collaborationist Chetnik irregular military force which operated in the German-occupied territory of Serbia under the leadership of vojvoda Kosta Pećanac. They were loyal to the Government of National Salvation, the German-backed Serbian puppet government, and actively collaborated with Nazi Germany and its military.
- **NMS Regina Maria -> Soviet Union** (`multi_sentence`): NMS Regina Maria was the second and last of the two Regele Ferdinand-class destroyers built in Italy for the Romanian Navy in the late 1920s. After the Axis invasion of the Soviet Union on 22 June 1941 (Operation Barbarossa), she took part in the Raid on Constanța a few days later and may have damaged a Soviet destroyer leader during the battle.

## Missing-span examples

- Q10457634 66th Division -> Q188712 Empire of Japan
- Q10572199 German General Staff -> Q7318 Nazi Germany
- Q108666425 Lötzen Infantry Brigade -> Q7318 Nazi Germany
- Q1118508 Ambra -> Q172579 Kingdom of Italy
- Q1130395 Come and See -> Q15180 Soviet Union
- Q113656063 Curt Bruns -> Q7318 Nazi Germany
- Q1141598 101st SS Heavy Panzer Battalion -> Q7318 Nazi Germany
- Q115517 61st Division -> Q188712 Empire of Japan
- Q11602255 252 Air Group -> Q188712 Empire of Japan
- Q116093 65th Division -> Q188712 Empire of Japan

## Files

- `country_reference_eda/resolved_relations.csv`
- `country_reference_eda/unresolved_relations.csv`
- `country_reference_eda/summary.json`
