# Geography candidate comparison: 40 inputs, 22 October 2026

## Result and decision boundary

The alternative WHG query increased reference-identifier coverage in its first
ten candidates from **10/17 to 13/17 QID inputs**. First-result agreement rose
from **5/17 to 8/17**. These are identifier-agreement measurements, not precision
or verified historical-geometry success rates. The experiment does not justify
automatic acceptance of a top name result.

**Status: `VERIFIED_CANDIDATE_COMPARISON_ONLY`.** No new QID, synthetic identity,
type, geometry, Geography row or graph output was assigned. No production
threshold, date rule or source priority changed. London and Java retain their
two previously verified geometries; the original eight unresolved cases remain
unresolved. The other 30 inputs received candidate/evidence diagnostics, not
30 completed geometry-selection runs.

## Population and reproducible method

The corrected 10K POC has 1,261 LOC targets: 956 QIDs and 305 synthetic IDs.
The test freezes the original ten regression inputs, then draws 15 additional
QIDs and 15 additional synthetic IDs with seed `20261022`, from pools sorted by
ID. It keeps every chosen input, including punctuation. There are 17 QIDs and
23 synthetic IDs in the resulting 40. This stratified sample is not suitable
for estimating the full-population match rate.

Thirty-eight names contain a letter or number and enter both query arms.
`.` and `'` remain visible as unsearchable inputs. Thirty-nine inputs have an
English Wikipedia source-page reference; one punctuation input has no resolved
page. There are no Japanese source pages in this sample. Saved Japanese labels
are retained as evidence, but bilingual query effectiveness was not tested.

Both arms use WHG `/reconcile`, `mode=fuzzy`, `limit=10`, and the unchanged
entity name. Each arm uses one batched request with 38 record keys:

| Arm | Query differences |
|---|---|
| Existing dated query | Selection year as `start=end`, `undated=true`, `temporal_mode=definitely`; no country filter. |
| Native context query | No query-time date filter; an ISO country filter only when saved P17/P297 evidence yields one unambiguous code. Eight inputs receive a country filter. |

The second arm changes both country scoping and date filtering. The test cannot
attribute its overall gain to either change separately. Removing the search
date filter is diagnostic only: the production historical-validity checks
remain required before geometry selection.

Two further requests collect OHM and OSM exact-QID tags for the 17 QIDs. Raw
responses, query payloads, retrieval times and checksums are saved. This query
inventory does not download full geometries. The diagnostic queries all names;
it does not change the production WHG trigger of zero or multiple combined
exact-QID candidates.

Reference agreement means a returned identifier equals the input QID, a saved
P1566 GeoNames ID, or an OHM/OSM object explicitly tagged with that QID in the
retrieved response. It is not an independent check of the original matching
decision. Different source IDs can represent the same place or different
places. A missing reference among ten results does not prove source absence.
Synthetic inputs have no approved identity reference and are not included in
the 17-input identifier-agreement denominator.

## Measurements

| Measurement | Existing dated | Native context |
|---|---:|---:|
| Inputs with returned candidates | 38/38 searchable | 38/38 searchable |
| QIDs with reference ID in first ten | 10/17 | 13/17 |
| First result agrees with reference ID | 5/17 | 8/17 |
| Queries with several distinct IDs tied at top score | 18/38 | 17/38 |
| Newly accepted geometries | 0 | 0 |

Reference coverage gains: Java, England, Federation of Malaya, New Spain and
German New Guinea. Losses: Bora Bora and Sakhalin. Net gain: three inputs.
This list describes candidate retrieval, not acceptance at a WWII date.

All four network requests succeeded, with no retries, in **66.103 seconds**.
The final local analysis took **6.375 seconds**; these timings exclude code,
tests, investigation and document preparation. They are not a full 10K runtime
estimate.

## Findings that affect a general workflow

