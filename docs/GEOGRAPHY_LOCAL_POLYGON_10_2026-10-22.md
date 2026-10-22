# Geography: broader local polygons, ten-input test

## Result

Status: `VERIFIED_CACHED_TEN_LOCAL_POLYGON_TEST`.

The same ten original inputs produced **two retained accepted geometries, one
new approximate local polygon, and seven unresolved results**. The baseline was
two accepted and eight unresolved. This is a bounded cached-evidence test, not
a production release or a measured identity-accuracy improvement.

The owner approved the test rule on 22 October 2026: select the smallest
supported existing local polygon covering the plausible locations, mark it
approximate, and exclude country-wide and larger approximations. The minimum
is among supported retrieved polygons, not every polygon in all sources.

## Method and limits

1. Freeze the original ten IDs and their order. Retain the two verified
   exact-QID geometries without changing their coordinates.
2. Reuse checksum-pinned source responses and the prior independently checked
   parent evidence. A candidate's own address or a Wikipedia page title alone
   does not establish the input's parent area.
3. For unresolved inputs, keep recorded exact-name/alias candidates supported
   by that parent evidence. Do not introduce fuzzy-name acceptance, historical
   name equivalences, new QIDs or new place extraction.
4. Compare complete original-source geometries and GeoNames reference points.
   A polygon must cover every retained plausible location. No bounding box,
   buffer, union or generated shape is used as an assigned geometry.
5. Require explicit local administrative metadata in this test. The accepted
   example is an OSM village boundary, admin level 8, also identified as the
   town in its address. Country, larger and unknown scope cannot pass. Other
   polygon classes are not classified or accepted by this sample helper.
6. Choose the smallest eligible area using WGS84 geodesic area; use the existing
   stable source-ID ordering for a remaining tie. Preserve date precision and
   undated-source eligibility under the existing policy.
7. Save the original geometry as Shapely/WKB in GeoParquet. Label approximation
   separately from identity status in the sample audit. Keep every input ID,
   including synthetic IDs, unchanged.

All ten inputs were evaluated. No new source requests were made. The test does
not establish that no suitable polygon exists elsewhere for the seven unresolved
inputs. No broader parent search, type expansion, alias expansion, or new context
extraction was approved or performed here. The numerical maximum extent and a
general production representation for approximation remain undefined.

## Per-input findings

| Input | Result | Geometry or remaining reason |
|---|---|---|
| London | Retained accepted | Exact-QID OSM point `N2091040477`; unchanged. |
| Hoosick Falls | **Approximate polygon** | OSM village boundary `relation:175845`, **3.847 km²**. It covers the GeoNames settlement point and OSM waterfall, as well as the village geometry itself. New York was already independently checked. |
| Java | Retained accepted | Exact-QID OSM island MultiPolygon `R9444963`; unchanged. |
| Tinian Town | Unresolved | Historical name candidate exists, but independently verified parent evidence and a supported local source polygon are missing in this test. |
| Sunharon Bay | Unresolved | Bay/anchorage interpretation and parent evidence remain unsupported; no broader source polygon was established. |
| Piva Yoke | Unresolved | Saved Piva river/settlement records do not establish the fighter strip; no supported parent polygon. |
| Crabbs Peninsula | Unresolved | Crabs Peninsula is a useful spelling candidate, but the exact-alias and independently checked Antigua evidence gaps remain. A broader polygon does not by itself resolve them. |
| Pocatello Army Air Base | Unresolved | Idaho is supported, but the saved historical Air Field name is not an accepted alias of the input. No supported original local polygon in saved searches. |
| Donbaik | Unresolved | The Done Paik record has the exact Donbaik alias, but independent input-parent evidence remains missing. No local polygon was established. |
| `.` | Unresolved | Punctuation-only input; no geographic name. |

Hoosick Falls keeps `SYN_7ff525261d2b6a91bff0ef42`. The selected boundary's own
QID is evidence about that source object; it is not assigned to Daniel's entity.
The approximate polygon does not establish whether Daniel meant the settlement
or waterfall, or prove its exact WWII footprint. The OSM source is undated under
the existing eligibility rule. A country-sized fallback was not used.

## Verification and artifacts

- Nine focused tests passed, including minimum area, full containment, country
  and larger scope exclusion, unknown metadata, and prior context diagnostics.
- Ruff passed. All ten IDs and their order match the frozen sample.
- All 56 protected source/model hashes remain unchanged.
- The three saved Shapely objects are valid and nonempty; GeoParquet readback
  reproduces each object exactly, including the two retained geometries.
- Output file checksums passed. Main model, identity assignments and graph
  exports are unchanged. No production selector was replaced.

Code: `GG_Data/pipeline/geography_local_polygon_sample.py`.

Local ignored output: `GG_Data/pipeline/outputs/geography_local_polygon_10_20261022/`:
`audit.json`, `verification.json`, `geometries.parquet`. Geometry references are
in the sample audit, not exported into graph JSON. These local artifacts are not
protected by a Git commit or an off-device backup.

Reproduce in a **new** output directory:

```powershell
C:\Users\User\anaconda3\python.exe -B -m GG_Data.pipeline.geography_local_polygon_sample --base GG_Data/pipeline/outputs/rebuild_page_scope_20261022 --output GG_Data/pipeline/outputs/new_local_polygon_test
```
