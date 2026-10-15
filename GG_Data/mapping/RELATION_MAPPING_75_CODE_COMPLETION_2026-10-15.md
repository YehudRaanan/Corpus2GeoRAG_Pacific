# Completion of the 75 missing relation mapping keys

**Date:** 2026-10-15

**Active tables:** `relation-map-v2.0.0` intermediate and `relation-map-v2.1.0` directional contract

**Scope:** The 75 source-predicate keys previously absent from the mapping tables but present in the current 700,890-assertion draft input.

**Change boundary:** All changes are inside `GG_Data`. The graph export and Agent code have not been rebuilt or changed by this work.

## 1. Result and denominators

All 75 keys now have explicit source-to-Level-2 rules, readable labels and descriptions, evidence, and an explicit opposite-direction ID and label. The runtime mapping table has **1,595 unique source keys**, up from 1,520.

| Source | Previous keys | Added keys | Current keys |
|---|---:|---:|---:|
| Wikidata | 601 | 69 | 670 |
| EventKG | 808 | 6 | 814 |
| WarSampo | 111 | 0 | 111 |
| **Total** | **1,520** | **75** | **1,595** |

The 75 source keys have 70 distinct normalized source identifiers and 68 effective Level 2 outputs. Five EventKG keys use the same Wikidata properties as five native Wikidata keys. The `owl:differentFrom` translation and the next-higher/next-lower-rank normalization further reduce the number of distinct outputs. These are different counting units; 75 is not the number of newly discovered relation meanings.

The whole catalog now has **1,064 effective Level 2 relations**, up from 1,009. The source inventory occurrence totals cover a wider source inventory than the current draft assertion export; the added keys account for 106,916 inventory occurrences but 102,154 current draft assertions. Do not interchange these denominators.

The full replay passed: **700,890 of 700,890 assertions mapped**, with **zero missing keys, zero duplicate or conflicting keys, and zero direction-contract errors**. The result is recorded in [`sanity_check_v2_1/summary.json`](sanity_check_v2_1/summary.json). This is mapping coverage, not proof that all assertion values are correct.

## 2. Why these keys were missing

The previous source inventory excluded the keys from its eligible relation list. The v1 runtime nevertheless exported them through its `runtime_independent` fallback. Both the old inventory decision and the observed assertions are preserved in the new rule ledger.

| Historical exclusion reason | Added source keys |
|---|---:|
| `PROVENANCE_OR_DOCUMENT` | 54 |
| `ATTRIBUTE` | 11 |
| `IDENTITY_LINK` | 6 |
| `TYPE_OR_SCHEMA` | 4 |
| **Total** | **75** |

These exclusions are not reliable evidence that an assertion is useless or invalid. For example, `P516` means **powered by**, but its native Wikidata row was excluded as `PROVENANCE_OR_DOCUMENT`. Its EventKG row already had a mapping. The new rule retains the exact property meaning. Metadata and type relations also need explicit mappings when the data layer exports their assertions.

This work completes the accepted current-export scope. It does not claim coverage of every predicate in every raw source dataset.

## 3. Deterministic decision rules

The reproducible build reads [`ADDITIONAL_RELATION_RULES_2026-10-15.csv`](ADDITIONAL_RELATION_RULES_2026-10-15.csv). Each row records the original source key, normalized ID, output ID, direction, prior exclusion, source count, draft count, evidence URLs, statement IDs where needed, description review, sample availability, and assertion review notes.

The decisions are:

1. **73 identifier-preserving rules.** Keep the exact source property ID, including explicit normalization of full Wikidata direct-property URIs to `wd:P...`. Prefix normalization does not identify unrelated properties with matching labels or local names.
2. **One reused formal inverse rule:** native `wd:P3730` (next higher rank) becomes `wd:P3729` (next lower rank) with swapped endpoints. The saved existing EventKG mapping and a fresh Wikidata `P1696` statement agree.
3. **One formal equivalence rule:** EventKG `owl:differentFrom` becomes `wd:P1889` without swapping endpoints. Wikidata explicitly declares the equivalent property through `P1628`. Both assert distinct individuals; Wikidata's description emphasizes items that may be confused. Preserve that usage context. Sources: [Wikidata P1889](https://www.wikidata.org/wiki/Property:P1889), [W3C OWL differentFrom](https://www.w3.org/TR/owl-ref/#differentFrom-def).

