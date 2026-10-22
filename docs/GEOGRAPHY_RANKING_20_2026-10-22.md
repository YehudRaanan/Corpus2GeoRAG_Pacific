# Geography ranking: twenty-input experiment, 22 October 2026

Status: completed diagnostic; no production assignments. The owner requested the ten existing examples plus ten new examples. The new ten are the first five QID and first five synthetic inputs from the previously frozen random comparison arms, not a fresh population-wide random draw. All twenty inputs were retained.

## Result

13 geometry proposals; 7 without an eligible geometry. Original ten: 7 proposals, compared with 5 in the previous coordinate test. New ten: 6 proposals. These counts measure candidate coverage, not verified accuracy. Zero IDs, matching assignments or main-model rows changed.

| Set | Input | Proposed source and object | Shape | Score (QID / coordinate / context / name / type) |
|---|---|---|---|---|
| Current | London | OpenHistoricalMap: London (N2091040477) | Point | 77 (45 / 25 / 0 / 7 / 0) |
| Current | Hoosick Falls | OpenStreetMap via Nominatim: Village of Hoosick Falls (relation:175845) | Polygon | 67 (20 / 30 / 10 / 7 / 0) |
| Current | Java | OpenStreetMap: Java (R9444963) | MultiPolygon | 92 (45 / 30 / 10 / 7 / 0) |
| Current | Tinian Town | GeoNames: JP Tinian Town pre-WW2 (4041558) | Point | 35 (0 / 25 / 0 / 7 / 3) |
| Current | Sunharon Bay | Wikidata: Sunharonská zátoka (Q101048967$09d74a13-4ed1-4530-9a89-a9dede7b1449) | Point | 57 (20 / 30 / 0 / 7 / 0) |
| Current | Piva Yoke | Unresolved | — | — |
| Current | Crabbs Peninsula | GeoNames: Crabs Peninsula (3576295) | Point | 33 (0 / 25 / 0 / 5 / 3) |
| Current | Pocatello Army Air Base | Unresolved | — | — |
| Current | Donbaik | GeoNames: Done Paik (1326299) | Point | 10 (0 / 0 / 3 / 7 / 0) |
| Current | . | Unresolved | — | — |
| New | Panaon | Wikidata: Panaon (Q523781$28531061-4e4d-2374-c125-9d00aa70c641) | Point | 82 (45 / 30 / 0 / 7 / 0) |
| New | England | OpenStreetMap: England (relation:58447) | Polygon | 85 (45 / 30 / 3 / 7 / 0) |
| New | Portuguese Macau | Wikidata: 葡属澳门 (Q3916279$adfb390e-487e-9ab7-5511-4566d5cef9f1) | Point | 92 (45 / 30 / 10 / 7 / 0) |
| New | Bora Bora | OpenStreetMap: Bora-Bora (relation:19251452) | MultiPolygon | 40 (0 / 30 / 3 / 7 / 0) |
| New | Lebanon | OpenStreetMap: لبنان (relation:184843) | Polygon | 82 (45 / 30 / 0 / 7 / 0) |
| New | of Borneo | Unresolved | — | — |
| New | Chosŏn Volunteer Cemetery | Unresolved | — | — |
| New | Dongbiandao | Unresolved | — | — |
| New | État des Alaouites | Unresolved | — | — |
| New | Mayu Range | GeoNames: Mayu Taungdan (1309910) | Point | 10 (0 / 0 / 3 / 7 / 0) |

## Ranking applied

- Weights: QID 45, coordinate 30, context 15, name 7, feature type 3. Missing evidence scores zero; weights are not redistributed. A synthetic input can receive 20 QID points from a saved candidate link; its input ID remains synthetic.
- Coordinate score: containment or exact point 30; within 1 km 25; within 5 km 15; within 20 km 5; otherwise 0. Distance is measured to the actual source geometry. Candidate-only coordinates remain explicitly candidate-derived, not independent identity proof.
- Geographic context: strongest supported parent in the immediate original text 10, wider original text 7, page title or same-page location context 3. Supplied compatible historical dates add 5. No dates means no historical points.
- Name: exact recorded alias 7, existing Unicode trigram similarity at least 0.8 gives 5. Feature type: specific compatibility 3, the supported broader military-installation case 2.
- Source geometries are ranked first. An unchanged Wikidata P625 Point is considered only when no eligible source geometry remains. Therefore the proposed geometry can score less than its fallback Point.
- Roads returned by reverse geocoding remain context, not target geometry. Explicit different-QID conflicts, incompatible supplied dates and punctuation-only names are exposed as exclusions.

## Findings and remaining limits

- London is Q84 in London, England; the former Ohio identity is not reused. Java retains its island MultiPolygon. Hoosick Falls selects the village polygon. Crabbs Peninsula selects the GeoNames Crabs Peninsula Point supported by the nearby candidate coordinate; Donbaik selects the recorded Done Paik alias.
- Piva Yoke: the collected river/settlement candidates do not identify the airstrip. Pocatello: the airport polygon scores 13 (context 10, feature 3), but the prototype eligibility gate requires QID/name support or a previously selected geometry. This gate is separate from ranking and must be discussed before a wider run; no new acceptance rule was introduced.
- The other unresolved inputs are punctuation (.), of Borneo, Chosŏn Volunteer Cemetery, Dongbiandao, and État des Alaouites. The latter has an exact-alias Alawite State candidate and saved OHM relation reference, but no eligible shape was loaded. This is incomplete geometry retrieval, not evidence that geometry does not exist.
- Donbaik and Mayu Range each score only 10: alias 7 and page context 3. They are proposals with weak evidence, not high-confidence accepted matches.
- QID and coordinate agreement dominate the score but can be dependent evidence. A P625 Point compared with itself receives 30; this is not a measured accuracy probability.
- This bounded adapter does not yet apply P625 stated uncertainty to distance bands. Context matching uses literal saved parent labels; feature parsing remains limited to existing supported families. A missing score can mean missing adapter coverage.
- New-source retrieval covered saved WHG/GeoNames records, OSM QID lookup, Nominatim name search and coordinate reverse lookup. This is not exhaustive retrieval across every source; no claim is made that absent candidates do not exist.
- Country-wide or larger approximations are not selected for a local place. Lebanon is the actual input country, so its own geometry is retained as a direct match. Present-day country footprints are not proof of 1941–1945 boundaries.

## Reproducibility and verification

Runner: `GG_Data/pipeline/geography_ranking_sample.py`. Parameters, frozen inputs, complete rankings, source receipts, component evidence, coordinates and experimental GeoParquet are stored under `GG_Data/pipeline/outputs/geography_ranking_20_20261022_corrected/`.

The first pass made 16 saved Nominatim requests and took 42.9 seconds. It was superseded after fixing source-Point fallback order and loading omitted saved GeoNames aliases. The corrected repeat took 23.82 seconds, made zero new requests and reused all 16 receipts. This is cached experiment runtime, not a full-pipeline estimate. Prior model/source hashes remained unchanged; geometry round-trip verification passed.

The prototype still needs an agreed geometry-eligibility rule for context-only candidates before general deployment. The experiment does not change production S2T decisions. Raw output files are ignored by Git and are not protected by a code commit.