1. **Exact identity remains stronger than a name rank.** Both WHG arms put a
   GeoNames place called London in Italy first. The existing London geometry
   remains linked to Q84 through exact source evidence. Java improves from an
   Angola namesake to the expected Indonesian GeoNames record when scoped to
   Indonesia, but no identity or geometry is replaced.
2. **A geopolitical parent is not always the gazetteer's country code.** Bora
   Bora has saved P17 France evidence, yielding `FR`; the expected gazetteer
   candidate uses `PF`. The native result loses both its saved QID and GeoNames
   reference. Do not promote this country-code derivation into a hard production
   filter without a general treatment of territories and source metadata.
3. **Identity coverage does not establish historical suitability.** The native
   query finds New Spain's QID, but every exact-QID OHM object returned for it
   ends before its 1941 selection date. Recovering a name candidate does not
   authorize a WWII geometry. Likewise, an undated search can expose postwar
   records that still need the approved date checks.
4. **The existing context parser is a separate bottleneck.** All 14 searchable
   additional synthetic inputs lack a feature recognized by the current
   seven-class literal parser. Names such as Mayu Range, Conical Hill and Chosŏn
   Volunteer Cemetery are outside that parser's vocabulary. This does not prove
   that Daniel omitted useful context. Missing parser output is not equivalent
   to a missing reference place. No extra class or acceptance rule was added.
5. **The unresolved original cases have different causes.** Hoosick Falls has
   several candidate representations; Tinian Town and Sunharon Bay have useful
   name candidates but insufficient verified parent evidence; Crabbs/Crabs has
   a spelling difference; Pocatello and Piva Yoke still have poor WHG top hits;
   Donbaik has a useful recorded alias but lacks the required checked context.
   Candidate discovery alone does not remove these acceptance blockers.
6. **A tie is a warning, not proof of several real places.** The native arm has
   17 top-score ties across distinct IDs. Cross-source duplicates, point versus
   boundary representations and namesakes must remain distinguishable. This
   test does not add a distance, containment or popularity tie-break rule.

The baseline inventory for the 30 added inputs is: nine QIDs have date/type
eligible exact-QID tag candidates with geometry still untested; six QIDs lack
such an eligible exact-QID candidate and would need the existing fallback;
14 searchable synthetic inputs are blocked by the existing feature parser;
one punctuation input is unsearchable. These categories are not 30 final
geocoding outcomes. Only the original ten reuse completed geometry decisions.

## Relationship to the project research

