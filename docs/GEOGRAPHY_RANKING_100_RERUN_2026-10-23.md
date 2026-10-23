# Same 100 Geography examples: rerun and evidence review — 23 October 2026

## Result

The same 100 original Daniel mentions were traced through the updated matching outputs and the approved Geography ranking. There are 96 current LOC targets. Of these, 94 received a native source geometry and two did not. Four mentions now have only non-LOC target types; all four remain in the original 100-row denominator. The main model and entity assignments were not changed by this test.

| Measure | Previous run | Current run |
|---|---:|---:|
| Original Daniel mentions | 100 | 100 |
| Current location targets | 100 | 96 |
| Selected geometries | 97 | 94 |
| Supported geographic connection | 68 | 72 |
| Incorrect geographic connection | 25 | 18 |
| Unverified selected result | 4 | 4 |
| No geometry | 3 | 2 |
| Now non-LOC | 0 | 4 |
| Supported precision: correct / selected | 68/97 = 70.1% | 72/94 = 76.6% |
| Correct-output coverage of original 100 | 68% | 72% |

Correct means any evidenced geographic connection to Daniel’s entity. It does not require an exact entity, feature boundary or historical period. An unrelated namesake fails. Unverified outputs are not counted as correct. Formal recall is not measured because this review has no complete independent set of recoverable true locations. Correct-output coverage is the recall proxy used here.

On the same currently eligible 96 mentions, the previous run had 68 supported outputs among 93 selected geometries (73.1% precision); the rerun has 72 among 94 (76.6%). This separates the effect of removing four false LOC targets from the geographic retrieval improvement. Precision among only decided current outputs is 72/90 = 80.0%; the primary result above keeps all four uncertain outputs in its denominator.

## Explicit findings: do not treat these as hidden passes

- **Tunis, row 69:** the selected OHM shape is the French protectorate of Tunisia, a country-wide polygon. It has a real connection to Tunis, so it passes the user’s geographic-connection criterion. It violates the approved rule against country-wide approximations for a city. The changed QID now identifies the protectorate; the Geography check treats that QID as the entity itself. No rule change or corrective reassignment was made. Counting only supported outputs that also satisfy this known size restriction gives **71/94 = 75.5%**, or 71/100 original-row coverage. A wider run must not be represented as policy-compliant until this is discussed.
- **Brisbane, row 100:** the new QID and shape identify Brisbane Airport. The saved source explicitly places it in Brisbane, so geography is connected. Exact city identity has regressed from the previous city QID.
- **Malaya, row 55:** the new point is in Kuala Lumpur, so the previous Himalayan error is removed geographically. The Federation of Malaya remains the wrong historical identity for the 1941 sentence; its establishment in 1948 was already a known, owner-approved matching limitation.
- **Ukraine, row 3:** the OHM geometry remains geographically connected; its existing OUTSIDE_SELECTION_DATE warning remains visible. This review does not certify exact historical borders.

No previous broad geographic success became an unrelated location. This does **not** mean exact identity did not degrade: Tunis and Brisbane are explicit counterexamples.

## Improvements and remaining errors

- Waco now selects Waco, Texas, rather than Wacol, Australia. Its synthetic entity ID remains unchanged.
- Dutch East Indies now selects the historical territory rather than an unrelated Texas point.
- Malaya now has a geographically connected point, with the historical identity limitation above.
- Konkoita now uses its existing Wikidata coordinate for a POW camp in Kanchanaburi, Thailand. The earlier sample had the named candidate but did not load its native coordinate. No entity was invented and its synthetic ID remains unchanged.
- Moore (author), Kaigun, Manchester (author) and Yuehan Railway are now non-LOC targets. These four status corrections are not counted as correct geolocations.
- Wrong results still include China → Okinawa, Queen Charlotte’s → New Zealand, generic Building → Texas, Supreme Court building → Hong Kong, and Royal Chapel → Belgium. These have no supported connection to the intended entity in Daniel’s text.
- Unverified: Dutch Borneo (row 24), Taganrog (row 60), Masaya (row 83), Trafalgar (row 97).
- No geometry: Galoeng Galoeng (row 1), Buna-Gona (row 6).

