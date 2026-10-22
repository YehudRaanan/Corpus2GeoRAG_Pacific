# Geography: 100 new inputs, 22 October 2026

## Verified result

Completed the separate 100-input experiment: **97 selected geometries, 3 inputs without retrieved usable geometry, and zero inputs with available geometry left unresolved**. This is retrieval/selection coverage, not 97 verified correct locations. Main-model rows, upstream matching decisions and input QID/SYN IDs remain unchanged. No new entities were created and no production Geography rows were populated.

The frozen sample contains 100 distinct existing LOC inputs: **73 QID and 27 synthetic** inputs, sampled without replacement from 1,241 remaining LOC targets in the existing 10K POC. Seed: `20261022100`. Overlap with the previous twenty: **zero**. All source pages are English; Japanese-page coverage was not tested. Selection coverage is 73/73 QID inputs and 24/27 synthetic inputs.

| Selected source | Inputs |
|---|---:|
| OpenStreetMap | 42 |
| OpenHistoricalMap | 13 |
| Wikidata | 36 |
| GeoNames | 6 |
| No retrieved geometry | 3 |

Storage contains **38 Polygons, 12 MultiPolygons, 46 Points and 1 LineString**. GeoParquet preserves the selected native geometries in EPSG:4326 and restores their Shapely objects exactly. No generated buffer or invented geometry was used.

## Applied rules and approvals

The existing 45/30/15/7/3 ranking uses QID agreement, Wikidata coordinates, context, name and feature type. Stable score ties prefer a polygon, then source and source-object ID. Every input with retrieved valid nonempty geometry receives a selection, including low/zero-score candidates; uncertainty remains visible. Wikidata Points compete by score. No source-first rule overrides a higher score.

Four inputs have multiple P625 statements: Omni Shoreham Hotel (Q7090343), Shanghai (Q8686), Aigun (Q404795) and Lesno (Q4977506). The owner approved retaining every non-deprecated coordinate statement separately, preserving its native values, rank, precision and statement ID. Deprecated statements are excluded; coordinates are not averaged.

The first 100-query WHG request returned HTTP 400 and the run stopped for consultation. The owner approved splitting the unchanged queries into batches of at most 50, caching each complete response and validating requested query IDs before combining. This follows the [official WHG batching limit](https://docs.whgazetteer.org/content/technical/apis.html#batching-quotas-and-retries). Both saved query arms then completed: 100/100 responses per arm. This was a retrieval correction; source scope, sample and ranking did not change.

The agreed exact-QID inventories contain 96 OHM and 86 OSM objects across the 73 QID inputs. Their native geometry is obtained through the respective Nominatim lookup service in batches of at most 50 objects. The final pass includes OHM geometry as ranking candidates, rather than treating its object IDs alone as geometry. It reuses saved OSM, name and coordinate-context responses.

## Remaining gaps and weak selections

| Input without retrieved geometry | Daniel source page | Existing clue / coverage limitation |
|---|---|---|
| Galoeng Galoeng | Dutch East Indies | WHG returns Galong-Galong and other name candidates, including source IDs. Those candidate IDs did not yield a loaded native geometry in this bounded run. Local GeoNames archives do not cover every candidate country. |
| Buna-Gona | New Guinea campaign | WHG returns Battle of Buna-Gona and other, partly unrelated candidates. No usable native geometry was materialized for this input. |
| Konkoita | Death Railway | WHG returns the exact named Wikidata candidate Q110913948 and other records. This run did not materialize a native geometry/coordinate from those results. |

These are retrieval/materialization gaps, not proof that the places or geometries are absent from external sources. The current runner does not dereference every WHG candidate source ID into a new native-record lookup. Extending that acquisition step is separate work; no such new run was started.

Three **zero-score** selections were retained under the owner's always-select rule:

| Daniel input | Selected source object | Concern |
|---|---|---|
| Dutch Borneo | OpenStreetMap Borneostraat, way:6752237 | No scored support for this replacement location. |
| Tohiti | GeoNames Ottville, 4905042 | No scored support for this replacement location. |
| Beijing-Hankou railway | GeoNames Puuhinahina Lookout, 5853132 | No scored support for this replacement location. |

These selections are not presented as correct or nearby. Scores distinguish the available candidates; the approved selection rule has no minimum score. Their source geometry, score components and uncertainty remain in the audit and CSV.

Including OHM native geometries changed 13 selections compared with the completed OSM/Wikidata/GeoNames pass. Examples include British Ceylon, French Algeria, Karafuto Prefecture and Fort Randall. The final result has 50 area geometries versus 42 in that intermediate pass. Both outputs are preserved.

## Artifacts, timing and verification

Root: `GG_Data/pipeline/outputs/geography_ranking_100_new_20261022/`.

- `sample.json`: immutable 100-input sample.
- `preflight.json`: historical initial stop and protected-input hashes; retained unchanged.
- `comparison/`: complete cached WHG query arms and exact-QID OHM/OSM inventories.
- `ranking/`: completed intermediate pass, 183 new requests, 487.874 seconds.
- `ranking_with_historical/`: **final** result, 185 request receipts, including 183 reused and 2 new OHM requests; 174.971 seconds for this pass.
- `ranking_with_historical/results.csv`: all 100 inputs, selected source/geometry, component scores, uncertainty, candidate and coordinate counts.
- `ranking_with_historical/proposed_geometries.parquet`: 97 selected native geometries.
- `ranking_with_historical/audit.json`, `candidates.json`, `coordinates.json`, `evidence.json`, `parameters.json`: complete ranking evidence and protected-source hashes.
- `ranking_with_historical/verification.json`: output checksums, source/shape counts, exact geometry round-trip check and unchanged-model flags.
- Root `verification.json`: independent final check of all output hashes, frozen/protected input hashes, 100 unique CSV rows, matching selected geometry IDs, EPSG:4326, 97 nonempty geometry rows and zero overlap with the previous twenty.

WHG/inventory retrieval took 95.078 seconds. These stage times exclude consultation waits and are not a production runtime estimate. Eight focused comparison/ranking tests, formatting and lint checks cover the current code. The actual 100-input run additionally verifies serialized geometry and input preservation.

To replay the ranking with the frozen comparison and existing request cache:

```powershell
C:\Users\User\anaconda3\python.exe -m GG_Data.pipeline.geography_ranking_sample --comparison GG_Data/pipeline/outputs/geography_ranking_100_new_20261022/comparison --request-cache GG_Data/pipeline/outputs/geography_ranking_100_new_20261022/ranking_with_historical --output <new-output-directory>
```

Run from `D:\Projects\GeoAI`. This replay uses exact matching cached request URLs/parameters. Missing cached requests can still require the agreed services; no new retrieval has been launched by this report.

Code/document checkpoints are local only. Generated source responses and results are ignored local artifacts; no off-device backup is claimed. Full-model Geography population and Agent integration remain outside this test.
