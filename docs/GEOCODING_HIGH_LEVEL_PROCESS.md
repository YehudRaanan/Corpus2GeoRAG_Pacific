# Geocoding High-Level Process

## Current selection rule — owner correction, 22 October 2026

If one or more valid nonempty source geometries have been retrieved for an existing LOC input, select the highest-ranked available geometry. Low or zero score, uncertain identity or conflicting evidence stays in metadata; it does not make an available geolocation unresolved. When no usable geometry has been retrieved, keep the geometry unresolved. Preserve the input QID/SYN ID and Wikidata matching status. Never fabricate an entity or source geometry.

Use the 45/30/15/7/3 QID, Wikidata-coordinate, context, name and feature-type ranking. Stable score ties prefer a polygon, then source and source-object ID. Wikidata Points compete by score; the previous last-resort-only/source-first priority does not override a higher-ranked Point. Retain source evidence, scores and uncertainty, including approximate position and unconfirmed historical extent. A useful nearby approximation is preferred over an empty location.

**Multiple coordinates — owner approval, 22 October 2026:** retain every non-deprecated Wikidata P625 statement as a separate coordinate/Point candidate. Preserve each original coordinate, rank, precision and statement ID. Apply the same ranking and stable tie rule; do not average coordinates or change the input identity. This supersedes the earlier single-coordinate stop rule for multiple statements. Other unsupported coordinate representations still stop for consultation.