## Execution, controls and limits

- Ranking elapsed time: **254.87 seconds (4 minutes 15 seconds)**. This is ranking-stage time, not the total preparation and evidence-review duration.
- 212 request receipts: 159 reused and 53 newly retrieved by the existing workflow.
- 43 candidate-only Wikidata records were obtained from the agreed BigQuery snapshot and cached. They supplied geometry evidence; they did not add Entity rows or replace synthetic identity IDs. Complete population-source results were subset locally with their original receipts.
- Latest matching outputs already use the approved 10% conflicting-type penalty, 5% penalty for measured relevance below 1%, and 80% adjusted-score cutoff. Matching was not run again in this bounded Geography test.
- Geography weights remain QID 45, coordinates 30, context 15, name 7, type 3, with existing candidate-only QID points and distance bands. The highest available valid geometry remains selected without a minimum score. No new acceptance rule was added.
- All 100 original mention IDs and Daniel texts were preserved. Twelve entity IDs differ from the prior reviewed run.
- 57 review verdicts were reused only where identity, source object and exact native geometry were unchanged. All 37 changed selected outputs received an explicit evidence review. Two missing and four non-LOC cases were checked separately.
- Exact geometry write/read verification passed. All 376 protected file hashes were rechecked unchanged, and every ranking output matched its verification manifest.
- This is a repeated diagnostic sample, not an independent estimate for all Daniel data. Improvements also reflect updated retrieval and native coordinates; they cannot be attributed only to matching penalties. No source geometry, matching rule or main model table was edited.

Focused verification: **19 tests passed** across the cohort adapter, Geography ranking, population wrapper and BigQuery OSM handling. Black formatting and Git whitespace checks passed. The completed source/ranking outputs are reused; these checks did not repeat external retrieval.

## Artifacts and rerun

- Review ledger: [GEOGRAPHY_RANKING_100_RERUN_2026-10-23.json](GEOGRAPHY_RANKING_100_RERUN_2026-10-23.json), with all 100 judgments, exact IDs, source links, evidence reasons, policy flags and SHA-256 inputs.
- Local output: `GG_Data/pipeline/outputs/geography_review_100_rerun_20261023_v2/`, including `cohort.json`, `evaluation.json`, source receipts, ranking audit and `ranking/proposed_geometries.parquet`. These generated data are ignored by Git.
- Source model: `GG_Data/pipeline/outputs/matching_penalty_poc_20261023/`.
- Frozen prior review: `docs/GEOGRAPHY_RANKING_100_REVIEW_2026-10-22.json`; it remains unchanged.
- The preparation-only folder without `_v2` is superseded. No ranking was run there.

Use `python -m GG_Data.pipeline.geography_review_rerun` in phase order `prepare`, `records`, `rank`, `compare`. `prepare` requires a fresh output folder; `records` refuses to overwrite saved candidate records. Supply `--base`, `--output`, `--previous-review` for preparation/comparison and `--request-cache` for ranking as applicable. Comparison leaves changed cases as REVIEW_REQUIRED until evidence review; it never converts a ranking score into a correctness label.

## All original examples

Previous judgments are reused only under the exact-match condition above. Source names below are the selected native objects; see the JSON ledger for original text, IDs, receipts and reasons.

