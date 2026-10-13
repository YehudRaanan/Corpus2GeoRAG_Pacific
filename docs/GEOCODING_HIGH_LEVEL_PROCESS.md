# Geocoding High-Level Process

## Purpose

This process assigns one geographic object to each confirmed place entity in the WWII graph. The result is designed for graph construction and Agent testing.

Policy version: `geo-object-selection-v0.5.0`

## Final data model

- The Wikidata QID is the canonical place identifier.
- Each place entity has one selected geographic object.
- The geographic object is stored as a Shapely geometry.
- The geometry can represent a point, line, polygon, or multipolygon. Its type comes from the Shapely object, so a separate geometry-type field is not required.
- The place-to-geometry connection has no `valid_from` or `valid_to` fields.
- Wikidata coordinates and shapes are not used as geometry sources.
- Wikidata names, aliases, types, parent context, QIDs, and external identifiers can be used as identity evidence.
- The coordinate reference system must be stored in the geometry table metadata. The Agent contract does not yet define its required CRS.

## Process overview

```mermaid
flowchart TD
    A[Confirmed place entity and Wikidata QID] --> B[Set a source-selection date]
    B --> C[Search OHM for exact QID]
    C --> D[Search OSM for exact QID]
    D --> E{Exact-QID result count is 1?}
    E -- Yes --> G[Check identity, date, place type, and geometry]
    E -- No: 0 or more than 1 --> F[Query WHG for reconciliation evidence]
    F --> G
    G --> H{Valid supported candidate?}
    H -- Yes --> I[Select one source geometry]
    H -- No --> J[Search names, aliases, context, and external IDs]
    J --> K{Unique supported candidate?}
    K -- Yes --> I
    K -- No --> L[Use a specialist source or manual review]
    I --> M[Convert to and validate Shapely geometry]
    M --> N[Save geometry and full provenance]
    L --> O[Accept after review or mark unresolved]
```

## Selection date

The source-selection period is the Pacific War period: **1941-12-07 through 1945-09-02**, inclusive.

For each place:

1. Use the earliest related event or relation date inside this period.
2. If no related date exists, use `1941-12-07`.
3. If several dates exist, use the earliest date inside the period.

The date helps select a historical source object. It is kept in the audit record and is not an attribute of the final place-to-geometry link.

A dated source geometry is eligible when its source interval contains the selection date. An undated geometry remains eligible when its identity and place meaning are correct.

## Source order and rationale

| Order | Source or method | Use | Rationale |
|---:|---|---|---|
| 1 | OpenHistoricalMap (OHM) | Find an exact `wikidata=QID` object and check its source dates. | Historical objects can better represent a WWII place or boundary. |
| 2 | OpenStreetMap (OSM) | Find an exact `wikidata=QID` object, mainly for stable physical features and current boundaries. | OSM has broad geometry coverage and often supplies a usable object when OHM does not. |
| 3 | World Historical Gazetteer (WHG) | Query only when the combined OHM and OSM exact-QID count is zero or greater than one. Use it for reconciliation and linked-source evidence. | WHG can resolve missing or ambiguous identities, but its request quota is limited and a WHG union is not a final geometry. |
| 4 | Name, alias, and context search | Search OHM or OSM name services and GeoNames. Require added evidence such as a source ID, compatible type and parent area, or two airport codes. | This recovers places without an exact QID link while controlling false matches from shared names. |
| 5 | Specialist source or documented manual construction | Use a suitable public dataset or digitize a documented historical map. | Some historical places have no supported object in the general sources. |

WHG requests are batched, with up to 50 place queries in one API request. The WHG key stays in the local `.env` file and must not appear in outputs or logs.

## Automatic candidate logic

For each place, the process:

1. Collects the OHM and OSM candidates.
2. Uses the Wikidata QID as the strongest identity link.
3. Uses WHG only under the rule above.
4. Removes candidates that do not apply on the selection date.
5. Removes candidates whose geographic meaning conflicts with the place type.
6. Applies the preferred representation for the place type.
7. Selects the first valid candidate in the project period. A stable source object ID breaks a remaining tie.
8. Retrieves the full geometry. If it is missing or invalid, the process tries the next source.
9. Converts the selected geometry to Shapely and checks that it is valid and not empty.
10. Saves the choice, source, evidence, rejected alternatives, and decision reason.

The process does not automatically union, buffer, simplify, or replace a geometry with its centroid. Each such transformation needs an explicit rule and an audit record.

## Place type and preferred geometry

| Place type | Preferred representation | Allowed fallback |
|---|---|---|
| Country or administrative area | Administrative boundary | Exact-identity point |
| City or settlement | Administrative boundary | Settlement point |
| Island | Land extent | Exact-identity point |
| Atoll | Reef extent | Reviewed island or regional extent |
| Harbor | Harbor or water extent | Exact-identity point |
| Airfield, base, camp, or facility | Site footprint | Exact-identity point |
| River, route, or other linear place | Line geometry | Exact-identity point |

These rules select the geographic meaning. They do not change the entity identity.

## Decision outcomes

- `ACCEPTED_AUTO`: deterministic identity, date, type, and geometry checks pass.
- `ACCEPTED_REVIEWED`: a reviewer accepts a candidate and records the reason.
- `UNRESOLVED`: the available evidence is insufficient.
- `REJECTED_NOT_PLACE`: the upstream node is not a place and must not receive a geometry.

An uncertain place stays unresolved. It does not receive a guessed geometry.

## Output and audit requirements

The main geometry table needs these fields:

| Field | Meaning |
|---|---|
| `place_id` | Canonical Wikidata QID |
| `name` | Place label used in the run |
| `place_type` | Normalized place class |
| `geometry` | Selected Shapely object |
| `source_dataset` | Selected source |
| `source_object_id` | Source record identifier |
| `source_url` | Direct source record URL |
| `match_method` | Exact QID, reconciled ID, or reviewed contextual match |
| `selection_date` | Date used to select the source geometry |
| `selection_policy_version` | Version of this process |
| `retrieved_at` | Retrieval timestamp |
| `review_status` | Decision outcome |
| `decision_reason` | Short evidence-based explanation |

The audit data also keeps all candidates, source attempts, exact-QID counts, WHG query details, rejected candidates, validation results, and review decisions. GeoParquet is the working storage format because it restores the geometry as a Shapely object when loaded.

## Why this design is used

- A QID gives all sources one identity anchor.
- Historical sources have priority because a WWII geometry can differ from a current map.
- Place type prevents the system from choosing the wrong meaning of a shared QID, such as a point instead of an atoll extent.
- Context fields reduce false matches when no source has an exact QID link.
- One geometry per place gives the Agent a simple and stable interface.
- Full provenance permits later review, correction, and replacement.
- An unresolved result is safer than a geometry selected from weak evidence.

## Current proof of concept

The first 50 nodes classified as locations produced:

- 47 accepted Shapely geometries.
- 34 objects from OSM, 9 from OHM, and 4 from GeoNames.
- 24 points, 20 polygons, and 3 multipolygons.
- 0 unresolved valid place inputs.
- 3 inputs rejected as non-places.

The four GeoNames results are points. They are usable starting geometries and can be replaced by better supported shapes in a later policy version.

## Production limits

- The Agent contract still needs to define the required coordinate reference system and the method used to load the Shapely geometry table.
- Public query services can time out or limit requests. A complete run should use stable endpoints, controlled retries, persistent caches, and resumable checkpoints.
- Source coverage does not prove geographic truth. Candidate evidence and provenance must remain available for quality review.
