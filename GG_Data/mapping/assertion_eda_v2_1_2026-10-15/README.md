# Assertions per relation code: exploratory data analysis

**Date:** 2026-10-15

**Scope:** The current WWII draft assertion export, replayed through the completed `relation-map-v2.1.0` catalog. These are exported entity-to-entity assertions with QID endpoints. Literal-valued source statements and records excluded upstream are not part of this population. This is not an EDA of all raw source datasets or a Pacific corpus release.

## Main results

The EDA scanned **700,890 assertion rows**, joined their endpoints to **146,318 draft nodes**, and applied the current source mappings without adding reverse assertion views. All rows found a mapping. The common-code and source-code totals reconcile exactly.

| Measure | Result | Interpretation |
|---|---:|---|
| Catalog Level 2 codes | 1,064 | All retained in the main profile |
| Level 2 codes with current assertions | 755 | Actual relation population in this export |
| Catalog Level 2 codes with zero current assertions | 309 | No exported examples; not missing mapping rules |
| Source/predicate keys with current assertions | 1,029 of 1,595 | 566 catalog keys have no rows in this export |
| Observed codes with 1–9 assertion rows | 337 | Often too small for a ten-example review |
| Observed codes with 10–99 assertion rows | 222 | Low-volume group |
| Median assertion rows per observed code | 13 | The long tail is large |
| Share held by the ten largest codes | 48.684% | A global random sample would be heavily skewed |
| Distinct full input rows | 700,890 | Zero identical full-row duplicates |
| Distinct observation IDs | 700,890 | Zero reused observation IDs |
| Reused selected source-record keys | 0 | No repeated nonempty `(source, record ID)` keys |
| Rows touching at least one QID-only endpoint name | 464,023 (66.20%) | Name/metadata limitation |
| Rows touching at least one draft `other`/unresolved type | 566,581 (80.84%) | Role checks often lack a reliable type |
| Rows touching at least one endpoint with empty node text | 466,008 (66.49%) | Node text is often unavailable; existing text is not automatically assertion evidence |
| Rows with no selected date | 618,963 (88.31%) | Review per relation and question; many relations do not require dates |
| Rows with any selected date | 81,927 (11.69%) | Relation dates, subject/event dates, and precision must remain distinct |
| Rows with impossible Gregorian calendar values | 6 | Concrete value defects in this exported representation |
| Definitely reversed intervals after precision handling | 127 | Needs original-statement review; no automatic correction |
| Self-loops | 45 | Mixed cases; relation-specific review required |

### 1. Source coverage is strongly uneven

| Selected source | Assertion rows | Observed source keys | Catalog source keys |
|---|---:|---:|---:|
| Wikidata | 572,283 | 670 | 670 |
| EventKG | 128,517 | 357 | 814 |
| WarSampo | 90 | 2 | 111 |
| **Total** | **700,890** | **1,029** | **1,595** |

The catalog is broader than the current assertion population. The low WarSampo count is a coverage finding about this export, not proof that WarSampo has only two useful predicates. The EDA cannot identify every upstream exclusion cause from the final CSV alone.

Of EventKG's 128,517 rows, **69,383** name its Wikidata source graph, **50,895** DBpedia English, and **4,048** YAGO. Another **3,710** explicitly use `source_unknown`; a nonempty graph field is therefore not equivalent to known lineage. **481** name the EventKG graph. These graph counts are in `source_graph_profile.csv`.

This is why “seen in Wikidata and EventKG” cannot be counted as two independent sources without checking lineage.

### 2. Repetition is real; identical-row duplication is absent

| Repetition measure | Result |
|---|---:|
| Distinct `(Level 2, subject, object)` pairs | 623,017 |
| Pairs represented by multiple assertion rows | 64,109 |
| Extra rows beyond one row per endpoint pair | 77,873 |
| Extra rows beyond one row per endpoint-plus-time key | 61,034 |
| Repeated endpoint pairs with different time values | 8,970 |
| Endpoint pairs present in multiple selected sources | 60,394 |

The 77,873 rows are **not a safe deletion list**. All full rows, observation IDs and selected source-record keys are distinct. Some repeated pairs have different periods; others can have different source records, source graphs or qualifiers that the CSV does not fully expose.

