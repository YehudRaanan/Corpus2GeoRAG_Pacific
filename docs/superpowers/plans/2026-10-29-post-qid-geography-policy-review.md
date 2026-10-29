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

## OWNER discussion, 29 October 2026

OWNER requested discussion of evidence before approval. The following are proposals only; Geography has not been populated.

1. Direct identity evidence: source geometry explicitly identifies the same QID. This supports considering that representation, subject to its meaning and suitability; a point is not a boundary.
2. Supporting evidence: name, object kind, location and page context agree. These can support a source identity, but name or proximity alone is not acceptance evidence. Provisional entities keep their identities.
3. Insufficient/conflicting evidence: preserve candidate and reason without acceptance. A ship or event coordinate requires its intended meaning to be understood; Daniel LOC alone does not establish fixed-place suitability.

Verified examples from core_3 and native_complete_3:

- Fort Stevens, Q1438734/LOC: native revision2540505757, normal Earth P625 statement q1438734$852D4584-3729-47AC-B092-5FAD562CDB89, latitude46.2019/longitude-123.963, precision0.0001. Original mention source_row_index312923, Wiki page23680822/revision1375594940. This is point evidence; no boundary inference.
- Battery Russell, provisional LOC PROV_cba1e3146d73a50d6043c9641c6f3ad2744ef3b921d974e239cefc1bc22b90e3: source_row_index312974 on the same page/revision; text places the battery within Fort Stevens. No assigned QID/native record. The fort geometry cannot be copied merely from containment context.
- Q2065004/LOC is the ship Akitsushima and has P625 evidence. QID+coordinate+Daniel LOC does not establish fixed-place suitability or the intended coordinate meaning.

Pending: eligible object kinds; evidence sufficient for same-place acceptance including provisional cases; point versus boundary handling; retention of every LOC with explicit unresolved reasons. Scores45/30/15/7/3 remain an existing ranking policy, not newly approved identity proof.
