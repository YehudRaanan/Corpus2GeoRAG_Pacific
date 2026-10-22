# Geography: context and coordinates for the five remaining inputs

## Verified result

The previous sample remains five geometries and five unresolved inputs. This
investigation retrieves more evidence; it makes no new identity or geometry
assignments. It does not change the production selector or define a new name,
distance, type or parent threshold.

Eleven Nominatim requests are saved. Their cached replay uses zero new requests.
One current Wikidata record supplies the previously skipped Crabs Peninsula
coordinate. The five inputs, their original text, page IDs, existing same-page
LOC mentions, previous context decisions and coordinate candidates are saved
in `context_evidence.json`. No new Daniel entities are extracted.

## Why the earlier process missed useful evidence

`geography_context_sample.context()` recognizes seven literal feature families
inside the name or immediately after it. It recognizes possible parents only
after a comma or the word `in`. `checked_context()` then checks those parents
against saved country and first-level administrative names. Only a parent that
passes this check is allowed into its qualified Nominatim search.

This excludes wider source-text and page clues from retrieval. For example,
Donbaik's immediate comma is followed by the person Lloyd, while the useful
Mayu Range/Valley clues occur later. Rejecting Lloyd as a parent was correct;
letting that rejection prevent other contextual searches was too restrictive.
Crabbs has an explicit Antigua clue, but the country/state lookup does not
establish its island relationship. This is a search limitation, not proof that
the input lacks context.

The coordinate helper additionally restricted Wikidata candidate lookup to
exact names/recorded aliases. Thus Crabs/Crabbs was not inspected even though
the saved candidate name score is 0.8888888888888888. The current investigation
checks that existing candidate without changing any matching threshold.

## Evidence and actual requests

| Input | Already available input context | What was tested and found |
|---|---|---|
| Donbaik | Exact GeoNames alias Donbaik for Done Paik, GN 1326299; coordinate X=92.67944, Y=20.35675. Source page Arakan Campaign 1942-1943; text contains Mayu Range, Mayu Valley and an 18 March attack. Existing same-page LOC rows include Burma Q836 and Arakan Q233838. | `Donbaik, Arakan` returns nothing. `Done Paik, Myanmar` returns two OSM village nodes. Node 5095553736 is 18.441 m from the saved GN coordinate; node 5095553737 is 88.920 km away. Reverse lookup at the GN point returns a road with the nearer village in its address. This distinguishes candidates but is not a newly approved distance acceptance rule. |
| Crabbs Peninsula | Original text: `Naval Air Station Crabbs at Crabbs Peninsula, Antigua`. Saved Crabs Peninsula candidates include a peninsula GN 3576295, a separate populated-place GN 11882973, and Wikidata Q21052107. | Current Q21052107 has original P625 X=-61.75, Y=17.116666666667. Both `Crabbs Peninsula, Antigua` and `Crabs Peninsula, Antigua` return nothing. Reverse at P625 returns Guinea Bush Line, a track in Parham, Saint Peter, Antigua. Its address supports the island context; its road geometry is not the peninsula. |
| Pocatello Army Air Base | Original text explicitly says Idaho and describes aircrew training during 1944. Saved GN 6354207 is Pocatello Army Air Field (historical), military installation INSM, X=-112.59333, Y=42.91167. Idaho already passes the parent check. | `Pocatello Army Air Field, Idaho` returns nothing. Reverse at the historical GN point returns OSM way 49215124, Pocatello Regional Airport, with Polygon geometry, Idaho address, IATA/FAA PIH, ICAO KPIH and Wikidata Q8190680. The polygon **contains the historical GN point**. This is useful site evidence; reverse lookup alone does not establish the historical name equivalence or a WWII boundary. |
| Piva Yoke | Original text explicitly says fighter strip, with March attacks on the Bougainville campaign page. Saved Piva river GN 2088278 and settlement GN 2088279 have coordinates. Existing same-page LOC mentions include Torokina River and Empress Augusta Bay Q647280. | `Piva Yoke, Bougainville` returns nothing. `Piva, Bougainville` returns two river objects and one village. Reverse at the saved settlement point returns a road in Torokina, South Bougainville District. This supplies a relevant local search area, but no returned object identifies the fighter strip. No river or village point is assigned to the strip. |
| `.` | The saved span is a period inside `U.S.` in text about the Fifth Fleet, with Persian Gulf, Western Pacific, Indian Ocean and Japan mentioned elsewhere. Existing same-page LOC rows include Bahrain and Mariana Islands. | No name query is sent for punctuation. Context explains the extraction problem and shows several possible surrounding places. It does not identify one distinct place represented by this period. The original row and ID are preserved. |