| Row | Daniel name | Before | Now | Selected object | Review | Flags |
|---:|---|---|---|---|---|---|
| 1 | Galoeng Galoeng | MISSING | MISSING | — | Reviewed |  |
| 2 | Yunnan | CORRECT | CORRECT | OpenStreetMap: 云南省 | Reviewed |  |
| 3 | Ukraine | CORRECT | CORRECT | OpenHistoricalMap: Украинская ССР | Reviewed | HISTORICAL_BOUNDARY_DATE_WARNING |
| 4 | Spoleto | CORRECT | CORRECT | Wikidata: Spoleto | Reviewed |  |
| 5 | Dieppe | CORRECT | CORRECT | OpenStreetMap: Dieppe | Reviewed |  |
| 6 | Buna-Gona | MISSING | MISSING | — | Reviewed |  |
| 7 | Madagascar | CORRECT | CORRECT | OpenStreetMap: Madagasikara | Reviewed |  |
| 8 | Shoreham Hotel | CORRECT | CORRECT | Wikidata: Omni Shoreham Hotel | Reused |  |
| 9 | Assab | CORRECT | CORRECT | OpenStreetMap: ዓሰብ Assab عصب | Reviewed |  |
| 10 | Pabedan Township | CORRECT | CORRECT | Wikidata: Pabedan Township | Reviewed |  |
| 11 | China | INCORRECT | INCORRECT | OpenStreetMap: 沖縄県 | Reviewed |  |
| 12 | Yorktown | INCORRECT | INCORRECT | OpenStreetMap: Yorktown | Reused |  |
| 13 | Heilongjiang Province | CORRECT | CORRECT | OpenStreetMap: 黑龙江省 | Reused |  |
| 14 | New York | CORRECT | CORRECT | OpenHistoricalMap: New York | Reused |  |
| 15 | Queen Charlotte's | INCORRECT | INCORRECT | Wikidata: Queen Charlotte | Reviewed |  |
| 16 | Caucasus | CORRECT | CORRECT | Wikidata: 高加索 | Reused |  |
| 17 | Alaska | CORRECT | CORRECT | OpenHistoricalMap: Alaska | Reused |  |
| 18 | Nikolaevsk | INCORRECT | INCORRECT | OpenStreetMap: Миколаїв | Reused |  |
| 19 | Xcaret | CORRECT | CORRECT | Wikidata: Xcaret | Reused |  |
| 20 | Ironbottom Sound | CORRECT | CORRECT | OpenStreetMap: Ironbottom Sound | Reused |  |
| 21 | Yugoslavia | CORRECT | CORRECT | OpenHistoricalMap: Jugoslavija / Југославија | Reused |  |
| 22 | Monte Artemisio | CORRECT | CORRECT | Wikidata: Monte Artemisio | Reused |  |
| 23 | Clermont-Ferrand | CORRECT | CORRECT | OpenStreetMap: Clermont-Ferrand | Reviewed |  |
| 24 | Dutch Borneo | UNVERIFIED | UNVERIFIED | OpenStreetMap: Borneostraat | Reused |  |
| 25 | Dresden | CORRECT | CORRECT | OpenStreetMap: Dresden | Reviewed |  |
| 26 | Bangkusay | INCORRECT | INCORRECT | OpenStreetMap: Bangkusay | Reused |  |
| 27 | Moore | INCORRECT | NON_LOC | — | Reviewed |  |
| 28 | Anchorage | CORRECT | CORRECT | OpenStreetMap: Anchorage | Reviewed |  |
| 29 | Sigmaringen | CORRECT | CORRECT | OpenStreetMap: Sigmaringen | Reviewed |  |
| 30 | Hungary | CORRECT | CORRECT | OpenHistoricalMap: Magyar Királyság | Reused |  |
| 31 | Prague | CORRECT | CORRECT | Wikidata: Prague | Reused |  |
| 32 | Konkoita | MISSING | CORRECT | Wikidata: Konkoita | Reviewed |  |
| 33 | Geneva | CORRECT | CORRECT | OpenStreetMap: Genève | Reviewed |  |
| 34 | Germany | CORRECT | CORRECT | Wikidata: 魏瑪共和国 | Reused |  |
| 35 | Marchwacz | CORRECT | CORRECT | Wikidata: Marchwacz | Reused |  |
| 36 | Hawaiʻi | CORRECT | CORRECT | OpenStreetMap: Hawaiʻi | Reviewed |  |
| 37 | Zanana | CORRECT | CORRECT | Wikidata: Zanana | Reused |  |
| 38 | Dongjiang | INCORRECT | INCORRECT | OpenStreetMap: 东江街道 | Reused |  |
| 39 | Mount Coot-tha | CORRECT | CORRECT | OpenStreetMap: Mount Coot-tha | Reused |  |
| 40 | French Algeria | CORRECT | CORRECT | OpenHistoricalMap: Algérie française | Reused |  |
| 41 | Shanghai | CORRECT | CORRECT | Wikidata: Shanghai | Reused |  |
| 42 | Tohiti | INCORRECT | INCORRECT | GeoNames: Ottville | Reused |  |
| 43 | Kaigun | INCORRECT | NON_LOC | — | Reviewed |  |
| 44 | Building | INCORRECT | INCORRECT | Wikidata: Building | Reviewed |  |
| 45 | Fremantle | CORRECT | CORRECT | Wikidata: Fremantle | Reused |  |
| 46 | Enkaku | CORRECT | CORRECT | Wikidata: 圓覺寺 | Reused |  |
| 47 | Sri Ayutthaya | INCORRECT | INCORRECT | GeoNames: Lake Sweetwater | Reused |  |
| 48 | Manchester | INCORRECT | NON_LOC | — | Reviewed |  |
| 49 | Wilhelmshaven | CORRECT | CORRECT | OpenStreetMap: Wilhelmshaven | Reviewed |  |
| 50 | Zuihō | CORRECT | CORRECT | Wikidata: Дзуйхо | Reused |  |
| 51 | Fort Randall Army | INCORRECT | INCORRECT | OpenHistoricalMap: Ft. Randall Mil Res County | Reused |  |
| 52 | Brunei | CORRECT | CORRECT | Wikidata: Brunei | Reused |  |
| 53 | North Stradbroke Island | CORRECT | CORRECT | OpenStreetMap: North Stradbroke Island | Reused |  |
| 54 | Akasaka Palace | CORRECT | CORRECT | OpenStreetMap: 迎賓館 | Reviewed |  |
| 55 | Malaya | INCORRECT | CORRECT | Wikidata: Federatie van Malaya | Reviewed | HISTORICAL_IDENTITY_MISMATCH |
| 56 | French Indochina | CORRECT | CORRECT | Wikidata: 法属印度支那 | Reused |  |
| 57 | Iraq | CORRECT | CORRECT | OpenHistoricalMap: العراق | Reused |  |
| 58 | Italy | CORRECT | CORRECT | OpenHistoricalMap: Italia | Reused |  |
| 59 | 's Islands | INCORRECT | INCORRECT | OpenStreetMap: South | Reviewed |  |
| 60 | Taganrog | UNVERIFIED | UNVERIFIED | OpenStreetMap: городской округ Таганрог | Reviewed |  |
| 61 | Tomoya | INCORRECT | INCORRECT | GeoNames: Tomoya | Reused |  |
| 62 | Kingdom of | INCORRECT | INCORRECT | OpenStreetMap: Universal United Kingdom Resort | Reviewed |  |
| 63 | Central Asia | CORRECT | CORRECT | Wikidata: 중앙아시아 | Reused |  |
| 64 | Navy Yard | INCORRECT | INCORRECT | Wikidata: Navy Yard | Reused |  |
| 65 | Leśno | CORRECT | CORRECT | Wikidata: Leśno | Reused |  |
| 66 | Supreme Court building | INCORRECT | INCORRECT | OpenStreetMap: 終審法院 The Court of Final Appeal | Reviewed |  |
| 67 | Bottomside | INCORRECT | INCORRECT | OpenStreetMap: Bottomside BA | Reused |  |
| 68 | Karafuto Prefecture | CORRECT | CORRECT | OpenHistoricalMap: 樺太庁 | Reused |  |
| 69 | Tunis | CORRECT | CORRECT | OpenHistoricalMap: Protectorat français de Tunisie | Reviewed | COUNTRY_WIDE_APPROXIMATION_FOR_CITY, IDENTITY_GRANULARITY_REGRESSION |
| 70 | Vangunu Island | CORRECT | CORRECT | Wikidata: 旺乌努岛 | Reviewed |  |
| 71 | Ceylon | CORRECT | CORRECT | OpenHistoricalMap: British Ceylon | Reused |  |
| 72 | Aleipata Islands | CORRECT | CORRECT | Wikidata: Aleipata-Inseln | Reused |  |
| 73 | Legation Quarter | CORRECT | CORRECT | Wikidata: 东交民巷 | Reused |  |
| 74 | White House | CORRECT | CORRECT | OpenHistoricalMap: White House | Reused |  |
| 75 | Central Europe | CORRECT | CORRECT | Wikidata: Europa Środkowo-Wschodnia | Reviewed |  |
| 76 | Czernowitz | CORRECT | CORRECT | Wikidata: 切尔诺夫策 | Reused |  |
| 77 | Crete | CORRECT | CORRECT | Wikidata: Kreta | Reused |  |
| 78 | Syria | CORRECT | CORRECT | Wikidata: Síria otomana | Reused |  |
| 79 | Margaret Street | CORRECT | CORRECT | Wikidata: Margaret Street | Reused |  |
| 80 | New Georgia | CORRECT | CORRECT | OpenStreetMap: New Georgia | Reused |  |
| 81 | Royal Chapel | INCORRECT | INCORRECT | OpenStreetMap: Église Saint-Joseph | Reviewed |  |
| 82 | Schweinfurt | CORRECT | CORRECT | OpenStreetMap: Schweinfurt | Reviewed |  |
| 83 | Masaya | UNVERIFIED | UNVERIFIED | OpenStreetMap: Masaya | Reused |  |
| 84 | Los Alamos | CORRECT | CORRECT | OpenStreetMap: Los Alamos | Reviewed |  |
| 85 | Fântâna Albă | CORRECT | CORRECT | Wikidata: Bila Krynyzja | Reviewed |  |
| 86 | Betano | CORRECT | CORRECT | Wikidata: Betano | Reused |  |
| 87 | South East Busway | CORRECT | CORRECT | Wikidata: バスウェイ | Reused |  |
| 88 | Mevatanana | CORRECT | CORRECT | Wikidata: Maevatanana | Reused |  |
| 89 | Indonesia | CORRECT | CORRECT | OpenStreetMap: Nusantara | Reused |  |
| 90 | Yuehan Railway | INCORRECT | NON_LOC | — | Reviewed |  |
| 91 | Wallis | CORRECT | CORRECT | Wikidata: 瓦利斯岛 | Reviewed |  |
| 92 | Waco | INCORRECT | CORRECT | OpenStreetMap: Waco | Reviewed |  |
| 93 | Bhimbetka | CORRECT | CORRECT | Wikidata: Bhimbetka | Reviewed |  |
| 94 | Dutch East Indies | INCORRECT | CORRECT | OpenHistoricalMap: Nederlands-Indië | Reviewed |  |
| 95 | Oryol Oblast | CORRECT | CORRECT | OpenHistoricalMap: Орловская область | Reviewed |  |
| 96 | German New Guinea | CORRECT | CORRECT | Wikidata: Nova Guinea Todésca | Reused |  |
| 97 | Trafalgar | UNVERIFIED | UNVERIFIED | OpenStreetMap: Trafalgar | Reused |  |
| 98 | Terminal | INCORRECT | INCORRECT | OpenStreetMap: Terminal | Reused |  |
| 99 | Mesopotamia | CORRECT | CORRECT | OpenStreetMap: Mesopotamia / Mezopotamya / Μεσοποταμία / بلاد الرافدين / ܒܝܬ ܢܗܪܝܢ | Reused |  |
| 100 | Brisbane | CORRECT | CORRECT | OpenStreetMap: Brisbane Airport | Reviewed | IDENTITY_GRANULARITY_REGRESSION |
