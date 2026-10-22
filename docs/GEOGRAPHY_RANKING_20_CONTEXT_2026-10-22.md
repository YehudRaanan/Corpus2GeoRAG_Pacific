# Geography: context coordinates and removal of the name/QID veto

22 October 2026. Status: **test completed; further runs stopped for owner discussion**. No production assignments.

## Result

The same twenty inputs were rerun, using only saved source responses. Eighteen top-candidate geometry proposals were produced versus thirteen previously; two inputs still lack a proposal. This is not eighteen successful geolocations. Ten previous source objects remain selected, three previous selections changed, and five previously unresolved inputs acquired proposals. Several new or changed proposals are wrong or unsuitable. No model row or input ID changed.

Pocatello now selects the Pocatello Regional Airport polygon. It contains the saved historical airfield GeoNames point 6354207, and the original input supports Idaho and airport use. This is useful approximate site evidence, not an established WWII boundary.

## All twenty outcomes

| Set | Input | Previous proposal | Current proposal | Score | Finding |
|---|---|---|---|---:|---|
| Current | London | London | London | 77 | Same source object as previous test; no new identity validation. |
| Current | Hoosick Falls | Village of Hoosick Falls | Village of Hoosick Falls | 67 | Same source object as previous test; no new identity validation. |
| Current | Java | Java | Java | 92 | Same source object as previous test; no new identity validation. |
| Current | Tinian Town | JP Tinian Town pre-WW2 | JP Tinian Town pre-WW2 | 35 | Same source object as previous test; no new identity validation. |
| Current | Sunharon Bay | Sunharonská zátoka | Tinian Harbor - Organized Anchorage | 35 | Changed to nearby harbour Point; target identity unconfirmed. Previous Wikidata Point displaced by source-first fallback order. |
| Current | Piva Yoke | Unresolved | Piva River | 3 | New river Point, not the fighter strip. Page context alone; not a confirmed airfield geometry. |
| Current | Crabbs Peninsula | Crabs Peninsula | Crabs Peninsula | 33 | Same source object as previous test; no new identity validation. |
| Current | Pocatello Army Air Base | Unresolved | Pocatello Regional Airport | 13 | Useful new approximate site polygon: contains historical GeoNames point 6354207 and matches Idaho/airport context. No proof of exact WWII boundary. |
| Current | Donbaik | Done Paik | Done Paik | 10 | Same weak proposal: recorded Done Paik alias plus page context. Not an accuracy validation. |
| Current | . | Unresolved | Unresolved | — | No candidate geometry; punctuation exclusion retained. |
| New | Panaon | Panaon | Camp Lumot | 25 | Changed to a campsite 347.72 m from QID coordinates; nearby feature does not identify the island. |
| New | England | England | England | 85 | Same source object as previous test; no new identity validation. |
| New | Portuguese Macau | 葡属澳门 | 美的閣 Mei Tek Kok Edifício | 30 | Changed to a building containing QID coordinates; unsuitable extent for the historical territory. |
| New | Bora Bora | Bora-Bora | Bora-Bora | 40 | Same source object as previous test; no new identity validation. |
| New | Lebanon | لبنان | لبنان | 82 | Same source object as previous test; no new identity validation. |
| New | of Borneo | Unresolved | J F Burns Elementary School | 0 | Incorrect US school selection with zero evidence points. Do not accept. |
| New | Chosŏn Volunteer Cemetery | Unresolved | Hanna Cemetery | 10 | Incorrect US cemetery selection. Context points come only from AS, a US alias that matched the word as. |
| New | Dongbiandao | Unresolved | Dunvilla Post Office (historical) | 0 | Incorrect US post-office selection with zero evidence points. Do not accept. |
| New | État des Alaouites | Unresolved | Unresolved | — | Identity candidates exist, but no eligible source geometry was loaded. |
| New | Mayu Range | Mayu Taungdan | Mayu Taungdan | 10 | Same weak proposal: recorded Mayu Range alias plus page context. Not an accuracy validation. |

## Exact changes tested

- Removed the selection condition requiring a positive name score, positive QID score or a prior geometry. Explicit different-QID conflicts, incompatible dates, punctuation and reverse-road exclusions remain.
- Reused existing input-local GeoNames Point hypotheses. A containing source Polygon/MultiPolygon can receive the existing geographic-context maximum of 10. The total context weight remains 15 with historical date support. Wikidata keeps its separate coordinate component with maximum 30. No additional distance threshold, new source or identity assignment was added.
- GeoNames coordinate hypotheses remain candidate-derived and are listed with their source IDs and receipts. A Point does not validate itself. Containment is location support, not independent identity proof.
- Source geometry still precedes a last-resort Wikidata Point. No minimum total score was introduced. The audit deliberately exposes zero-score and weak selections rather than hiding them as successes.

## Problems found and stop reason

1. Removing the veto without another evidence condition permits a zero-score unrelated result: of Borneo selects J F Burns Elementary School in the US, and Dongbiandao selects Dunvilla Post Office (historical) in the US.
2. The cemetery gets ten false context points because the GeoNames US alias AS matches the ordinary word as. Literal matching of every country alias is not reliable geographic context.
3. Source-first fallback order displaces a direct-QID Point even when the retrieved feature is inappropriate: Panaon selects a nearby campsite, and Portuguese Macau selects a building containing the coordinate. Containment alone does not establish the correct feature or geographic extent. Sunharon Bay similarly switches to a nearby harbour Point.
4. Piva Yoke selects a river based on three page-context points. This does not identify the fighter strip. It could be local search context but is not an established strip position.

These findings are retained without new filters or manual corrections. The owner must discuss the next rule before another run. The eighteen proposal geometries are an experimental failed-test artifact, not model population or accepted matches. A general solution needs meaningful geographic evidence, control of ambiguous parent aliases, and feature/extent compatibility while keeping name matching optional. No new numerical threshold or feature mapping was approved or implemented here.

## Artifacts and checks

`GG_Data/pipeline/outputs/geography_ranking_20_context_20261022/` contains parameters, unchanged twenty inputs, candidate records, geographic context checks, full rankings, receipts, comparison.json and experimental proposed_geometries.parquet. The runner is `GG_Data/pipeline/geography_ranking_sample.py`.

Elapsed computation: 23.52 seconds; zero new requests, sixteen saved responses reused. The two focused tests passed; Ruff passed and Black formatted the changed test. Geometry round-trip verification passed for all eighteen proposals. All baseline output hashes were rechecked and the twenty input records match exactly. Main model and identity assignments remain unchanged.

Production S2T rules are not promoted by this test. The previous diagnostic results remain available. Code/documents can be protected by a Git commit; ignored data outputs are local only.