WHG's published guidance separates candidate retrieval from place-identity
confirmation. Its score is relative to a query; a top score of 100 can accompany
a poor candidate. Its country and date fields are hard filters with coverage
risks. This experiment follows that distinction rather than adding exceptions
for the four original difficult names. See the [official WHG API documentation](https://docs.whgazetteer.org/content/technical/apis.html).

The earlier research also examined [GeoHistoricalData](https://github.com/GeoHistoricalData/historical_geocoding),
[T-Res](https://living-with-machines.github.io/T-Res/getting-started/complete-tour.html)
and [Perdido](https://ceur-ws.org/Vol-3385/paper3.pdf). Their code/models were
not installed or run in this experiment. No accuracy claim for them is made.
Nominatim remains an existing candidate/original-geometry provider; this test
does not introduce a new Nominatim search or change its acceptance role.

The next decision is about a general structured context interface, especially
verified geographic parent IDs and source-compatible feature types. This test
has not defined or approved that interface. It does not support replacing the
existing identity checks with WHG's first hit or a lower similarity threshold.

## Artifacts, verification and recovery

- Implementation: `GG_Data/pipeline/geography_comparison.py`.
- Focused checks: `test_geography_comparison.py` and the existing context tests.
- Output directory: `GG_Data/pipeline/outputs/geography_comparison_40_20261022`.
- `sample.json`, `evidence.json`, `queries.json`, `plan.json`: frozen sample,
  original evidence, requests and protected input hashes.
- `sources/`: both complete WHG result sets and complete OHM/OSM tag responses,
  including raw response bytes; credentials and authorization headers excluded.
- `audit.json`: all 40 inputs, evidence, baseline status, reference IDs and arm
  profiles. `comparison.csv`: 80 flat input/arm rows. `verification.json`:
  counts and output hashes.

The model, mentions and original ten-input output hashes passed verification.
All seven focused tests and Ruff passed. The test checks that a perfect name
score, a tied expected ID, or even first-result reference agreement cannot
create an accepted geometry. No Agent or full-pipeline validation is claimed.

The code, tests and this report are suitable for a local Git checkpoint.
The output directory is ignored by Git; its local caches are not an off-device
backup. Exact replay of these live-source results requires retaining those
caches. Re-querying the same names later can return a different live index.

Cached analysis replay, without network calls:

```powershell
python -m GG_Data.pipeline.geography_comparison analyze --output GG_Data/pipeline/outputs/geography_comparison_40_20261022
python -m pytest GG_Data/pipeline/test_geography_comparison.py GG_Data/pipeline/test_geography_context_sample.py -q
```

## All 40 inputs

`O` = original ten; `Q` = added random QID; `S` = added random synthetic.
Rank columns list reference-identifier positions in the first ten results;
`none` means absent there; `n/a` means no approved reference ID. Native top
candidates below are observations, **not accepted assignments**. Full original
IDs, candidates and text evidence remain in the audit.

| # | Cohort | Input | ID | Dated reference ranks | Native reference ranks | Native first candidate |
|---:|:---:|---|---|---|---|---|
| 1 | O | London | Q84 | none | none | London (place:gn:10293491; IT) |
| 2 | O | Hoosick Falls | SYN_7ff525261d2b6a91bff0ef42 | n/a | n/a | Hoosick Falls (place:osm:n1744460703; US) |
| 3 | O | Java | Q3757 | none | 1, 2 | Java (place:gn:1642673; ID) |
| 4 | O | Tinian Town | SYN_42cf906b118d1567aa031500 | n/a | n/a | JP Tinian Town pre-WW2 (place:gn:4041558; MP, US) |
| 5 | O | Sunharon Bay | SYN_8b3229a1addcbdc9c46d8fff | n/a | n/a | Sunharon Bay (place:wd:Q101048967; MP) |
| 6 | O | Piva Yoke | SYN_01912ac9cc98235e83235ce0 | n/a | n/a | 背負沢川 (place:osm:w132958719; JP) |
| 7 | O | Crabbs Peninsula | SYN_0217e26726c06075914ce081 | n/a | n/a | Crabs Peninsula (place:wd:Q21052107; AG) |
| 8 | O | Pocatello Army Air Base | SYN_06cabd2d31a60683159f2824 | n/a | n/a | Port-la-Joye–Fort Amherst (place:wd:Q3398320; CA) |
| 9 | O | Donbaik | SYN_0836391c7551a8007835210f | n/a | n/a | Done Paik (place:gn:1326299; MM) |
| 10 | O | . | SYN_092024bf94bc1388c0fe0df9 | n/a | n/a | not searched |
| 11 | Q | Panaon | Q523781 | 4, 6 | 5, 7 | Panaon (place:gn:1695668; PH) |
| 12 | Q | England | Q21 | none | 8 | England (place:gn:1005436; ZA) |
| 13 | Q | Portuguese Macau | Q3916279 | 1, 2, 3 | 1, 2, 3 | Portuguese Macau (place:wd:Q3916279; country not supplied) |
| 14 | Q | Bora Bora | Q183113 | 3, 4 | none | Gare de Bourbourg (place:wd:Q2243517; FR) |
| 15 | Q | Lebanon | Q822 | none | none | Lebanon (place:tm:16752; LB) |
| 16 | Q | Federation of Malaya | Q1479726 | none | 5 | Federation of Malaya (place:clio:federation_of_malaya_1958_1960; MY, TH, SG) |
| 17 | Q | Denpasar | Q11506 | 1, 5 | 1, 2, 4, 5, 10 | Denpasar (place:osm:n274113797; ID) |
| 18 | Q | Khabarovsk Krai | Q7788 | 1, 2 | 1, 2, 4, 5, 6, 7, 8, 9, 10 | Khabarovskiy Kray (place:gn:2022888; RU) |
| 19 | Q | New Spain | Q170603 | none | 1 | New Spain (place:wd:Q170603; MX) |
| 20 | Q | German New Guinea | Q165008 | none | 3 | German Marshall Islands Colony -1914 (place:gn:7670500; MH, DE) |
| 21 | Q | Northern Mariana Islands | Q16644 | 3 | 1, 2, 5, 6 | Northern Mariana Islands (place:osm:n9526689314; MP, US) |
| 22 | Q | Aachen | Q1017 | 3, 4, 5 | 6, 7, 9 | Aachen (place:gn:10238853; GB) |
| 23 | Q | Arabian Sea | Q58705 | 1, 2, 4 | 1 | Arabian Sea (place:gn:1158455; IN, IR, MV, OM, PK, SO, YE) |
| 24 | Q | Sakhalin | Q7792 | 8 | none | Sakhalin (place:gn:1493240; RU) |
| 25 | Q | Điện Biên Phủ | Q36027 | 1, 2 | 1, 2, 3, 4 | Điện Biên Phủ (place:osm:n428504674; VN) |
| 26 | S | of Borneo | SYN_3ead5f848fc304229fb72978 | n/a | n/a | Borneo (place:wd:Q36117; ID) |
| 27 | S | Chosŏn Volunteer Cemetery | SYN_1c3a4e0c7143f6312086b1e6 | n/a | n/a | Joseon (place:wd:Q28179; KR) |
| 28 | S | Dongbiandao | SYN_5a6087f1b7f228cec9d1f169 | n/a | n/a | Dongbianduan (place:gn:12165321; CN) |
| 29 | S | État des Alaouites | SYN_59a874ad06e273c01d79e412 | n/a | n/a | État des Alaouites (place:ohm:r2863996; SY, LB, TR) |
| 30 | S | Mayu Range | SYN_8f81f6079bfac3baafc72fcb | n/a | n/a | Mayu Taungdan (place:gn:1309910; MM) |
| 31 | S | Champaign | SYN_30408a482da5e35649eec796 | n/a | n/a | Champaign (place:gn:4887158; US) |
| 32 | S | Royal | SYN_42aba83bbeb0ddfc5983614d | n/a | n/a | Royal (place:gn:10111465; RO) |
| 33 | S | South | SYN_dd0f815ce002f2c50a17a811 | n/a | n/a | South (place:osm:n153359809; US) |
| 34 | S | Chu Lai Advance Base | SYN_340cd559de24bf73527abbce | n/a | n/a | Steegse Haven (place:wd:Q19547496; NL) |
| 35 | S | New Strip | SYN_64fa35fd0e49eac676be4bb9 | n/a | n/a | Tendu (SAPC) weather station (place:wd:Q118246623; FR) |
| 36 | S | Kohima Ridge | SYN_c7f90cedca4e87aa510e3704 | n/a | n/a | Kohima Village (place:wd:Q55685174; IN) |
| 37 | S | Conical Hill | SYN_0343ac99d88e9310d4bdc36b | n/a | n/a | Conical Hill (place:gn:1716944; PH) |
| 38 | S | Taganrog | SYN_317e53df20ea48eb610cd6cb | n/a | n/a | Taganrog (place:gn:484907; RU) |
| 39 | S | Oceans | SYN_TYPE_UNKNOWN_a56947e0650335a774097244 | n/a | n/a | Oceans (place:tgn:7594545; country not supplied) |
| 40 | S | ' | SYN_418366f3300bd65569207805 | n/a | n/a | not searched |
