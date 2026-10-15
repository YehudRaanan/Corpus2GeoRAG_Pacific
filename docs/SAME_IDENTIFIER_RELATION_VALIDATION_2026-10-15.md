# Validation of the 403 Same-Identifier Relation Pairs

**Date:** 2026-10-15

**Scope:** The 403 connections previously reported as identity matches in the deterministic Level 2 relation audit

**Source pair:** EventKG and Wikidata

## Conclusion

All 403 connections are valid identifier identities. Each connection compares an EventKG relation such as `wd:P85` with the Wikidata relation `wd:P85`. The normalized property ID is equal on both sides. No cross-identifier translation is performed.

This result does not show that all relation labels or all assertions are good. The separate validation found:

- 381 exact English label matches;
- 9 wording differences with no detected contradiction;
- 13 EventKG labels that omit or change part of the current Wikidata scope;
- no EventKG description for any of the 403 connections, so a two-sided description comparison is not possible;
- 3,228 sampled assertions across the 403 connections;
- 274 connections with ten examples;
- 129 connections with fewer than ten examples;
- 24 relations with at least one clear contradiction in the sampled assertions;
- 379 relations with no clear contradiction found in the available sample.

The 24 sample failures are assertion-quality problems. They do not change the identity result. For example, a bad assertion under `wd:P118` does not make EventKG `wd:P118` a different property from Wikidata `wd:P118`.

## 1. Formal mapping result

### Question

Is a formal cross-source mapping available for each of the 403 pairs?

### Result

No separate mapping statement is required or used. Both source rows already use the same global Wikidata property identifier.

Example:

| EventKG relation | Wikidata relation | Deterministic result |
|---|---|---|
| `wd:P85` | `wd:P85` | Same identifier; keep `wd:P85` |
| `wd:P607` | `wd:P607` | Same identifier; keep `wd:P607` |
| `wd:P118` | `wd:P118` | Same identifier; keep `wd:P118` |

The normalizer only converts equivalent identifier syntax to one form. It does not infer meaning from a name or description.

Five of the 403 Wikidata properties have a formal symmetric-property declaration: `P26`, `P47`, `P1038`, `P3373`, and `P451`. Symmetry affects reverse query traversal. It is not evidence that maps EventKG to Wikidata.

Fourteen properties are also members of unsafe formal mapping components found in the earlier audit. Their direct same-identifier result remains valid. The unsafe result applies only when a system tries to merge those properties transitively with other identifiers. The 14 are:

`P53`, `P170`, `P176`, `P195`, `P463`, `P710`, `P725`, `P800`, `P1056`, `P1269`, `P1344`, `P1923`, `P2184`, and `P3342`.

## 2. Label and description comparison

### Description availability

Wikidata has an English description for every reviewed property. EventKG has no relation description for any of these 403 inventory rows. Therefore, a true description-to-description comparison cannot be done.

The audit instead compared:

1. the EventKG English label;
2. the Wikidata English label;
3. the Wikidata English property description.

These text fields validate the data. They do not decide identity.

### Label results

| Result | Pairs |
|---|---:|
| Exact label match | 381 |
| Wording variant; no contradiction found | 9 |
| EventKG label omits or changes Wikidata scope | 13 |
| **Total** | **403** |

The 22 non-exact label matches are:

| Property | EventKG label | Current Wikidata label | Review |
|---|---|---|---|
| `P607` | conflict | participated in conflict | EventKG label omits relation direction and scope |
| `P1029` | crew member(s) | crew members | Wording variant |
| `P112` | founded by | founder | Wording variant |
| `P504` | home port | shipping port | Source label drift |
| `P118` | league | league or competition | EventKG label omits competition scope |
| `P1552` | has quality | has characteristic | Wording variant |
| `P1308` | officeholder | position holder | Wording variant |
| `P1313` | office held by head of government | office held by the head of government | Wording variant |
| `P1876` | vehicle | vessel | Source label drift |
| `P2388` | office held by head of the organization | position held by head of the organization | Wording variant |
| `P2505` | carries | carries thoroughfare | EventKG label omits object scope |
| `P2522` | victory | competition won | EventKG label is broader |
| `P355` | has subsidiary | child organization or unit | EventKG label omits unit scope |
| `P749` | parent organization | parent organization or unit | EventKG label omits unit scope |
| `P3975` | secretary general | general secretary | Source label drift |
| `P410` | military rank | military, police or special rank | EventKG label omits scope |
| `P5012` | special rank | special rank or class rate | EventKG label omits scope |
| `P629` | edition or translation of | version, edition or translation of | EventKG label omits version scope |
| `P747` | has edition or translation | has version, edition or translation | EventKG label omits version scope |
| `P676` | lyrics by | lyricist | Wording variant |
| `P7137` | acknowledged | acknowledges | Wording variant |
| `P8032` | victim | victim(s) | Wording variant |

These differences show why the property ID must remain authoritative. A cached or shortened label can change while the Wikidata property ID remains stable.

## 3. Ten-example validation

### Method

The validation reused the stable samples from the deterministic mapping audit. For each connection, it selected up to ten distinct assertions by SHA-256 order. It then resolved every sampled Wikidata QID to its current English label and description through the Wikidata Query Service.