For example, `P607` has 57,938 rows but 38,004 endpoint pairs. `P166` has 64,026 rows but 52,969 endpoint pairs. `P361` has 16,916 rows but 9,008 endpoint pairs, and 1,998 of its repeated pairs have different time values.

These are v2.1-normalized keys. They must not be compared directly with an older v1 graph's 74,111 repeated-assertion count as though new duplicate input rows had been added.

### 3. Both sides of some named inverses are already stated

After aligning endpoints by the accepted reverse contract, **2,270 endpoint pairs** have rows under both effective named inverse IDs:

| Inverse pair | Endpoint pairs seen under both IDs |
|---|---:|
| SEM `hasSubEvent` / `subEventOf` | 1,821 |
| Wikidata `P1056` product or material produced / `P176` manufacturer | 443 |
| Wikidata `P2354` has list / `P360` is a list of | 6 |
| **Total** | **2,270** |

For SEM, 3,642 assertions represent 1,821 direction-normalized pairs, and every pair has both named relation IDs. This is useful evidence of explicit two-sided data. It still does not justify doubling support when the data layer also generates reverse views. The EDA does not check temporal compatibility or hidden qualifiers for these pair overlaps.

### 4. The largest codes describe very different data

| Common Level 2 | Meaning | Assertion rows | Distinct endpoint pairs | Rows touching a QID-only name |
|---|---|---:|---:|---:|
| `wd:P166` | award received | 64,026 | 52,969 | 45,669 |
| `wd:P607` | conflict | 57,938 | 38,004 | 9,780 |
| `wd:P31` | instance of | 56,160 | 56,092 | 48,554 |
| `wd:P793` | significant event | 30,455 | 29,985 | 30,086 |
| `wd:P106` | occupation | 29,078 | 28,939 | 28,523 |
| `wd:P241` | military branch | 22,529 | 14,520 | 6,111 |
| DBpedia `battle` | battle | 21,714 | 21,714 | 393 |
| `wd:P27` | country of citizenship | 20,823 | 18,778 | 16,349 |
| `wd:P121` | item operated | 19,618 | 14,379 | 3,842 |
| `wd:P17` | country | 18,882 | 17,474 | 12,857 |

Volume is not answer value. Awards, types, occupations and citizenship are legitimate graph content, but they do not all answer where a battle happened or who attacked.

`P607` is also concentrated: **64.678%** of its rows target the World War II node. Such a hub can dominate retrieval. Concentration is not itself wrong: low-cardinality attributes, such as `P21`, naturally have common values. Inspect the exact relation and question before treating a hub as a defect.

### 5. Location-related assertions mostly lack readable endpoint names

| Exact relation | Rows | Rows touching a QID-only name |
|---|---:|---:|
| `P276` location | 3,996 | 3,744 |
| `P131` administrative area | 3,968 | 3,899 |
| `P706` physical feature | 96 | 93 |

This is a metadata and discovery limit even when the exact relation is valid. Administrative or physical containment also remains distinct from a precise event-occurrence assertion. Missing geometry has not been counted here.

The 464,023 QID-name count uses the primary-name pattern. The earlier graph audit's 462,289 count used the narrower `metadata_status=QID_FALLBACK` condition; they are different measures.

### 6. Time problems include bad values and incomplete selection context

The EDA finds **1,687 rows** with precision metadata for at least one date field but no single date selected in that field. **165 rows** contain mixed precision values. These groups overlap and must not be added together. They are separate from rows that have no date evidence at all.

Concrete exported calendar defects include:

- Ferdinand Schörner — award received: `1934-02-31`.
- Winston Churchill — position held: `1904-04-31`, on two adjacent interval records.
- Karl Allmendinger — military rank: `1936-06-31`.
- Francesco Crispi — significant event: `1927-02-29`.
- U-48 — significant event: `1936-11-31`.

Source statement IDs are retained in `examples.csv`. These impossible month/day combinations are visible in the exported Wikidata-selected values; the original source statement and extraction path must be checked before attribution or repair.

