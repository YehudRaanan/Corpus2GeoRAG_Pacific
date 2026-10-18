# Single-type trial and page lookup audit

18 October 2026. Offline replay of the same three pages and all 362 original
Daniel rows. No new entity extraction, live collection, notebook, or canonical
graph change. Earlier runs are preserved.

## Type rule

Keep compatible candidates first. If none exists, examine the highest-scoring
name candidates (score >= 0.80). Adopt their mapped Wikidata type only if every
candidate has one accepted mapped type and all agree on that type. Unknown,
excluded, or conflicting types do not trigger a correction. Equal-scoring QID
ties still use the agreed saved random seed.

Each row retains the exact original `raw.entity_group`. `type_metadata` records
`original_type`, `resolved_type`, `type_changed`, `type_source`, and, for QID
matches, the mapped type set and original Wikidata P31 class IDs. CSV exposes
these fields beside the original `entity_group`. Broad categories such as MISC
are our mapping, not native Wikidata classes; the P31 IDs preserve that distinction.

The shared class filter now discards an excluded inheritance branch without
erasing other valid branches. Direct instances of lists/disambiguation remain
excluded. This fixes Yale Q49112, which has valid organization branches and an
unrelated branch reaching a list class.

## Trial result and limits

| Result | Mentions |
|---|---:|
| Page-context QID assignments | 263 |
| Frozen matched-ID fallback | 1 |
| Saved fresh-WWII fallback | 5 |
| Calendar dates | 37 |
| Unresolved synthetic mentions | 56 |
| Total | 362 |

Ten rows record a type change; Yale resolves without changing its original ORG
type. Eleven previously unresolved rows receive QIDs. All previously assigned
IDs remain unchanged. The remaining reasons are 46 name failures, six type
conflicts, three cases without accepted type evidence, and one invalid date.

These are automatic assignments, not validated identities. The relaxed type
fallback exposes existing identity problems: `14 Infantry Division` selects
`26th Infantry Division`; Pescadores selects Q141451967 instead of the known
Penghu Islands candidate Q918799, without proving identity; the two New York Times rows select
different QIDs (Q9684 and Q135925219). Shared broad type does not prove identity.
The agreed random tie rule and unrelated exact-name candidates remain causes.
The broad map also calls Burma Campaign ORG through inherited classes; this is
a mapping limitation, not a native Wikidata statement that the campaign is an
organization. No manual QID corrections were applied.

A preliminary unrestricted per-candidate override is saved separately in
`runs/direct_wikidata_single_type_20261018`. It is rejected: it changed existing
assignments to unrelated homonyms. The current bounded trial is the `_v2` run.

## Why page collection did not resolve the 46 name failures

Audit of both saved English/Japanese article HTML records, direct hyperlink
inventories, redirect maps, and the actual candidate metadata. No inferred names
were added. The categories describe links whose displayed text contains the
original Daniel mention; they do not prove identity or Wikidata absence.

| Saved-page evidence | Mentions |
|---|---:|
| Internal link target QID already collected, name still rejected | 12 |
| Only external links containing the mention | 7 |
| Link to a missing Wikipedia page (red link) | 1 |
| No hyperlink text containing the mention | 26 |
| Total name failures | 46 |

The collector retained target QIDs but did not add the source link's displayed
name as page-specific comparison evidence. Examples:

| Daniel mention / link text | Linked target / collected QID | Best saved name score |
|---|---|---:|
| Akyab Island | Sittwe / Q738748 | 46.2% (`Akyab`) |
| 23rd Mountain Regiment | 23 Field Regiment / Q111168464 | 40.0% |
| Indian Signal Corps | Corps of Signals / Q6019841 | Below 80% |
| Indian Engineers | Corps of Engineers / Q1164370 | Below 80% |

These are failures to use page evidence, not failures to retrieve the QID. A
source hyperlink can also be imprecise: Akyab Island linking to Sittwe does not
by itself prove that the city and island are identical. An anchor may contain a
longer name than Daniel's fragment, such as `of Surrender` inside `Japanese
Instrument of Surrender`; the fragment is not a new full entity name.

`23rd Indian Brigade` is a red link in the relevant paragraph. A differently
named `23rd Indian Infantry Brigade` item is already in the wider page pool,
but its name scores below 80% against this mention.

`Maru Special` and `Ships of the World` appear as plain bibliography text with
no containing hyperlink. `Ushio Shobo` (rendered with a macron in the source)
and `Kaijinsha` link only to publisher websites. The collector follows internal
Wikipedia links, so these external links provide no page QID. Exact English/
Japanese label/alias lookups of Daniel's names returned no accepted name for
these rows; spelling/transliteration variants are not searched exhaustively.
Their presence or absence in all Wikidata is not established.

Next collection improvement to consider: retain each existing internal anchor
name with its target QID, source revision, and page context as comparison
evidence. This uses existing page links, not newly extracted entities. It has
not been implemented in this trial.

## Date explanation

February 29 is valid in leap years. Under the Gregorian calendar, years divisible
by four are leap years except century years not divisible by 400. 1943 is not
divisible by four; February 1943 had 28 days. `29 February 1944` is valid and is
included in the validation check. The invalid 1943 date occurs in both Daniel's
context and the saved Wikipedia article; it was not invented by the matcher.
The source value is preserved, not silently changed to a different date.

## Artifacts and verification

[Rows](runs/direct_wikidata_single_type_20261018_v2/matches.csv) ·
[46-row page audit](runs/direct_wikidata_single_type_20261018_v2/page_lookup_audit.csv) ·
[Summary](runs/direct_wikidata_single_type_20261018_v2/summary.json) ·
[Manifest](runs/direct_wikidata_single_type_20261018_v2/manifest.json)

Replay:

```powershell
python GG_Data/entity_resolution/direct_wikidata_pilot.py --snapshot GG_Data/entity_resolution/runs/direct_wikidata_small_20261018 --output <new-output-directory>
```

Checks: input/snapshot hashes, all 362 exact raw rows, separate synthetic IDs,
type correction evidence, prior assignment preservation, leap-year validation,
thresholds and stage pools, artifact hashes, Ruff, and five unit checks.
Backup: Local checkpoint only.
