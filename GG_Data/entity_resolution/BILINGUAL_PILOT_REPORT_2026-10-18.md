# Bilingual entity-matching pilot — 18 October 2026

Status: completed example run, mechanically verified. Automatic matches are not validated identity truth. No manual match choices or overrides were used. The canonical graph is unchanged.

Current run: `runs/bilingual_pilot_20261018_v1`. The initial run is preserved in `runs/bilingual_pilot_20261018` and local commit `939fd1d`. The current run fixes calendar-month type coverage and excludes Wikidata properties from item candidates. It reuses the initial run's verified fresh metadata, with its source hash recorded.

## Results

All **362** Daniel mentions from three pages were processed, including repeated mentions and all five types.

| Page | Page pass | Already-matched pass | Fresh WWII pass | Synthetic | Total |
|---|---:|---:|---:|---:|---:|
| 1st Mobile Fleet (Imperial Japanese Navy) | 5 | 0 | 0 | 9 | 14 |
| 14th Indian Infantry Division | 115 | 4 | 10 | 64 | 193 |
| 1943 Cairo Declaration | 109 | 0 | 1 | 45 | 155 |

Total: **244 automatic matches**, **118 distinct synthetic mention IDs**. Unresolved reasons: **99** with no qualifying name, **17** type conflicts, **2** without enough type evidence. A synthetic ID does not establish a new real-world entity. Repeated mentions can share a matched QID; synthetic IDs are always separate.

## Open the example

- [Executed step-by-step notebook](BILINGUAL_PILOT_STEP_BY_STEP.ipynb): replay all three passes offline; change the threshold from 0.80 to 1.00, page, random seed, or inspected mention. All 362 assigned IDs are checked against the saved result at the default settings.
- [Filterable result and independent page lists](runs/bilingual_pilot_20261018_v1/report.html).
- [Every Daniel mention and result](runs/bilingual_pilot_20261018_v1/matches.csv).
- [Independent provisional page candidate lists](runs/bilingual_pilot_20261018_v1/page_inventory.csv).
- [Summary](runs/bilingual_pilot_20261018_v1/summary.json) and [run manifest](runs/bilingual_pilot_20261018_v1/run_manifest.json).

## Simple pipeline

1. Resolve each Daniel source title to its English Wikipedia page ID and Wikidata QID. Fetch the linked Japanese article when available. English and Japanese pages have different local Wikipedia page IDs, but the same entity has one Wikidata QID.
2. Read full article content, including infoboxes, tables, captions, references and bibliography. Collect article links and automatic phrases independently of Daniel's mentions. Remove navigation templates. English extraction uses capitalized phrases; Japanese extraction uses dictionary noun phrases that contain proper nouns. Year strings are also collected.
3. Resolve linked pages to QIDs. For unlinked phrases, look up exact English/Japanese Wikidata labels and aliases in batches, including case variants. Preserve all matching item candidates; exclude properties, disambiguation pages and Wikimedia lists. The candidate list is provisional, not proof that every returned homonym occurs in the article.
4. Match Daniel mentions against the combined English/Japanese page pool. Filter incompatible types, then select the highest Unicode-normalized character-trigram Dice score at least 0.80. There is no HITS ranking. Choose randomly between equal-highest QIDs using seed `20261018`, separately keyed by mention ID and stage.
5. Freeze the QIDs matched in pass 1. Match unresolved mentions against only those IDs' saved names across the three selected pages. Do not add pass-2 matches to this frozen pool.
6. Match remaining mentions against the fresh WWII set using the same score, threshold, type and tie rules. Give each remaining mention its own `SYN_...` ID. Use `SYN_TYPE_...` for type conflicts and `SYN_TYPE_UNKNOWN_...` for missing type evidence.

## Article evidence