Of the **127 definitely reversed intervals**, **78** belong to `P361`. One example is U-960 → part of → 3rd U-boat Flotilla with start `1944-08-01` and end `1944-05-19`. Do not silently swap the dates. The old stored `time_status=CONFLICT` occurs on 128 rows; its parser and the current precision-aware test are different checks.

The **38,749 rows** with a present year outside 1939–1945 are context flags. Births, service histories, later awards and publications can be valid outside the war period. Coarser-than-year precision is not converted into precise interval bounds.

### 7. Value and endpoint-role problems cannot be fixed by merging relation codes

The self-loop sample includes:

- Omar Bradley → DBpedia honours → Omar Bradley.
- Bill Stone → DBpedia militaryUnit → Bill Stone.
- Alastair Mars → occupation → Alastair Mars.
- Some unit → replaces (`P1365`) → the same unit.

These are strong candidates for source/extraction/identity review. A reflexive `seeAlso` link has a different meaning and must not be rejected by the same rule. The current EDA preserves all 45 self-loops and their source records.

**Subsequent source review:** 14 assertions are approved for exclusion from future outputs: the three EventKG person-target examples above, three Wikidata errors (own parent unit, own child, own manufacturer), and eight unqualified succession self-links. All 29 EventKG self-links already have identical raw endpoint resources; all 16 Wikidata self-links were found in their exact saved statements. Country self-reference can be valid under P17, so the review does not apply a blanket self-loop rejection. The approved gate retains 700,876 rows and 31 self-links. It also preserves the separate 77th Division successor assertion to a distinct QID. Historical phase relationships have not been reconstructed. See the [source review and approved output gate](../self_link_review_2026-10-15/README.md). This EDA remains the unfiltered 700,890-row baseline.

The previous 75-code review also identified `P2353` statistical-unit usage on Vivian Street's military-unit targets, and `P5961` (depicts in context) used as a main relation on Convoy PQ 18 → Allies instead of its documented qualifier context. The EDA confirms their counts (three `P2353` rows and two `P5961` rows), but does not replace that semantic review. See the [75-code completion report](../RELATION_MAPPING_75_CODE_COMPLETION_2026-10-15.md).

### 8. Evidence and mapping status remain separate from assertion truth

Every row has a nonempty selected record ID, graph string, source-reference field, support array and evidence array. No row contains multiple support entries. This is traceability coverage, not proof of an answer-supporting passage. In particular, 3,710 graph strings are explicitly unknown, and only **263,101 of 572,283 Wikidata-selected rows** contain nonempty source reference-hash lists in the exported pointer.

The mapping marks **105,480 rows** for assertion QA. That flag is a catalog policy; it does not mean all those assertions are wrong, nor that the unflagged assertions are proven true. The EDA also detects **142,891 legacy rows** where a ranked Level 1 candidate was written as an active family. Current Level 1 status is profiled separately and remains optional.

The current reverse contract covers every mapped relation. It uses named inverse, symmetric, or explicit synthetic reverse values. A synthetic reverse is an explicit directional representation; it is not a new historical assertion or an extra independent support record.

## Conclusions and suggested order of review

1. **Use the common-code profile as the main table, with the source-key profile beside it.** This exposes both relation meaning and source-specific failures. Keep all zero-count catalog rows visible.
2. **Inspect repeated pairs and named inverse overlaps before deciding support counts.** Preserve records and dates; group only with clear compatibility rules. Do not delete the 77,873 rows as duplicates.
3. **Review frequent relations with weak endpoint context.** `P793`, `P106`, `P31` and `P166` combine high volume with many QID-only names. Location predicates need the same review for query usefulness. Resolve names/types from identity evidence, rather than guessing from relation families.
4. **Trace concrete value defects first within the time and self-loop groups.** Preserve the original values and attach a review decision. Separately investigate EventKG subject-level date attachment and unselected multi-value dates.
5. **Investigate source-scope selection before judging WarSampo coverage.** Its 90 assertions do not represent the whole 111-key catalog.
6. **Then validate question fit with original evidence.** Review one exact relation at a time using its endpoint-role distribution, dates, source lineage and original statement qualifiers. The retained random examples are review inputs, not a completed semantic gold set.