No label, keyword, description embedding, or model similarity creates a mapping. Description and example review can reject or limit a formally supported candidate.

The original **589 candidate connection decisions** remain an audit of their original scope: 403 same-code candidates plus 186 cross-identifier candidates. The 75 coverage rules have a separate evidence ledger. Zero in an added row's `connection_count` means that it has no row in that historical 589-candidate table; it does not mean that the new row lacks identifier or formal evidence.

Level 1 remains optional. An added row can reuse an existing family only for the exact accepted effective Level 2 identifier. Otherwise it remains `UNRESOLVED`; all 55 newly added effective identifiers have no new family assignment. The source assertion QA flag remains enabled on all 75 additions because the review does not establish source truth for every assertion.

## 4. Opposite directions

The active catalog contains 1,064 explicit reverse decisions:

| Reverse resolution | Effective Level 2 relations |
|---|---:|
| Formal named inverse | 88 |
| Formal symmetric/self-inverse | 13 |
| Explicit synthetic inverse | 963 |
| **Total** | **1,064** |

The lookup contains **2,097 rows for 1,055 direction pairs**: two rows for each of 1,042 non-symmetric pairs, plus one explicit self-mapping row for each of 13 symmetric properties. For a non-self symmetric assertion, the data layer must still return both endpoint directions. A lookup row describes the relation-level reversal; it is not a stored assertion.

