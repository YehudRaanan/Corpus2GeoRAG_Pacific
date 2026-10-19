# Geo Object Extraction Method

## Status

This document records the proposed method for assigning one geographic geometry to each place entity in the WWII graph.

Policy version: `geo-object-selection-v0.5.0`
Last verified: `2026-10-13`

The method is a project policy. It does not change the source datasets.

**Delivery boundary:** Geometry is deferred from the current relation and identity handoff. The results in this document are proof of concept and audit evidence. They are not approved production geometry, and they must not be included in an Agent release until the separate geometry gate approves the source, representation, CRS, and export conversion.

**Retrieval plan update — 19 October 2026:** Use bulk downloads, BigQuery
exports, and saved references for distinct confirmed place QIDs, with API calls
for remaining gaps and required WHG reconciliation. The user accepts the older
OSM BigQuery snapshot; snapshot age does not require rejection or refresh.
Identity, place meaning, selection-date checks, and source priority remain
unchanged. This retrieval plan is documented in
[Bulk downloads and reuse](../../docs/GEOCODING_HIGH_LEVEL_PROCESS.md#bulk-downloads-and-reuse)
and has not yet been implemented as a full geocoding run.

## Output rule

- A place is identified by its Wikidata QID.
- Each place has exactly one selected geo object.
- The geo object is a Shapely geometry.
- The place-to-geometry connection has no `valid_from` or `valid_to` fields.
- Geometry type is read from the Shapely object and is not stored in a separate field.
- Wikidata coordinates and Wikidata shapes are not geometry sources.
- Wikidata is used only for the QID, names, types, aliases, and identity links.

The coordinate reference system must be stored once in the geometry table or GeoDataFrame metadata. The project CRS is still an Agent-contract decision.

## Source and quota logic

Sources are used in this order:

1. **[OpenHistoricalMap (OHM)](https://wiki.openstreetmap.org/wiki/OpenHistoricalMap/Overpass)**
   - Search for an exact `wikidata=QID` link.
   - Prefer a source geometry that represents the place on its selection date within the project period.
   - Use OHM chronology and date tags only to select the source object. Do not copy these dates to the final place-to-geometry connection.
2. **[OpenStreetMap (OSM)](https://wiki.openstreetmap.org/wiki/Wikidata)**
   - Search for an exact `wikidata=QID` link.
   - Use OSM mainly for stable physical features, current boundaries, and places missing from historical sources.
3. **[World Historical Gazetteer (WHG)](https://docs.whgazetteer.org/content/technical/apis.html), only when needed**
   - Skip WHG when OHM and OSM produce exactly one exact-QID object.
   - Query WHG when they produce no exact-QID object or more than one exact-QID object.
   - Put all required places into batches of up to 50 queries. A batch uses one daily API request.
   - Use WHG to supply reconciliation candidates and linked source records. WHG does not make the final identity decision.
   - Use the geometry and provenance of a selected original record. Do not automatically use a WHG union of several geometries.
   - Read `WHG_key` from the local `.env` file and send it in the `Authorization` header. Do not store the key in results or logs.
4. **Name and alias evidence**
   - Search WHG, [Nominatim](https://nominatim.org/release-docs/latest/api/Search/),
     or the [GeoNames country files](https://download.geonames.org/export/dump/)
     with the name, aliases, parent area, country, and place type.
   - Treat each result as a candidate. A name match alone is not sufficient for automatic acceptance.
   - Accept a unique candidate when at least one additional identity field agrees,
     such as an external identifier, feature type and parent area, or two standard
     airport codes.
5. **Specialist source or manual construction**
   - Use an appropriate public boundary or feature dataset when the first four steps fail.
   - Georeference and digitize a documented historical map when no suitable structured geometry exists.

## Project period and selection-date rule

The Pacific War project period is **1941-12-07 through 1945-09-02**, inclusive.

For each place, use the earliest related event or relation date inside this
period. When the place has no related date, use **1941-12-07**. When it has
several related dates, use the first date in the period.

For OHM and OSM date tags, a dated geometry is eligible only when its source
interval contains the selected date:

```text
start_date <= selected_date
and
end_date > selected_date, or end_date is absent
```

The end date is exclusive. If an exact-identity, type-compatible source geometry
is undated, use it. WHG is queried for the year of the selected date and includes
undated candidates. A WHG candidate must still match the required identity and
geometry meaning.

When several exact-QID candidates pass the identity, type, and selected-date
checks, select the first candidate in the project period. Use the source object
ID as a stable tie-break when candidates have the same effective first date.

The final geo object has no time attributes. The project period and the selected
date are part of the method version and audit record.

## Candidate selection

For each place:

1. Collect exact-QID objects from OHM and OSM.
2. Count these objects.
3. Derive the selection date from related events and relations; use the project start when none exists.
4. Apply the selection-date rule to every dated source object; keep undated objects eligible.
5. Skip WHG when exactly one exact-QID object exists. Query WHG when the raw count is zero or greater than one.
6. Remove candidates whose feature meaning conflicts with the place type.
7. Apply the type preference table below.
8. Select the first remaining candidate in the project period.
9. Convert the selected source geometry to Shapely.
10. Require a non-empty, valid geometry.
11. Keep the source evidence and decision status.
12. Send conflicting or weak candidates to review.

Do not union, buffer, simplify, or replace a geometry with its centroid without an explicit project rule and recorded transformation.

## Type preferences

| Place type | Preferred representation | Fallback |
|---|---|---|
| Country or administrative area | Administrative boundary | Exact-identity point |
| City or settlement | Administrative boundary | Settlement point |
| Island | Land extent | Exact-identity point |
| Atoll | Reef extent | Island or regional extent after review |
| Harbor | Harbor or water extent | Exact-identity point |
| Airfield, base, camp, or facility | Site footprint | Exact-identity point |
| River, route, or other linear place | Source line geometry | Exact-identity point |

These preferences select the meaning of the geo object. They do not change the place identity.

## Decision statuses

- `ACCEPTED_AUTO`: an exact identity candidate passes the period, type, and geometry checks.
- `ACCEPTED_REVIEWED`: a reviewer selects one candidate and records the reason.
- `UNRESOLVED`: no candidate has sufficient identity or geometry evidence.

An unresolved place does not receive a guessed geometry.

## Required output and audit fields

The geometry table contains:

| Field | Meaning |
|---|---|
| `place_id` | Wikidata QID and unique place key |
| `geometry` | Selected Shapely object |
| `source_dataset` | OHM, source gazetteer found through WHG, OSM, or another named source |
| `source_object_id` | Identifier of the selected source object |
| `source_url` | Direct source record URL |
| `match_method` | Exact QID, reconciled identifier, or reviewed name/context match |
| `selection_policy_version` | Version of this source and selection policy |
| `retrieved_at` | Retrieval timestamp |
| `review_status` | Automatic, reviewed, or unresolved status |
| `decision_reason` | Short explanation of the selection |

Rejected candidates and their evidence remain in a separate audit table. They do not become additional place geometries.

## Proof-of-concept evidence

A live rerun on 2026-10-13 used five place entities from the WWII graph and
applied policy `geo-object-selection-v0.4.0`. The POC input did not contain
related dates, so every place used the project start, `1941-12-07`:

| Place | Finding | POC result |
|---|---|---|
| Hiroshima (`Q34664`) | OSM relation `R4097196` had the exact QID, the required city-boundary meaning, and no conflicting source dates. | Accepted. |
| Pearl Harbor (`Q127091`) | OSM relation `R7378187` had the exact QID, the required harbor meaning, and no conflicting source dates. | Accepted. |
| Wake Island (`Q43296`) | OSM returned three exact-QID objects. The type rule selected reef relation `R3991103`; WHG was queried because the QID count was greater than one. | Accepted. |
| Henderson Field (`Q12259031`) | No exact-QID OHM or OSM object was found. WHG and name search did not prove the required identity. | Unresolved. |
| Soviet Union (`Q15180`) | OHM returned 27 exact-QID historical objects. The date and type rules selected relation `R2851156` for `1941-12-07`; WHG was queried because the QID count was greater than one. | Accepted. |

The run accepted four objects and left Henderson Field unresolved. Wake Island,
Henderson Field, and the Soviet Union were sent together in one authenticated
WHG batch request because they had zero or more than one exact-QID object.

The public OSM Overpass endpoints timed out during this run. The fallback used
Nominatim name discovery and then required an exact QID before applying the type
rule. This fallback can miss OSM objects that Nominatim does not index or return.
It is suitable for this small POC, but the complete run needs a stable Overpass
service or a local OSM extract.

The POC showed that an exact QID is strong identity evidence, but it does not
always define which spatial representation is correct. Place type and the
project-period selection rule resolve the main repeatable cases. Unclear
identities still require review.

## First 50 place-node run

The first 50 nodes classified as `location` in the WWII draft graph were run
on 2026-10-13 with policy `geo-object-selection-v0.4.0`:

- 41 received one valid Shapely geometry: 9 from OHM and 32 from OSM.
- The geometries contain 20 points, 18 polygons, and 3 multipolygons.
- 6 places remain unresolved because no exact-QID OHM or OSM object was found.
- 3 inputs were rejected because they are ships or an organization, not places.
- WHG was called once with 34 queries for cases with zero or multiple exact-QID
  objects. Its candidates remain reconciliation evidence and did not prove an
  additional geometry in this run.
- Gabon's selected historical OHM record had no retrievable valid geometry. The
  source-order fallback selected its exact-QID OSM administrative boundary.

The unresolved places are Nilgiri Mountains, Bathurst Island Airfield, Port
Keats Airfield, Urakami, Provence, and Dachau concentration camp. They need the
documented name-and-context or specialist-source stages. They did not receive a
guessed geometry.

### Six-place fallback run

The six unresolved places were run through the name, alias, type, parent, and
external-identifier fallback on 2026-10-13:

- Bathurst Island Airfield and Port Keats Airfield matched one OSM aerodrome
  each by both IATA and ICAO codes. Their site polygons were accepted.
- Nilgiri Mountains matched one GeoNames hills record by two aliases, feature
  type, and the Tamil Nadu parent.
- Urakami matched one GeoNames populated-place section by alias, feature type,
  and the Nagasaki parent.
- Provence matched the GeoNames region record linked by Wikidata property P1566.
- Dachau concentration camp matched one GeoNames historical-site record by its
  full name and feature type.

The four GeoNames results are points. The fallback resolved all six cases. The
version 2 result therefore contains 47 valid place geometries and 3 rejected
inputs that are not places.
