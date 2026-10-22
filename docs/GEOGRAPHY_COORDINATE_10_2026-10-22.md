# Geography: Wikidata coordinates, ten-input test

## Result

The same ten frozen inputs retain **three geometries and seven unresolved
locations**. There are **no additional accepted geometries** and no selected
Wikidata Point fallback. The production model, graph and identity assignments
were not changed. This is a bounded retrieval/context/fallback test, not a
complete new gazetteer search or a production selector release.

The three retained objects are London's Point, Java's MultiPolygon and the
previously approved approximate Hoosick Falls village Polygon.

## Method

Apply population S2T section 9.3 and the dated coordinate approval in
`GEOCODING_HIGH_LEVEL_PROCESS.md`:

1. Preserve the same ten IDs, order and previous accepted geometries.
2. Reuse matched-input Wikidata records. For unresolved inputs, inspect explicit
   saved WHG Wikidata links with an existing exact name/recorded alias. These
   are candidate records, not new assignments. Never reuse superseded
   `previous_place_id` values as input evidence.
3. Reuse the agreed BigQuery snapshot, `2026-10-18T18:45:19.304197+00:00`.
   London and Java have matched-input P625 statements. Tinian Town and Sunharon
   Bay have candidate-only P625 statements in an existing cached query. There
   was no new BigQuery request or live Wikidata retrieval.
4. Request Nominatim reverse results at these four original coordinates, with
   names, tags, address and full geometry. Use the API's default detail level;
   do not add a search radius, nearest-acceptance rule or distance threshold.
   This tests coordinate-guided retrieval, not every Nominatim query strategy.
5. Store returned objects as context/candidates. Check exact source-QID
   agreement and geometry coverage. Compare original GeoNames coordinates
   through existing exact aliases or Wikidata P1566 links. Distances are
   diagnostics, not identity acceptance thresholds. Records can share an
   upstream gazetteer and are not assumed to be independent confirmation.
6. Use an unchanged `Point(longitude, latitude)` only when input identity is
   supported and no supported other geometry exists. Existing identity gates
   remain in force. A candidate's own coordinate cannot prove that Daniel
   meant that candidate. In this sample no additional input passes this gate.

An existing supported geometry takes priority over the coordinate fallback.
Thus Hoosick Falls does not require another coordinate retrieval. Candidate
discovery is deliberately limited to saved links and approved exact aliases;
the test does not establish that other places lack Wikidata coordinates.

## Per-input findings

| Input | Result | Coordinate test and remaining issue |
|---|---|---|
| London | Retain accepted Point | Matched Q84 coordinate retrieved Charing Cross road. The nearest road is not London's geometry. Existing accepted source Point retained. |
| Hoosick Falls | Retain approximate village Polygon | Supported 3.847 km² local polygon already available. No coordinate fallback needed; SYN ID unchanged. |
| Java | Retain accepted MultiPolygon | Matched Q3757 coordinate retrieved an unnamed road in Central Java. Existing island geometry retained. |
| Tinian Town | Unresolved | Candidate Q101003545 has P625 and P1566=4041558. Its coordinate is 16.36 m from the saved GeoNames point. Reverse returned an unnamed road in San Jose (Tinian). The source-record agreement does not supply the missing independent input-parent evidence. |
| Sunharon Bay | Unresolved | Candidate Q101048967 has P625 and P1566=4041645. Its coordinate is 5.45 m from the linked GeoNames anchorage point. Reverse returned Marpo Heights suburb. Bay/anchorage interpretation and input identity remain unconfirmed; suburb geometry rejected. |
| Piva Yoke | Unresolved | No eligible saved exact-alias Wikidata candidate link. River/settlement candidates do not establish the fighter strip. |
| Crabbs Peninsula | Unresolved | Existing candidate spelling is Crabs Peninsula. No new fuzzy-name acceptance or parent rule is introduced. |
| Pocatello Army Air Base | Unresolved | Saved historical Air Field name/type is still not an accepted input match. No eligible saved exact-alias Wikidata coordinate link. |
| Donbaik | Unresolved | Exact GeoNames alias exists; independent input-parent/type evidence remains missing. No eligible saved Wikidata coordinate link in this test. |
| `.` | Unresolved | Original punctuation-only input preserved. No fabricated place or coordinate. |

All four reverse results lacked the requested Wikidata QID, and none of their
returned geometries covered the original coordinate. This is not an API error:
Nominatim documents that reverse lookup returns the closest suitable indexed
object, which can be unrelated to the intended feature. See the
[official reverse documentation](https://nominatim.org/release-docs/latest/api/Reverse/).
The test uses one thread, an identifying User-Agent, cache storage and a
1.1-second pause after new requests, within the
[public service policy](https://operations.osmfoundation.org/policies/nominatim/).

## Verification and artifacts

- Initial run: 10 inputs; four new Nominatim requests; three retained geometries;
  seven unresolved; zero new fallback Points.
- Replay: same decisions and exact geometries; all four responses reused;
  zero new requests.
- Nine focused tests passed, including fallback identity/source-priority gates,
  exact coordinate preservation, conflicting coordinates, non-Earth rejection,
  existing containment/context checks and frozen-sample behavior. Ruff passed.
- All 69 protected hashes in the replay and seven output hashes passed readback.
  IDs/order and all three geometries match the previous test exactly.
- Shapely objects round-trip exactly through GeoParquet. References remain in
  the sample model/audit, not graph JSON.

Code: `GG_Data/pipeline/geography_coordinate_sample.py` and its focused test.
Original output: `GG_Data/pipeline/outputs/geography_coordinate_10_20261022/`.
Final cached replay:
`GG_Data/pipeline/outputs/geography_coordinate_10_20261022_cached_replay/`.
Each contains source responses, `audit.json`, `verification.json`, progress and
`geometries.parquet`. These ignored local outputs are not protected by Git.

Reproduce without additional requests in a **new** output directory:

```powershell
C:\Users\User\anaconda3\python.exe -B -m GG_Data.pipeline.geography_coordinate_sample --base GG_Data/pipeline/outputs/rebuild_page_scope_20261022 --prior GG_Data/pipeline/outputs/geography_local_polygon_10_20261022 --candidate-cache GG_Data/pipeline/outputs/wikidata_full_cache/1c8841ce530789458d059e9f8b92254f0fb0835e46a32301852d69b8aa00a8ce.json.gz --request-cache GG_Data/pipeline/outputs/geography_coordinate_10_20261022/sources --output GG_Data/pipeline/outputs/new_coordinate_test
```

## Interpretation

Coordinates add useful source/context evidence here, but do not repair the
unresolved identity matches. The unchanged-Point fallback is implemented and
code-tested; no real unresolved input qualified for it in these ten examples.
No new distance, alias, feature-type, parent or identity acceptance rule was
added. A wider candidate-discovery or identity-policy change requires separate
agreement before a new run.