## Dimensions and questions

| Dimension | What to measure per common Level 2 code | What it can reveal |
|---|---|---|
| Volume and coverage | Assertion rows, distinct endpoint pairs, share of all rows, source keys with no exported rows | Dominant relations, rare relations, unused catalog entries |
| Source and extraction lineage | Selected source, original predicate, source graph, distinct source record IDs | Source imbalance, copied data, extraction-specific patterns |
| Repetition | Full-row duplicates, repeated observation IDs, repeated source-record keys, repeated endpoint pairs, repeated endpoint-plus-time keys | Accidental row duplication versus repeated source observations or different periods |
| Endpoint diversity and concentration | Unique subjects/objects, largest subject/object and its row share, self-loops | Hub-dominated retrieval and relations with little entity diversity |
| Endpoint metadata | QID-only names, missing nodes, `other` and unresolved types, empty endpoint text | Failures in naming, identity context, typing, and answer support |
| Endpoint role combinations | Full subject-type × object-type distribution by code | Examples to inspect against the exact relation meaning; frequencies alone do not prove misuse |
| Time | No date, point date, interval boundaries, year distribution, calendar defects, definitely reversed intervals | Missing temporal context, malformed values, uncertainty, extraction problems |
| Evidence availability | Source record/graph/reference pointers, support/evidence arrays, Wikidata reference-hash availability | Whether an assertion can be traced, and which evidence still needs retrieval |
| Mapping and direction | Source-to-Level-2 rules, changed IDs, endpoint reversals, named/symmetric/synthetic reverse, optional Level 1 status | Mapping-sensitive groups and exact reverse delivery requirements |
| Scope and question fit | Core WWII endpoint membership, relation meaning, visible examples | Whether counts describe the intended scope and whether a relation can support a particular question |

These dimensions remain separate. There is no combined quality score or automatic rejection threshold. Geometry is deferred and is not counted as a defect.

## Files and counting units

| File | Unit and purpose |
|---|---|
| `relation_profile.csv` | One row for every effective catalog Level 2 ID, including IDs with zero current assertions; main EDA table |
| `source_relation_profile.csv` | One row for every original source/predicate lookup key, including keys with zero assertions |
| `endpoint_type_pairs.csv` | Observed assertion counts for every Level 2 / draft subject type / draft object type combination |
| `source_graph_profile.csv` | Assertion counts by Level 2, selected source and source graph |
| `year_profile.csv` | Present, calendar-valid date-field values by Level 2, date field and year; one assertion can contribute to several fields |
| `time_precision_profile.csv` | Source precision values by Level 2, source, date field, and whether a single date was selected |
| `status_profile.csv` | Assertion counts by Level 2 and legacy/current status dimensions; dimensions must not be added together |
| `direction_pair_profile.csv` | Assertion counts and unique endpoint pairs after aligning named inverse directions and symmetric endpoints |
| `examples.csv` | Up to three seeded random rows per observed Level 2, plus capped examples of structural/date/record issues; repeated appearances across sample reasons are intentional |
| `summary.json` | Dataset-wide totals, reconciliation results, source paths, sizes, and limitations |

### Definitions that prevent wrong conclusions

1. **Assertion** means one row in the existing exported assertion CSV. The EDA restores the source orientation from v1, then applies the v2.1 mapping exactly once. It does not add the Agent's reverse views to these counts.
2. A **source key** is `(selected_source, selected_source_predicate)`. The normalized Level 2 relation can be shared by multiple source keys. A zero count is not a missing mapping.
3. A **distinct endpoint pair** is `(Level 2, canonical subject, canonical object)`. Different dates, qualifiers, source records or works can still describe separate facts with these same endpoints.
4. An **endpoint-time key** also includes the original `time_from`, `time_to`, and `time_point` strings. Equal keys are repetition candidates, not proven duplicate assertions; other qualifiers and provenance are not included.
5. A **full-row duplicate** has identical values in every original CSV column. A repeated selected source-record key is weaker: the same record can have multiple contexts. IDs must not be used to delete evidence without review.
6. **Multiple selected sources** means the same mapped endpoint pair occurs in rows selected from more than one source. It is separate from multiple support entries within one row. EventKG can reuse Wikidata, so this does not prove independent corroboration.
   `repeated_selected_source_record_key` and `repeated_observation_id` flag a key already seen earlier in the complete input, rather than proving that two records are identical. Full-row duplication is checked separately.