New symmetric properties include `P1889`, `P460`, `P2959`, and `P5278`, supported by explicit Wikidata self-inverse `P1696` values. Symmetry does not permit entity merging. In particular, `P460` remains **said to be the same as**, with its uncertainty preserved; it is not strengthened to definite identity. See [Wikidata P460](https://www.wikidata.org/wiki/Property:P460).

Nine fresh reverse decisions are in [`ADDITIONAL_REVERSE_CONTRACTS_2026-10-15.csv`](ADDITIONAL_REVERSE_CONTRACTS_2026-10-15.csv). Existing saved formal inverse contracts also cover added native keys such as `P180`, `P2354`, `P2813`, `P3729`, `P3730`, and `P885`.

### Formal evidence retained but named reverse blocked

| Candidate | Formal evidence | Description/sample check | Delivered reverse |
|---|---|---|---|
| `P1343` described by source ↔ `P921` main subject | `P1343` declares `P921` through `P1696`; the fresh `P921` snapshot has no reciprocal declaration | Being described in a work does not establish that the entity is the work's main subject. EventKG also has questionable source targets. | `inverse:wd:P1343` |
| `P6803` taxon found at location ↔ `P2974` habitat | Reciprocal `P1696` declarations exist | Presence at a location does not by itself establish that the location is the taxon's natural habitat. Only one current example exists. | `inverse:wd:P6803` |

These blocks preserve the formal evidence and the reason for separation. The synthetic inverse reverses the exact original assertion without substituting the broader named predicate. The existing 11 ambiguous reverse cases remain synthetic for their original reasons.

`P885` now has its own forward row and uses the saved `P201` outflows inverse contract. Only one current example exists: Albert Canal → origin → Meuse. The focused metadata confirms that Meuse is a river. This example does not validate every possible outflow value; evaporation and seepage require scope care. The underlying saved formal statement is `P201$9f9635eb-4a3a-add8-0200-455a152171ad`.

## 5. Ten-example validation

The sample retains up to ten **distinct subject-object facts per source key**. Repeated observations of the same fact do not fill the ten-example requirement. The selection uses the lowest ten SHA256 values for seed `20261015` and the complete source/predicate/subject/object key.

| Sample result | Source keys |
|---|---:|
| Ten distinct examples available | 38 |
| Fewer than ten available | 37 |
| No examples available | 0 |
| **Total keys** | **75** |

There are **496 retained examples** covering the 102,154 formerly unmapped assertions. Each example contains the original source assertion identity, endpoints, predicate, source reference, canonical orientation, explicit reverse orientation, and review note. The availability counts are in [`ADDITIONAL_RELATION_VALIDATION_2026-10-15.csv`](ADDITIONAL_RELATION_VALIDATION_2026-10-15.csv); the examples are in [`ADDITIONAL_RELATION_EXAMPLES_2026-10-15.csv`](ADDITIONAL_RELATION_EXAMPLES_2026-10-15.csv).

All 496 displayed examples were inspected for relation role, direction, and obvious scope conflicts. **407 of the 496 object names are only QIDs in the draft.** This limits semantic assessment. A focused official lookup supplies additional context for 13 endpoint IDs; it does not repair or relabel the draft graph. A broader metadata request was stopped after HTTP 429, and no complete endpoint refresh is claimed.

A structural endpoint-swap pass is not an assertion-truth pass. Missing explicit inverse assertions are not contradictions: inverse facts can be absent from an incomplete source export. Source agreement can also reflect reuse of Wikidata rather than independent evidence.

## 6. Data quality findings that remain open

### Confirmed source usage problems

- **`P2353`: Vivian Street → Rifle Brigade / Devonshire Regiment.** The property means statistical unit of the dataset, while the subject is a British Army general. Both current source statement IDs and property codes match the exported records. This is an upstream value/usage problem, not a translation invented by GG. Do not change it into a military-service relation without separate evidence.
- **`P5961`: Convoy PQ 18 → Allies of World War II.** The property description says to use it as a qualifier for `depicts` or `image`. It appears as a main statement in both the draft input and the current Wikidata entity. The matching EventKG assertion repeats the same usage; it does not resolve the scope problem.

The focused current statement evidence is saved in [`ADDITIONAL_RELATION_FOCUSED_STATEMENTS_2026-10-15.json`](ADDITIONAL_RELATION_FOCUSED_STATEMENTS_2026-10-15.json). A current source check does not prove that the source has been unchanged at every earlier date.

### Possible source or endpoint problems

- EventKG `P1343` links Carl Friedrich Goerdeler to **World War II**, an event instead of a document/source-work target. The current Wikidata subject has a different `P1343` target. This is a source-version or extraction-context issue to trace, not evidence that `P1343` should be mapped to participation.
- EventKG `P279` links **Art Looting Investigation Unit** to **Office of Strategic Services**. The visible roles suggest organizational part-of rather than subclass. Keep the predicate and flag the assertion; the mapping must not silently correct the claim.
- Some `P460` examples connect a military rank with an equivalent rank, or a historical concept with a related one. Uncertain or scoped identity evidence is insufficient for entity merging.
- Some historical-looking names refer to films, photographs, documents, museum ships, or categories. Examples include **Masters of the Air**, **The World at War**, **U.S. Army Field Manual 30-31B**, and **outline of World War II**. The draft often assigns event, organization or location types to these incorrectly.
- Media participant `P11108`, depiction `P180`, category metadata, and project-focus `P5008` do not prove who fought, attacked, commanded, or occupied a place.
- KML links, map categories and route-diagram templates are references to resources. Mapping these predicates does not supply usable geometry. Geometry remains outside this check.
- `P9660` means **not found in**. Preserve that negative meaning when assembling evidence.

Per-key notes record both the visible agreement and these limits. Native codes remain exact even where their source assertion values look wrong. None of these flags is a new broad Level 1 classification.

## 7. Rebuild and verification

Run from the repository root:

```powershell
& 'Agent/.venv/Scripts/python.exe' 'GG_Data/mapping/rebuild_relation_mapping.py'
& 'Agent/.venv/Scripts/python.exe' 'GG_Data/mapping/test_relation_mapping_keys.py'
& 'Agent/.venv/Scripts/python.exe' 'GG_Data/mapping/validate_additional_relation_rules.py'
& 'Agent/.venv/Scripts/python.exe' 'GG_Data/mapping/run_relation_mapping_sanity.py'
```

The canonical entry point reads the saved original audit plus the fixed 75-rule ledger. It invokes the **local** reverse builder at `GG_Data/mapping/build_relation_mapping_v2_1.py`; the historical `poc` builders must not regenerate the expanded tables.

The build checks identifier preservation, duplicate keys, formal statement values for the two non-identity translations, original source metadata, and reverse lookup completeness. Six regression checks cover original keys, additional keys, WarSampo full identifiers, blocked named inverses and symmetry, reverse involution, and legacy endpoint restoration.

The legacy v1 notebook writes endpoints after applying its direction rule. The audit now undoes that old normalization before applying v2.1. Otherwise, an already-reversed assertion could be swapped a second time and shown in the wrong direction. The added-key source facts are preserved from the original orientation; the correction also applies to counterpart checks.

The evidence snapshot contains 69 requested Wikidata properties plus eight inverse-target properties, including English labels/descriptions and selected formal claims with statement IDs, rank and qualifiers. The build reuses this saved snapshot without live network calls. External property values are not promoted to graph truths merely because a formal declaration exists.

## 8. Remaining integration gate

The mapping catalog is complete for the current draft input. The existing large assertion file, draft graph and v1 export notebook still describe the v1 build. A v2.1-aware export/data-layer integration and Agent evaluation are separate steps. Full Agent answers require exact relation evidence, reliable endpoint identity, time/qualifier context, and the private Gold Set traces; mapping coverage alone does not establish answer correctness.

## Appendix: all 75 delivered source keys

`WD` means native Wikidata; `EK` means EventKG. The rule ledger retains each full source URI. Counts below are **current draft assertions**, not total source-inventory occurrences.

| Source | Source predicate | Label | Draft assertions | Distinct facts | Sample | Effective Level 2 | Reverse type |
|---|---|---|---:|---:|---:|---|---|
| EK | `wdt:P1889` | different from | 105 | 105 | 10 | `wd:P1889` | SYMMETRIC |
| EK | `owl:differentFrom` | differentFrom | 101 | 101 | 10 | `wd:P1889` | SYMMETRIC |
| EK | `wdt:P31` | instance of | 54 | 53 | 10 | `wd:P31` | SYNTHETIC_INVERSE |
| EK | `wdt:P460` | said to be the same as | 7 | 7 | 7 | `wd:P460` | SYMMETRIC |
| EK | `wdt:P279` | subclass of | 5 | 5 | 5 | `wd:P279` | SYNTHETIC_INVERSE |
| EK | `wdt:P1343` | described by source | 3 | 3 | 3 | `wd:P1343` | SYNTHETIC_INVERSE |
| WD | `wd:P31` | instance of | 56,106 | 56,090 | 10 | `wd:P31` | SYNTHETIC_INVERSE |
| WD | `wd:P21` | sex or gender | 17,476 | 17,475 | 10 | `wd:P21` | SYNTHETIC_INVERSE |
| WD | `wd:P1343` | described by source | 9,623 | 9,500 | 10 | `wd:P1343` | SYNTHETIC_INVERSE |
| WD | `wd:P1889` | different from | 6,696 | 6,696 | 10 | `wd:P1889` | SYMMETRIC |
| WD | `wd:P279` | subclass of | 5,312 | 5,311 | 10 | `wd:P279` | SYNTHETIC_INVERSE |
| WD | `wd:P910` | topic's main category | 3,033 | 3,033 | 10 | `wd:P910` | NAMED_INVERSE |
| WD | `wd:P5008` | on focus list of Wikimedia project | 1,261 | 1,261 | 10 | `wd:P5008` | SYNTHETIC_INVERSE |
| WD | `wd:P516` | powered by | 486 | 486 | 10 | `wd:P516` | SYNTHETIC_INVERSE |
| WD | `wd:P437` | distribution format | 203 | 203 | 10 | `wd:P437` | SYNTHETIC_INVERSE |
| WD | `wd:P180` | depicts | 199 | 199 | 10 | `wd:P180` | NAMED_INVERSE |
| WD | `wd:P8030` | military size designation | 198 | 198 | 10 | `wd:P8030` | SYNTHETIC_INVERSE |
| WD | `wd:P460` | said to be the same as | 158 | 158 | 10 | `wd:P460` | SYMMETRIC |
| WD | `wd:P3729` | next lower rank | 119 | 118 | 10 | `wd:P3729` | NAMED_INVERSE |
| WD | `wd:P3730` | next higher rank | 115 | 115 | 10 | `wd:P3729` (swap) | NAMED_INVERSE |
| WD | `wd:P2517` | category for recipients of this award | 114 | 114 | 10 | `wd:P2517` | SYNTHETIC_INVERSE |
| WD | `wd:P2684` | Kijkwijzer rating | 85 | 83 | 10 | `wd:P2684` | SYNTHETIC_INVERSE |
| WD | `wd:P1754` | category related to list | 76 | 76 | 10 | `wd:P1754` | NAMED_INVERSE |
| WD | `wd:P2354` | has list | 75 | 75 | 10 | `wd:P2354` | NAMED_INVERSE |
| WD | `wd:P7084` | related category | 74 | 74 | 10 | `wd:P7084` | SYNTHETIC_INVERSE |
| WD | `wd:P7867` | category for maps or plans | 48 | 48 | 10 | `wd:P7867` | SYNTHETIC_INVERSE |
| WD | `wd:P1431` | executive producer | 39 | 39 | 10 | `wd:P1431` | SYNTHETIC_INVERSE |
| WD | `wd:P7561` | category for the interior of the item | 37 | 37 | 10 | `wd:P7561` | SYNTHETIC_INVERSE |
| WD | `wd:P2061` | aspect ratio (W:H) | 33 | 33 | 10 | `wd:P2061` | SYNTHETIC_INVERSE |
| WD | `wd:P1792` | category of associated people | 30 | 30 | 10 | `wd:P1792` | SYNTHETIC_INVERSE |
| WD | `wd:P10527` | documentation files at | 27 | 26 | 10 | `wd:P10527` | SYNTHETIC_INVERSE |
| WD | `wd:P1791` | category for people buried here | 21 | 21 | 10 | `wd:P1791` | SYNTHETIC_INVERSE |
| WD | `wd:P2637` | RARS rating | 20 | 20 | 10 | `wd:P2637` | SYNTHETIC_INVERSE |
| WD | `wd:P2959` | permanent duplicated item | 19 | 19 | 10 | `wd:P2959` | SYMMETRIC |
| WD | `wd:P1433` | published in | 18 | 18 | 10 | `wd:P1433` | SYNTHETIC_INVERSE |
| WD | `wd:P2629` | BBFC rating | 17 | 17 | 10 | `wd:P2629` | SYNTHETIC_INVERSE |
| WD | `wd:P1151` | topic's main Wikimedia portal | 15 | 15 | 10 | `wd:P1151` | NAMED_INVERSE |
| WD | `wd:P5869` | model item | 13 | 13 | 10 | `wd:P5869` | SYNTHETIC_INVERSE |
| WD | `wd:P11108` | recorded participant | 11 | 11 | 10 | `wd:P11108` | SYNTHETIC_INVERSE |
| WD | `wd:P91` | sexual orientation | 11 | 11 | 10 | `wd:P91` | SYNTHETIC_INVERSE |
| WD | `wd:P1611` | NATO code for grade | 10 | 10 | 10 | `wd:P1611` | SYNTHETIC_INVERSE |
| WD | `wd:P2813` | house publication | 8 | 8 | 8 | `wd:P2813` | NAMED_INVERSE |
| WD | `wd:P4195` | category for employees of the organization | 8 | 8 | 8 | `wd:P4195` | SYNTHETIC_INVERSE |
| WD | `wd:P618` | source of energy | 8 | 8 | 8 | `wd:P618` | SYNTHETIC_INVERSE |
| WD | `wd:P8625` | bibliography | 8 | 8 | 8 | `wd:P8625` | SYNTHETIC_INVERSE |
| WD | `wd:P3912` | newspaper format | 7 | 7 | 7 | `wd:P3912` | SYNTHETIC_INVERSE |
| WD | `wd:P4437` | FPB rating | 7 | 7 | 7 | `wd:P4437` | SYNTHETIC_INVERSE |
| WD | `wd:P8875` | indexed in bibliographic review | 6 | 6 | 6 | `wd:P8875` | SYNTHETIC_INVERSE |
| WD | `wd:P275` | copyright license | 4 | 4 | 4 | `wd:P275` | SYNTHETIC_INVERSE |
| WD | `wd:P3858` | route diagram template | 4 | 4 | 4 | `wd:P3858` | SYNTHETIC_INVERSE |
| WD | `wd:P10642` | place of disappearance | 3 | 3 | 3 | `wd:P10642` | SYNTHETIC_INVERSE |
| WD | `wd:P1534` | end cause | 3 | 3 | 3 | `wd:P1534` | SYNTHETIC_INVERSE |
| WD | `wd:P3301` | broadcast by | 3 | 3 | 3 | `wd:P3301` | SYNTHETIC_INVERSE |
| WD | `wd:P972` | catalog | 3 | 3 | 3 | `wd:P972` | SYNTHETIC_INVERSE |
| WD | `wd:P2353` | statistical unit of the dataset | 2 | 2 | 2 | `wd:P2353` | SYNTHETIC_INVERSE |
| WD | `wd:P2378` | issued by | 2 | 2 | 2 | `wd:P2378` | SYNTHETIC_INVERSE |
| WD | `wd:P248` | stated in | 2 | 2 | 2 | `wd:P248` | SYNTHETIC_INVERSE |
| WD | `wd:P3150` | birthday | 2 | 2 | 2 | `wd:P3150` | SYNTHETIC_INVERSE |
| WD | `wd:P5125` | Wikimedia outline | 2 | 2 | 2 | `wd:P5125` | SYNTHETIC_INVERSE |
| WD | `wd:P6186` | category for eponymous categories | 2 | 2 | 2 | `wd:P6186` | SYNTHETIC_INVERSE |
| WD | `wd:P7327` | OFLC classification | 2 | 2 | 2 | `wd:P7327` | SYNTHETIC_INVERSE |
| WD | `wd:P8058` | symbol of | 2 | 2 | 2 | `wd:P8058` | SYNTHETIC_INVERSE |
| WD | `wd:P12693` | source of transfer | 1 | 1 | 1 | `wd:P12693` | SYNTHETIC_INVERSE |
| WD | `wd:P1881` | list of characters | 1 | 1 | 1 | `wd:P1881` | SYNTHETIC_INVERSE |
| WD | `wd:P3096` | KML file | 1 | 1 | 1 | `wd:P3096` | SYNTHETIC_INVERSE |
| WD | `wd:P4082` | captured with | 1 | 1 | 1 | `wd:P4082` | SYNTHETIC_INVERSE |
| WD | `wd:P5278` | surname for other gender | 1 | 1 | 1 | `wd:P5278` | SYMMETRIC |
| WD | `wd:P553` | website account on | 1 | 1 | 1 | `wd:P553` | SYNTHETIC_INVERSE |
| WD | `wd:P5961` | depicted part | 1 | 1 | 1 | `wd:P5961` | SYNTHETIC_INVERSE |
| WD | `wd:P6803` | taxon found at location | 1 | 1 | 1 | `wd:P6803` | SYNTHETIC_INVERSE |
| WD | `wd:P78` | top-level Internet domain | 1 | 1 | 1 | `wd:P78` | SYNTHETIC_INVERSE |
| WD | `wd:P8464` | content partnership category | 1 | 1 | 1 | `wd:P8464` | SYNTHETIC_INVERSE |
| WD | `wd:P885` | origin of the watercourse | 1 | 1 | 1 | `wd:P885` | NAMED_INVERSE |
| WD | `wd:P9660` | not found in | 1 | 1 | 1 | `wd:P9660` | SYNTHETIC_INVERSE |
| WD | `wd:P9969` | catalogue raisonné | 1 | 1 | 1 | `wd:P9969` | SYNTHETIC_INVERSE |