| Daniel source | Language | Wikipedia page ID | Wikidata QID | Revision |
|---|---|---:|---|---:|
| 1st Mobile Fleet (Imperial Japanese Navy) | en | 29607850 | Q4596490 | [1323366204](https://en.wikipedia.org/w/index.php?oldid=1323366204) |
| 1st Mobile Fleet (Imperial Japanese Navy) | ja | 1291607 | Q4596490 | [101873495](https://ja.wikipedia.org/w/index.php?oldid=101873495) |
| 14th Indian Infantry Division | en | 8245289 | Q4550030 | [1343287212](https://en.wikipedia.org/w/index.php?oldid=1343287212) |
| 1943 Cairo Declaration | en | 248345 | Q702120 | [1356482833](https://en.wikipedia.org/w/index.php?oldid=1356482833) |
| 1943 Cairo Declaration | ja | 381963 | Q702120 | [111206216](https://ja.wikipedia.org/w/index.php?oldid=111206216) |

The retrieved Wikidata item for **14th Indian Infantry Division** has no Japanese Wikipedia sitelink. The two other pages have Japanese counterparts.

## Fresh WWII population

A new Wikidata query returned **103,235 QIDs**. Every ID was included in the name collection, without a result limit. There are **163,069 unique QID/name pairs** after duplicate names within each QID are removed; **20,684 QIDs** have no English or Japanese label/alias in these results. Those IDs cannot match a name in this pilot. The old 144,990-ID graph was not used.

The exact population is items with conflict or participation statements for WWII or a part of WWII, items that are part of WWII, or items whose main subject is WWII. This is an explicit query boundary, not a claim to contain every semantically WWII-related entity. Queries, retrieval times and hashes are saved in the manifest.

```sparql
SELECT DISTINCT ?item WHERE {
  { ?item wdt:P607/wdt:P361* wd:Q362 }
  UNION { ?item wdt:P1344/wdt:P361* wd:Q362 }
  UNION { ?item wdt:P361+ wd:Q362 }
  UNION { ?item wdt:P921 wd:Q362 }
}
```

## Real decision examples

| Daniel mention | Automatic result | Score | Stage | What this shows |
|---|---|---:|---|---|
| 1st Mobile Fleet | Q4596490 — 1st Mobile Fleet / 第一機動艦隊 | 1.000 | Page | One QID for both languages |
| Commander in chief (`PER`) | Separate `SYN_TYPE_...` | — | All three passes | A role candidate cannot pass the human type check |
| March (`DATE`) | Q110 — March / 3月 | 1.000 | Page | Calendar months now pass the date type check |
| Mayforce | Q3219966 — Layforce | 0.833 | Fresh WWII | Wrong identity can still pass the chosen threshold |
| Alfred Curtis | Q8001772 — Wilfred Curtis | 0.870 | Fresh WWII | Similar personal names can refer to different people |
| 6th Brigade | Q4645308 — 8th Brigade | 0.889 | Fresh WWII | Trigrams can underweight a different unit number |
| British | Q9309 — Welsh, using alias British | 1.000 | Already matched | Exact ambiguous aliases can propagate an incorrect match |

These examples were inspected after the automatic run. No result was replaced or corrected by hand. Counts measure rule acceptance, not linking accuracy. Raising the threshold alone cannot fix exact-name homonyms or ambiguous aliases.

## Type and coverage limits

Type checks use saved P31 types and the complete reachable non-deprecated P279 class edges. The manifest records the broad roots for humans, organizations/military units, places and calendar dates/years/months. `MISC` is the residual known type category; missing P31 evidence remains unknown.

Type conflicts can come from Daniel's tag, our broad type map, or Wikidata's hierarchy. They do not prove Daniel's data is wrong. For example, the saved hierarchy links military campaign through campaign to organization, so Burma Campaign was rejected for Daniel's `MISC` tag. [Wikidata campaign](https://www.wikidata.org/wiki/Q6056746) shows this broad classification. Calendar months use [Q47018901](https://www.wikidata.org/wiki/Q47018901).

Full article processing does not guarantee complete extraction. Lexical phrases can miss or join names. Exact unlinked-name lookup misses spelling variants and names without a label/alias. Several bibliography mentions in the fleet page remain unresolved. The provisional page pools also contain homonymous candidates that may be unrelated to the article. These are limits of this first collector, separate from the trigram matching rule.

The user-approved random tie rule can select different QIDs for repeated ambiguous mentions. All tied IDs and each stage's rejection evidence remain in `matches.json.gz`. Synthetic IDs are stable for the same pinned input row and mention span.

## Verification and rerun

The run checks the raw-input hash, all 362 raw rows, unique mention IDs, separate synthetic IDs, QID-only page pools, compatible types, exact scores and stage-pool membership. The executed notebook independently reproduces all 362 assigned IDs at 0.80. A second in-memory execution at 0.90 also passed without live metadata requests. All current artifact hashes, all 362 CSV/HTML result rows and all 2,238 page/QID inventory pairs were checked. Ruff and both unit checks passed. Unit checks cover highest compatible scores, bilingual aliases, seeded ties, unknown/conflicting types, inheritance cycles, calendar months and exclusions.

```powershell
python -m pytest -q GG_Data/entity_resolution/test_bilingual_page_pilot.py
python -m ruff check GG_Data/entity_resolution/bilingual_page_pilot.py GG_Data/entity_resolution/test_bilingual_page_pilot.py
python GG_Data/entity_resolution/bilingual_page_pilot.py --output GG_Data/entity_resolution/runs/<new-name> --metadata-snapshot GG_Data/entity_resolution/runs/bilingual_pilot_20261018_v1/entity_metadata.json.gz
```

The online collector needs `fugashi==1.5.2` and `unidic-lite==1.0.8` in `C:\Users\User\.cache\geoai_bilingual_dependencies`. The offline notebook does not need these packages. HTTP and query caches are on C:; compact evidence is saved in the D: project. Earlier completed runs cannot be overwritten. The pinned Daniel upload hash is in the manifest; the raw parquet remains outside Git and is recoverable from the [pinned upstream upload](https://raw.githubusercontent.com/EtzionR/Corpus2GeoRAG_Pacific/43e35453421b032fc67d426d7d16fe436574b0fa/Data/georag_selected_v2_full_n36335_r482092353_20261016.parquet).

## Follow-up retained for Daniel

Ask Daniel later to include the original Wikipedia URL, language, Wikipedia page ID and revision ID/URL in each source reference. No message was sent in this task.

Backup at handoff: **Local checkpoint only**. No push was made.