7. **Both named relation IDs** means a direction-normalized pair has assertions under both effective inverse IDs. For a symmetric code, there is only one ID, so this metric does not claim two independently stated directions. The EDA does not strengthen named inverse mappings that the catalog has blocked.
8. **QID-only names** are a presentation/metadata gap, not proof that the entity identity itself is wrong. Draft `other` or unresolved classifications are diagnostics; they do not establish the true domain or range of a relation.
9. **Empty endpoint text** measures node text in the draft, not the absence of every possible external source passage. Existing text can also be insufficient to support the particular assertion.
10. A **source reference pointer** can be a statement ID, a reference hash list, or an extraction file/line. These are not equivalent to a retrieved, readable passage that supports an answer.

## Time interpretation

- Calendar checks accept signed and extended years. Month/day zero can indicate unknown components. Invalid Gregorian month/day combinations are reported; clock and timezone syntax are not separately validated. The CSV does not retain the Wikidata calendar model, so calendar flags need original-source review.
- Precision is used when checking interval order. A year-only value represents its year, a month-only value its month. An interval is called definitely reversed only when the start's earliest date is later than the end's latest date. Coarser-than-year precision is not forced into an invented interval.
- Numeric Wikidata precision and exact EventKG `unitDay`, `unitMonth`, `unitYear`, `unitDecade` values are handled separately. WarSampo `day`, `month`, and `year` values are supported too. A date with absent precision is not silently treated as day-accurate.
- Year zero and distant years are not rejected just because they look unusual. Values outside 1939–1945 are a context flag, because the graph includes lives, organizations, equipment and later works about WWII.
- Stored `time_status` values are reported separately from recomputed checks. The original status code and the EDA do not necessarily use the same uncertainty rules.
- Different time values on a repeated pair are recorded explicitly. Neither differing dates nor missing dates prove a contradiction without source and qualifier review.
- Nonempty precision metadata with no selected date, and mixed precision values, have separate counts. These are not necessarily parser failures: the exporter can leave a single date empty when several raw source values exist. Full competing values are not available in the final CSV.
- The v1 notebook's `direct_eventkg_records` attaches dates from its subject/event and source graph to direct predicates. Therefore an exported date is not automatically a date stated on that specific relation. Reified EventKG relation records and Wikidata qualifiers have different attachment logic. See the `direct_eventkg_records`, `reified_eventkg_records`, and `wikidata_time` functions in [the input builder](../RELATION_MAPPING_ALL_ITEMS_v1.0.0.ipynb). This EDA preserves the exported dates; it does not certify their attachment semantics.

## Evidence limits and next checks

The assertion CSV does not include all non-temporal qualifiers, full Wikidata reference statements, or grounded corpus passages. Thus this EDA measures coverage, consistency, repetition, lineage and metadata; it does not certify historical truth.

The draft metadata states `DRAFT_AGENT_MECHANISM_QA` and `pacific_corpus_used: false`. The endpoint types and names come from this same draft. No model, external metadata refresh, geocoding operation, source change or graph rebuild is part of this run.

For a relation selected for deeper review, inspect its source-key distribution, endpoint-type distribution, hub entities, dates, evidence pointers, and retained examples together. Then retrieve the original statement and its qualifiers. Compare an exact relation's role with the intended question. For example, participation alone does not establish who attacked.

## Reproduce and verify

From the repository root:

```powershell
& 'Agent/.venv/Scripts/python.exe' 'GG_Data/mapping/run_assertion_eda.py'
```

The script uses the standard library and existing local readers. It checks calendar/precision and repetition behavior before scanning. It fails on missing mapping keys or malformed structured input rather than silently omitting rows. It also reconciles the total assertion count across the common-code and source-code profiles.

The input files are read without modification. All outputs are inside this directory. The examples use seed `20261015`; issue examples retain the first three instances per relation/issue and are not population estimates.