Same-page rows are context, not guaranteed correct identities or geographic
parents. Page titles can cover large or multiple areas; the global US Naval
Advance Bases page is an example. A candidate's own country, address or
coordinate is labelled candidate-directed evidence, not independent proof of
Daniel's intended place.

The previous cached BigQuery query does not contain Q21052107. Its absence
from that query is not proof of absence from the agreed snapshot. This test
uses the approved latest-available fallback source and records its retrieval
time and full native coordinate statement. No new BigQuery query was made.

## Retrieval correction demonstrated by this test

Use original text, page references, existing related LOC rows, candidate names,
aliases and original coordinates to generate labelled search hypotheses.
Do not require a search clue to be an already accepted geographic parent just
to inspect search results. Preserve the distinction between original-input
evidence and source-candidate evidence. Nominatim addresses and shapes can then
support or contradict these hypotheses.

The query plan here is an explicitly prepared **diagnostic plan** using saved
evidence, not a new unattended context extractor. The reusable runner accepts
that plan without applying the old parent gate. It does not establish a new
production context-selection or geometry-acceptance rule. Existing approved
Wikidata Point and broader local-polygon fallbacks remain documented in S2T 9.2–9.3.

Do not automatically take the first name result: the first Done Paik village
is the one 88.920 km away. Do not automatically take a reverse-result geometry:
Crabbs, Donbaik and Piva return roads. No new nearest-distance cutoff is inferred.

## Verification, artifacts and replay

- Six focused tests pass; Black and Ruff pass for the new probe and test.
- Seventy-two protected hashes remain unchanged, including model evidence and
  the completed five-geometry test output.
- All eleven cached request receipts match the plan. The replay makes zero
  new requests and reuses eleven responses.
- The original Crabbs coordinate and the Pocatello containment check were
  read back and verified. Distances use WGS84 geodesics and are diagnostics.
- The first Donbaik request returned before a local save-directory bug stopped
  the script. That response was not saved. The directory creation was fixed and
  checked by a regression test; the query was repeated. Eleven saved responses
  therefore do not account for that one additional initial request.

Code: `GG_Data/pipeline/geography_context_probe.py`.
Local ignored artifacts:
`GG_Data/pipeline/outputs/geography_context_evidence_5_20261022/`:
`query_plan.json`, `retrieval.json`, `context_evidence.json`,
`crabs_wikidata_coordinate.json`, eleven `sources/` receipts and the native
Wikidata response under `wikidata/`.

```powershell
C:\Users\User\anaconda3\python.exe -B -m GG_Data.pipeline.geography_context_probe --plan GG_Data/pipeline/outputs/geography_context_evidence_5_20261022/query_plan.json --output GG_Data/pipeline/outputs/geography_context_evidence_5_20261022
```

Data: OpenStreetMap contributors (ODbL), GeoNames, Wikidata. The bounded public
Nominatim test uses one machine/thread, identifying User-Agent, caching and at
least 1.1 seconds between requests. See the [usage policy](https://operations.osmfoundation.org/policies/nominatim/)
and [search documentation](https://nominatim.org/release-docs/latest/api/Search/).
These ignored local artifacts are not backed up by a code commit.