**WHG batching — owner approval, 22 October 2026:** submit the unchanged reconciliation queries in batches of at most 50, following the [service limit](https://docs.whgazetteer.org/content/technical/apis.html#batching-quotas-and-retries). Save each complete batch and validate every requested query ID before combining results. Reuse a saved batch only when its queries match exactly. A failed or partial response is a source failure, not an empty candidate set; stop under the POC consultation rule. Batching does not change sources, query content, input identities or ranking.

This rule supersedes conflicting uniqueness, confidence, date/type/name/QID rejection and mandatory-manual-review selection gates in the historical workflow below. It changes geometry selection, not upstream entity matching or the approved source list. Input-local candidate retrieval and valid Shapely storage still apply. The [twenty-input result](GEOGRAPHY_RANKING_20_ALWAYS_SELECT_2026-10-22.md) verifies eighteen selections for eighteen inputs with loaded geometries and zero avoidable unresolved outputs. Full-model integration has not been run.

**Synthetic LOC approval - 21 October 2026:** all existing LOC identities enter Geography, including unresolved SYN IDs. QIDs use exact-ID lookup first; SYN IDs use the existing name/alias/date/type/context fallback and keep their original IDs. Supported geometry does not create a Wikidata match. The current rule above now selects among ambiguous geometry candidates instead of leaving an available location unresolved. `Geography.geometry_ref.place_id` can therefore be an existing QID or SYN ID; the reference stays in the model, not graph JSON. This extends target coverage under the existing source and acceptance policy.

**Geometry pointer correction - 21 October 2026:** `Geography.geometry_ref` belongs to the data model, not final graph JSON. It retains the approved `{file, place_id, sha256}` format and identifies the saved Shapely/WKB object. The existing loader can read this model reference; Agent access to the model still requires integration verification. Earlier graph-node pointer instructions are superseded. No pointer or inline GeoJSON is exported in graph JSON.

## Purpose

This process seeks one selected geographic object for each existing LOC entity, including synthetic identities without a Wikidata match. Use the highest-ranked available valid geometry and record uncertainty. Only an input without a retrieved usable geometry stays unresolved.

Base retrieval/storage policy: `geo-object-selection-v0.5.0`. Current tested selection rule: `geo-ranking-20-experiment-v3` (22 October 2026).

Approved population extension, 21 October 2026: include synthetic LOC identities in the existing name/alias/date/type/context fallback. Keep each original SYN ID; do not assign a new QID or merge repeated names. This changes target coverage, not the source list or acceptance rules.

Bulk acquisition plan added: `2026-10-19`. This is a planned retrieval method;
the place-selection rules remain unchanged.

## Final data model

- The existing entity ID identifies the place: its QID when matched, otherwise its unchanged SYN ID. A geometry match does not change the entity's Wikidata matching status.
- Each place entity has one selected geographic object.
- The geographic object is stored as a Shapely geometry.
- Geocoding returns a validated Shapely object, not GeoJSON. GeoParquet persists it as WKB and restores it as Shapely when loaded. The Geography data model contains `geometry_ref={file,place_id,sha256}` pointing to the saved object. The loader restores Shapely from this model reference. Final graph JSON omits the pointer and inline geometry. Agent access to the model must be verified, as defined in the [S2T](ENTITY_MODEL_TO_AGENT_GRAPH_S2T.md#geometry-object-reference-and-loading).
- The geometry can represent a point, line, polygon, or multipolygon. Its type comes from the Shapely object, so a separate geometry-type field is not required.
- The place-to-geometry connection has no `valid_from` or `valid_to` fields.
- Wikidata coordinates may guide retrieval, strengthen location context, and supply an unchanged last-resort Shapely Point under the coordinate rule below. Wikidata shapes are not approved geometry sources.
- Wikidata names, aliases, types, parent context, QIDs, and external identifiers can be used as identity evidence.
- The coordinate reference system must be stored in the geometry table metadata. The Agent contract does not yet define its required CRS.

## Historical process overview (selection gates superseded above)

```mermaid
flowchart TD
    A[Existing LOC entity: QID or SYN ID] --> B[Set a source-selection date]
    B --> P{Has a matched Wikidata QID?}
    P -- Yes --> C[Search OHM for exact QID]
    P -- No --> J
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

**Partial-date approval - 21 October 2026:** retain year/month precision (`YYYY` or `YYYY-MM`) and compare the source date range at that same precision. Do not insert day 01 or invent an exact date. Project-period eligibility uses the existing possible-overlap comparison at the supplied precision. Preserve the original date evidence.

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
| 6 | Wikidata coordinate fallback | If no other supported geometry is available after the approved source attempts, use the supported coordinate as a Shapely Point without moving or expanding it. | Owner approval, 22 October 2026; this is the last geometry fallback, not a shortcut around identity checks. |

WHG requests are batched, with up to 50 place queries in one API request. The WHG key stays in the local `.env` file and must not appear in outputs or logs.

## Bulk downloads and reuse

Use saved snapshots and bulk exports as the main retrieval method. Search them
for all existing LOC targets after entity matching, using QID lookup where available and the supported name/context fallback otherwise, rather than making
the same request for every mention. Retain all candidate objects for the
existing identity, date, type, and geometry checks. Source priority remains
OHM, then OSM, with WHG used under the exact-QID count rule above.

| Data | Bulk retrieval plan |
|---|---|
| Wikidata identity and coordinate evidence | Reuse the saved BigQuery reference results first. Retrieve missing QIDs together from BigQuery, or use an [official Wikidata dump](https://www.wikidata.org/wiki/Wikidata:Database_download). Coordinates have the three approved uses below; Wikidata shapes remain excluded. |
| OHM geometries and tags | Download a pinned [OHM snapshot](https://wiki.openstreetmap.org/wiki/OpenHistoricalMap/Reuse) and search locally for QIDs and supported fallback evidence. |
| OSM geometries and tags | Export candidates for the place-QID list from the [OSM BigQuery dataset](https://wiki.openstreetmap.org/wiki/BigQuery_dataset). [Geofabrik regional files](https://www.geofabrik.de/en/data/download.html) are an alternative when required objects or complete geometry are unavailable in that dataset. |
| GeoNames fallback records | Reuse or download the needed [country files](https://download.geonames.org/export/dump/readme.txt) and search them locally using the existing identity-evidence rules. |

**OSM snapshot decision — 19 October 2026:** The user accepts the older OSM
BigQuery snapshot for this historical-period project. Snapshot age is not a
rejection criterion, and updating it to the latest OSM data is not required.
Still record the snapshot date. Historical suitability is assessed separately:
each candidate must pass the existing place-identity, geographic-meaning, and
selection-date rules. The snapshot's publication date does not establish that
its shapes represent the WWII period.

The planned sequence is:

1. Produce targets for all existing LOC identities, retaining original mention
   and page references. QIDs use exact-ID lookup first; synthetic IDs use the
   existing name/alias/context fallback directly. Never send a SYN ID as a QID.
   Retain each synthetic target separately; no new entity extraction or merging.
2. Reuse saved references and retrieve missing candidates in bulk. For BigQuery,
   estimate bytes processed before execution and save the query and result.
3. Apply the existing selection policy to each place; preserve rejected
   candidates and unresolved reasons.
4. Save one selected Shapely geometry per accepted place, with reusable
   GeoParquet output and provenance.
5. Use controlled, cached API calls only for remaining gaps or necessary WHG
   reconciliation. Keep resumable checkpoints and respect each service's limits.

For each input snapshot or bulk export, save the source URL or table ID,
available source date/version, retrieval time, query or filter scope, row count,
and file checksum. Reuse verified saved files on restart. This plan does not
start a new download, geocoding run, or Agent release.

## Automatic candidate logic

For each place, the process:

1. Collects the OHM and OSM candidates.
2. Uses the Wikidata QID as the strongest identity link when available; otherwise uses supported name/alias/type/context evidence. Daniel's source-page title is context, not proof of a parent area. Missing type/parent evidence is not invented. Dates use the existing rule, including its default when unsupported.
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

## Approved broader-polygon preference — 22 October 2026

When a precise location cannot be established, prefer a supported broader local polygon over an unresolved geolocation. Country-wide and larger polygons are not acceptable approximations for a local place. This restriction concerns fallback approximations, not the exact boundary of an entity that is itself a country.

The selected area must be identified as approximate, with its actual source object and supporting evidence retained. It must not be presented as the exact footprint of the input place or as proof that an ambiguous identity has been resolved. Keep the existing entity ID and Wikidata matching status unchanged. Unsupported areas remain unresolved; this preference does not authorize a guessed polygon, buffer, union, or new source.

**Implementation pending:** the maximum permitted extent, the rule for selecting a broader area, and the machine-readable representation of approximation must be agreed before changing the automatic selector. No numerical limit, parent-area rule, or new acceptance status is approved by this preference alone. The current selector and previous sample assignments are unchanged.

**Ten-example test approval and result:** the owner subsequently approved the smallest supported existing local polygon covering the plausible locations, marked approximate, with country-wide and larger approximations excluded. The [cached ten-input test](GEOGRAPHY_LOCAL_POLYGON_10_2026-10-22.md) retained London and Java, added an approximate 3.847 km² Hoosick Falls village polygon, and left seven inputs unresolved. This sample-only helper does not replace the production selector, define a numerical maximum area, or approve new identity/alias/context rules. The prior outputs remain unchanged.

## Wikidata coordinate approval — 22 October 2026

The owner approved three uses of available Wikidata coordinates (`P625`):

1. **Retrieval context:** use the coordinate to guide Nominatim retrieval of candidate places, addresses and source geometries. It does not authorize an arbitrary search radius or automatic acceptance of the nearest result.
2. **Supporting context:** use the coordinate with names, aliases, place type, dates and supported parent evidence to strengthen or reject unresolved location candidates. Keep candidate coordinates distinct from independently supported input evidence; do not use a candidate's own coordinate to prove that the candidate is Daniel's intended place.
3. **Last-resort geometry:** when no other supported geometry is available after the approved source attempts, use the supported coordinate as-is as `Shapely.Point(longitude, latitude)`. Do not buffer, snap, average, infer a polygon, or replace it with another location. This explicitly supersedes the previous ban on Wikidata coordinates as selected geometry; it does not approve Wikidata shapes.

**Owner correction, 22 October 2026:** do not require an additional confirmed-input identity gate for the final coordinate fallback. For a matched QID, use evidence for that item. For an unresolved synthetic input, an available saved exact-name/alias-linked Wikidata candidate coordinate can supply the fallback Point. Keep the synthetic ID and matching status unchanged; record the source QID, candidate-only identity status and uncertainty in the Geography audit. This assigns a position, not a new identity. It does not authorize arbitrary candidate coordinates or a nearest-result match. Multiple conflicting candidates/coordinates or unsupported coordinate representations require consultation, not a silent choice.

Retain the original coordinate statement, precision, globe/CRS, source item and statement identifier, available dates/qualifiers, snapshot/retrieval evidence and the fallback reason in the existing audit. Apply the agreed snapshot-first acquisition rule and cache reuse. A point is a position, not a place boundary or proof of its WWII extent. Persist it through the existing Shapely/WKB/GeoParquet path; keep its pointer in Geography and out of graph JSON.

The [corrected ten-example coordinate test](GEOGRAPHY_COORDINATE_10_2026-10-22.md) retained three geometries and added the original Wikidata Points for Tinian Town and Sunharon Bay: five with geometry, five unresolved. Both retain synthetic IDs and candidate-only uncertainty metadata. The correction reused all four saved Nominatim responses with zero new requests. The initial three/seven result had an extra identity gate and is superseded by this correction. Production selection and earlier outputs remain unchanged.

## Decision outcomes

- `ACCEPTED_AUTO`: deterministic identity, date, type, and geometry checks pass.
- `ACCEPTED_REVIEWED`: a reviewer accepts a candidate and records the reason.
- `UNRESOLVED`: the available evidence is insufficient.
- `REJECTED_NOT_PLACE`: the upstream node is not a place and must not receive a geometry.

An uncertain place does not receive a guessed geometry. The approved broader-polygon preference above permits a supported approximate area in principle; its automatic selection rule is not yet implemented.

## Output and audit requirements

The main geometry table needs these fields:

| Field | Meaning |
|---|---|
| `place_id` | Existing LOC entity ID: QID or unchanged SYN ID |
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
- Current owner rule: select the highest-ranked available valid geometry even when evidence is weak; preserve uncertainty. Only no retrieved usable geometry leaves the location unresolved.

## Current proof of concept

The first 50 nodes classified as locations produced:

- 47 accepted Shapely geometries.
- 34 objects from OSM, 9 from OHM, and 4 from GeoNames.
- 24 points, 20 polygons, and 3 multipolygons.
- 0 unresolved valid place inputs.
- 3 inputs rejected as non-places.

The four GeoNames results are points. They are usable starting geometries and can be replaced by better supported shapes in a later policy version.

## Production limits

- The model pointer schema and geometry loading helper exist. Agent access to Geography, storage/version binding and spatial CRS compatibility remain integration checks. Graph JSON does not carry a geometry pointer or inline GeoJSON.
- Bulk exports and saved snapshots are the planned main retrieval route. Public query services used for gaps can time out or limit requests; use controlled retries, persistent caches, and resumable checkpoints.
- Source coverage does not prove geographic truth. Candidate evidence and provenance must remain available for quality review.
