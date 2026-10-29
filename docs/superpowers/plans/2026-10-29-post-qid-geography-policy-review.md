# Geography policy review: first three pages

Verified from saved core data and existing code on 29 October 2026. This is a read-only review, not an approved replacement policy. Geography population is pending OWNER decisions.

## Current population

| Measure | Count |
|---|---:|
| Original LOC mentions | 94 |
| LOC bridge links | 100 |
| Typed LOC identities | 50 |
| QID LOC identities | 16 |
| Provisional LOC identities | 34 |
| QID LOCs with saved nondeprecated Earth P625 statements | 14 |
| These P625 statements | 15 |

Daniel's LOC label is preserved. Some linked QIDs identify an event or a ship, so that label alone does not establish geographic suitability. Provisional literals include `Japan`, `United States`, `Battery Russell`, `Clatsop County`, `Fort Stevens State Park`, and unusable strings such as `.`, `S`, and `31`. Preserve all original strings and identities.

## Existing implementation

`GG_Data/pipeline/geography_ranking_sample.py` ranks QID, coordinate, context, name and feature-type evidence with maximum points 45/30/15/7/3. A provisional candidate QID can add 20 points without changing identity. Missing evidence scores zero. Coordinate evidence uses containment, then distance bands of 1, 5 and 20 km. Context includes local text, paragraph, page title, other page LOC names, GeoNames containment and supported historical dates.

The selector can choose geometry at zero total score. Conflict and uncertainty flags do not exclude it. Ties prefer polygons, then stable source and source ID. Wikidata points compete by score. Nondeprecated Earth P625 statements remain separate; coordinates are not averaged. Country/continent substitutes are excluded unless they identify the target itself.

`GG_Data/pipeline/geography_population.py` requires selection when geometry exists, marks selected rows `ACCEPTED_AUTO`, and omits unresolved LOC rows. The new population must retain every LOC with geometry or an explicit unresolved reason; this is an integration change, not an identity correction.

## Cached evidence and limits

The saved full Geography output covers four of the 16 QIDs: Q184425, Q211377, Q928 and Q98. This proves availability, not current selection correctness. The 2.12 GB candidate cache was not scanned. Complete compatible candidate coverage remains unknown.

## Pending decisions

OWNER was asked whether to retain the scores only for ranking, require same-place evidence before geometry acceptance, and retain weak/conflicting/unusable cases as unresolved. Provisional identities would remain provisional. No zero-score or conflicting geometry has been automatically accepted in this run.

The separate Agent `what_happened_at` spatial date-filter issue remains open and outside this task.