The final sample contains:

- 3,228 assertions;
- 2,995 assertions stored with `Wikidata` as the selected source;
- 233 assertions stored with `EventKG` as the selected source;
- 4,710 unique endpoint QIDs;
- an English label for every sampled endpoint QID.

Example coverage is:

| Examples available for a relation | Relations |
|---:|---:|
| 10 | 274 |
| 9 | 6 |
| 8 | 6 |
| 7 | 8 |
| 6 | 14 |
| 5 | 15 |
| 4 | 11 |
| 3 | 17 |
| 2 | 24 |
| 1 | 28 |
| **Total** | **403** |

No relation has zero examples. The 129 relations below ten were reviewed with all available examples. The audit does not invent examples to reach ten.

For 132 relations, at least one sampled subject-object pair appears in both source datasets. There are 425 such duplicate facts in the sample. This overlap is supporting observation only. Missing overlap is not a contradiction because EventKG and Wikidata do not have identical coverage.

### Clear contradictions in sampled assertions

The review found at least one clear semantic contradiction for 24 relations:

| Property | Wikidata meaning | Contradictory sampled use |
|---|---|---|
| `P114` | airline alliance | The event “Shelling of the Mees” points to KLM |
| `P118` | league or competition | Military officers point to the Waffen-SS, Schutzstaffel, or German Army |
| `P135` | artistic, scientific, or philosophical movement | Political ideologies are used although the description directs them to `P1142` |
| `P1327` | partner in business or sport | Hitler-Stalin and Stalin-Churchill political relationships are used |
| `P1536` | immediate cause of | Operation Harvest Festival points to the earlier state Nazi Germany as its effect |
| `P828` | has cause | Adolf Heusinger points to Germany as his cause |
| `P1591` | defendant | The Holocaust is treated as a trial with Adolf Hitler as defendant |
| `P169` | chief executive officer | Einsatzgruppen leaders are stored as corporate CEOs |
| `P1789` | chief operating officer | Subhas Chandra Bose is stored as COO of the Indian National Army |
| `P208` | executive body | A person is stored as the government executive body of a memorial institution |
| `P1346` | winner | Hero City awardees are stored as winners although the description excludes awardees |
| `P2568` | repealed by | Hitler's rise to power is treated as a document repealed by Nazi Germany |
| `P2650` | interested in | Military units point to military classes as vested interests |
| `P2789` | physically connects with | A regiment points to a riot event |
| `P2868` | subject has role | A ship points to an event and a division points to an activity as their roles |
| `P425` | field of an occupation | Organizations such as the British Army are used as occupations |
| `P3712` | has goal | “code name” points to values such as motivation and determination |
| `P767` | contributor to a creative work | Gabriel El-Registan points to the anthem, reversing the documented direction |
| `P4330` | physically contains | Class and list links are stored as container contents |
| `P520` | armament | Military parade events are treated as armed platforms |
| `P608` | exhibition history | The values are museums or display locations instead of exhibitions |
| `P6275` | copyright representative | Copyright-status categories are used instead of people or organizations |
| `P7047` | enemy of a fictive character or group | Real wartime organizations are linked as enemies |
| `P8324` | funder | Adolf Hitler is stored as funder of the Close Combat Clasp |

This table means that at least one sampled assertion is inconsistent with the saved property description. It does not mean that every assertion under the relation is wrong.

For the other 379 relations, no clear contradiction was found in the available sample. This is a limited negative result. Ten examples cannot prove that the complete relation data is correct.

## 4. Decision for Level 2 mapping

The deterministic decision for all 403 pairs is:

1. keep the shared Wikidata property ID;
2. do not create a translation row between two different identifiers;
3. preserve the source dataset and source predicate on every assertion;
4. flag the 13 label-scope differences as metadata drift;
5. route assertions under the 24 failed relations to assertion-quality review;
6. keep the 14 unsafe formal components blocked from transitive multi-property merging.

The label and example findings must not split `wd:Pxx` into two relations. If a source assertion uses the correct property ID with a bad value, correct or quarantine that assertion while retaining the property identity.

## 5. Limits

- EventKG has no relation descriptions for these rows. The audit cannot compare two independent descriptions.
- The graph export has no source sentence for these sampled assertions. The audit cannot inspect the original sentence or extraction context.
- A sampled assertion can be copied between sources. Cross-source duplication does not prove that it is true.
- The Wikidata labels and descriptions are a live snapshot from 2026-10-15. They can change while property IDs remain stable.
- The review reports clear contradictions. It does not classify every uncertain or overly broad assertion as an error.

## 6. Evidence files

All machine-readable evidence is in `poc/relation_alignment/deterministic_level2_mapping/`.

| File | Purpose |
|---|---|
| `same_identifier_pair_validation.csv` | One row for each of the 403 identities, including formal status, text comparison, coverage, and conclusion |
| `same_identifier_example_validation.csv` | All 3,228 resolved examples with endpoint labels and descriptions |
| `same_identifier_entity_metadata.json` | Saved Wikidata labels and descriptions for 4,710 endpoint QIDs |
| `same_identifier_validation_summary.json` | Counts, source snapshot, method, and limits |

The reproducible validator is `poc/relation_alignment/validate_same_identifier_connections.py`.
