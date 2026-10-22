# Geography: always select an available geometry

22 October 2026. Latest owner instruction: whenever one or more geometry options are available for an input, select one using the ranking. Uncertain identity or low confidence must not turn an available location into an unresolved result.

## Rule and scope

- Select the highest-ranked nonempty valid source geometry among the input-local retrieved candidates. Existing weights remain QID 45, Wikidata coordinate 30, context 15, name 7 and feature type 3.
- Keep stable score ties: polygon first, then source and source-object ID. A zero score is not an exclusion threshold.
- Wikidata Points participate in the same ranking. The earlier source-first/last-resort-only priority no longer overrides a higher score.
- Keep name, QID, date and feature uncertainty as metadata, not separate selection vetoes. A different source QID never changes the original entity ID or its matching status.
- Leave geometry unresolved only when no usable geometry option has been retrieved. Invalid geometry or broken source records remain technical data problems; no geometry is fabricated.
- The business preference remains a useful approximate location over no location. The selected Point or local geometry is not a claim of exact historical boundaries.
- This implementation/test covers the same frozen twenty inputs. Main model population, final JSON and entity IDs are unchanged. No new sources or entities were added.

## Verified result

18 of 20 inputs have loaded geometry options; all 18 received a selected geometry in the sample output. Two have no loaded geometry: punctuation (.) and État des Alaouites. Zero inputs with an available geometry were left unresolved. This is coverage, not measured accuracy.

| Set | Input | Selected object | Source | Shape | Score |
|---|---|---|---|---|---:|
| Current | London | London | Wikidata | Point | 82 |
| Current | Hoosick Falls | Village of Hoosick Falls | OpenStreetMap via Nominatim | Polygon | 67 |
| Current | Java | Java | OpenStreetMap | MultiPolygon | 92 |
| Current | Tinian Town | Tinian Town | Wikidata | Point | 57 |
| Current | Sunharon Bay | Sunharonská zátoka | Wikidata | Point | 57 |
| Current | Piva Yoke | Piva River | GeoNames | Point | 3 |
| Current | Crabbs Peninsula | Crabs Peninsula | Wikidata | Point | 55 |
| Current | Pocatello Army Air Base | Pocatello Regional Airport | OpenStreetMap | Polygon | 13 |
| Current | Donbaik | Done Paik | GeoNames | Point | 10 |
| Current | . | No loaded geometry | — | — | — |
| New | Panaon | Panaon | Wikidata | Point | 82 |
| New | England | England | OpenStreetMap | Polygon | 85 |
| New | Portuguese Macau | 葡属澳门 | Wikidata | Point | 92 |
| New | Bora Bora | 波拉波拉岛 | Wikidata | Point | 92 |
| New | Lebanon | لبنان | OpenStreetMap | Polygon | 82 |
| New | of Borneo | J F Burns Elementary School | GeoNames | Point | 0 |
| New | Chosŏn Volunteer Cemetery | Hanna Cemetery | GeoNames | Point | 10 |
| New | Dongbiandao | Dunvilla Post Office (historical) | GeoNames | Point | 0 |
| New | État des Alaouites | No loaded geometry | — | — | — |
| New | Mayu Range | Mayu Taungdan | GeoNames | Point | 10 |

## Requested examples and Borneo context

- Panaon selects its original QID coordinate Point (82), above the nearby campsite (25). It is not left empty. Sunharon Bay selects its saved Wikidata candidate Point (57), above the nearby harbour Point (35); the synthetic input ID stays unchanged.
- Pocatello selects the airport polygon (13), containing the historical GeoNames airfield coordinate. This remains a useful approximate site location.
- Daniel extracted the exact span of Borneo from a publication citation to Prefectures Apostolic of Borneo in the British Borneo page (enwiki page 5113347). Existing same-page LOC names include Borneo, Brunei, Colony of Labuan, Jesselton and Sabah. The immediate text is a Catholic Encyclopedia citation with a New York publisher; that is publication context, not a Borneo location in the US.
- Saved WHG results include Borneo Q36117, Borneo GN 1648148 and the Borneo/Kalimantan OSM relation 3986083. Those records have no loaded geometry in this experiment. Loaded options include the US school and several Nominatim names containing Borneo; all score zero under the current full-span name/context adapter. Stable tie order selects the GeoNames school. This location is retained with its zero score under the owner rule. Improving candidate geometry retrieval/ranking is separate work; the output is not silently emptied or manually replaced.
- The known ambiguous AS country alias still contributes context to the cemetery result. This test does not introduce a new alias filter. Original evidence and all scores remain visible for later ranking improvement.

## Artifacts and verification

`GG_Data/pipeline/outputs/geography_ranking_20_always_select_20261022/` contains the twenty inputs, complete candidate rankings, source receipts, original coordinate evidence, uncertainty flags and proposed_geometries.parquet with all eighteen selected sample geometries. selection_invariant.json verifies that every input with an available geometry has its highest-ranked available option selected.

Runtime: 24.34 seconds; zero new requests and sixteen saved responses reused. The two focused tests passed, Ruff passed, and Black confirmed formatting. Geometry round-trip verification passed. Original twenty records and all previous output hashes remain unchanged. Source and test data outputs are ignored by Git; a code commit does not back them up.
