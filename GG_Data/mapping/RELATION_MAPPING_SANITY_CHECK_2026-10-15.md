# Relation mapping v2.1 sanity check

**Date:** 2026-10-15

**Mapping:** `relation-map-v2.1.0`

**Assertion input:** the 700,890 assertions used by `wwii-agent-draft-v0.1.0`

**Method:** deterministic replay plus a fixed, stratified random sample

**Seed:** `20261015`

## Conclusion

The exact Level 2 mappings in the reviewed sample are generally reasonable. The
formal reverse examples also preserve the intended direction. However, the data
layer is not ready to apply v2.1 to the whole draft export.

There are three separate blockers:

1. **Coverage:** v2.1 has a lookup row for 598,736 of 700,890 draft assertions
   (85.43%). It has no lookup row for 102,154 assertions (14.57%) across 75
   source-predicate keys.
2. **Ambiguous lookup keys:** ten WarSampo `source + source_predicate` keys occur
   more than once and produce different Level 2 IDs. A data layer that uses only
   those two fields cannot select one result deterministically.
3. **Question sufficiency:** several exact relations are valid but are too broad
   for the Agent question. A participant relation does not prove who attacked.
   Administrative containment does not always prove where an event occurred.

The direction contract itself passed: all 1,995 direction lookup rows returned
to the original relation after applying reverse twice.

## Gold or Silver question set

The published Agent document calls this a **56-question Gold Set**, not a Silver
Set. It states that `evals/gold.jsonl` is in the Agent developer's working
repository and is not included in the published package. Therefore, this check
cannot compare generated answers with the private expected answers.

This audit uses the published question categories and examples as query patterns:

- where an event happened;
- who attacked or participated;
- who commanded;
- all places connected to an entity;
- date-filtered and ambiguous-name questions;
- map and coordinate questions.

Sources:

- [Agent evaluation specification](https://github.com/EtzionR/Corpus2GeoRAG_Pacific/blob/1e1acd4384ad78cc741cb42812792cb5c65ec152/Agent/docs/EVALUATION.md)
- [Graph-team handoff](https://github.com/EtzionR/Corpus2GeoRAG_Pacific/blob/1e1acd4384ad78cc741cb42812792cb5c65ec152/Agent/docs/GRAPH_TEAM.md)

## Why the sample is stratified

A uniform random sample would be dominated by common relations, especially
`wd:P607`. It could miss reverse mappings, formal translations, blocked
translations, and low-frequency relations. The checker therefore samples five
assertions from each mapping-risk stratum and five assertions from each exact
relation used by a documented question pattern.

The risk strata are:

- identical identifier with a cross-source connection;
- formal translation in the same direction;
- formal translation in the reverse direction;
- source relation retained without a cross-source connection;
- mapping blocked or kept separate;
- assertion QA required;
- no v2.1 lookup row.

This produced 130 review rows. Sampling is reproducible with seed `20261015`.

## Deterministic checks

| Check | Result | Meaning |
|---|---:|---|
| Mapping rows | 1,520 | Rows in the v2.1 table |
| Duplicate `source + source_predicate` keys | 10 | These keys have 25 rows, or 15 rows beyond one row per key |
| Conflicting duplicate keys | 10 | Each duplicate key can lead to more than one Level 2 result |
| Direction lookup rows | 1,995 | Forward and reverse lookup rows |
| Direction contract errors | 0 | Each reverse points back to the original relation |
| Draft assertions replayed | 700,890 | Complete draft assertion input |
| Assertions with one v2.1 mapping | 598,736 (85.43%) | Deterministic replay was possible |
| Assertions with no v2.1 mapping | 102,154 (14.57%) | No v2.1 row exists |
| Assertions affected by ambiguous WarSampo keys in this draft | 0 | The draft subset has no such WarSampo assertion |

The ten conflicting keys matter even though this draft does not use them. They
include `warsa/unit`, `municipality_of_birth`, `municipality_of_death`,
`municipality_of_residence`, and `rank`. The table must use a stronger key, such
as the source graph and normalized predicate ID that distinguish the WarSampo
subschemas.

The missing v2.1 rows are concentrated in:

| Source predicate | Draft assertions |
|---|---:|
| `wd:P31` | 56,106 |
| `wd:P21` | 17,476 |
| `wd:P1343` | 9,623 |
| `wd:P1889` | 6,696 |
| `wd:P279` | 5,312 |
| `wd:P910` | 3,033 |
| `wd:P5008` | 1,261 |

These seven keys account for 99,507 of the 102,154 missing assertions. The data
layer needs an explicit pass-through row or an explicit exclusion rule for each
missing predicate. Silent fallback is not deterministic mapping.

## Random mapping examples

### Reverse translations

The fixed sample contains reasonable reverse transformations:

- `USS Shasta — operator (P137) → United States Navy` becomes
  `United States Navy — item operated (P121) → USS Shasta`.
- `11th U-boat Flotilla — has part (P527) → U-1302` becomes
  `U-1302 — part of (P361) → 11th U-boat Flotilla`.
- `Q132537 — doctoral student (P185) → Robert Serber` becomes
  `Robert Serber — doctoral advisor (P184) → Q132537`.

These examples agree with the formal inverse rule and the endpoint swap.

### Same-direction translations

The sample also contains plausible same-direction translations:

- DBpedia `award` becomes Wikidata `award received (P166)`.
- DBpedia `country` becomes Wikidata `country (P17)`.

This is evidence that the sampled mapping and direction are reasonable. It is
not proof that every source assertion is historically correct.

## Question-oriented findings

### “Where did the event happen?”

The documented relation group yields 8,060 assertions:

| Level 2 relation | Assertions | Event → location in draft types | Review |
|---|---:|---:|---|
| `wd:P276` location | 3,996 | 47 | Possible answer relation, but check place scale and endpoint identity |
| `wd:P131` administrative area | 3,968 | 9 | Context or containment; not general proof of event occurrence |
| `wd:P706` physical feature | 96 | 0 | Physical context; not general proof of event occurrence |

Only 56 of 8,060 assertions have the strict `event → location` type pair in the
draft. This low count is mainly an endpoint metadata and type problem. It does
not show that the Level 2 codes are wrong.

The sample illustrates the difference:

- `Battle of Midway — P276 → Q47863` is a suitable location relation, but
  `Q47863` is not named or typed as Midway Atoll in the draft.
- `Casablanca Conference — P131 → Q7903` can give an administrative place, but
  `P131` must remain distinct from an explicit event-occurrence relation.
- `Paris in World War II — P706 → Paris` is spatial context. It should not be
  treated as a precise battle-site assertion.

### “Who participated?” and “Who attacked?”

The participation and command group yields 74,597 assertions:

| Level 2 relation | Assertions | Safe use |
|---|---:|---|
| `wd:P607` conflict | 57,938 | Conflict participation or association only |
| `wd:P598` commander of | 5,464 | Command relation after endpoint check |
| DBpedia `commander` | 4,388 | Command relation after endpoint check |
| `wd:P1344` participant in | 2,604 | Participation only |
| `wd:P710` participant | 2,459 | Participation only; event is normally the subject |
| YAGO `participatedIn` | 1,744 | Participation only |

These relations can support participation or command questions. They do not
identify attacker and defender roles. The v2.1 table contains no general
`ATTACKED` relation. Predicates whose labels contain “aircraft attack” are
aircraft attributes, not attack assertions between an actor and a place.

For the named examples:

- Battle of Midway has `P710` participants and several DBpedia `commander`
  assertions. These are useful for participant and commander questions.
- It also has many `P607` person-to-conflict links. They do not prove which side
  attacked.
- Two graph nodes are both named “Battle of Guam.” Relation mapping does not
  solve the 1941 versus 1944 identity question. The date and entity-resolution
  layer must do that.
- “KISKA” resolves in the draft to an organization-like node, while the island
  is not available under the expected name. This is an identity problem, not a
  relation-translation problem.

Therefore, “Who attacked Guadalcanal in 1942?” must require an exact action and
role assertion, or supporting passage evidence. It must not translate
`participant`, `conflict`, or `commander` into `attacked`.

### Hierarchy and reverse direction

There are 16,916 replayed part-whole assertions under canonical `wd:P361`.
The sample includes both direct `P361` and reversed `P527` assertions. The
reversed examples preserve the correct subject and object after the swap.

This supports using the relation map for hierarchy expansion. The returned
assertion must still include the explicit direction-specific relation ID and
label. The Agent must not infer the reverse meaning itself.

### Broad spatial search

Level 1 `SPATIAL` can help to build a candidate list for “all places connected
to X.” It must remain an optional search aid. The answer must show the exact
Level 2 relation, such as birth place, headquarters, administrative area, or
event location. These relations are not interchangeable.

## Recommended acceptance process

Run the sanity check after every mapping-table build and after every graph
export:

```powershell
& 'Agent\.venv\Scripts\python.exe' `
  'GG_Data\mapping\run_relation_mapping_sanity.py'
```

The run writes:

- `sanity_check_v2_1/summary.json`
- `sanity_check_v2_1/relation_mapping_sanity_sample.csv`
- `sanity_check_v2_1/missing_v2_mapping_rows.csv`
- `sanity_check_v2_1/ambiguous_v2_mapping_keys.csv`
- `sanity_check_v2_1/question_relation_counts.csv`
- `sanity_check_v2_1/question_relation_type_pairs.csv`

Use these gates:

1. Every exported source predicate has exactly one deterministic v2 mapping or
   one explicit exclusion rule.
2. No lookup key produces more than one Level 2 ID.
3. The reverse-of-reverse check has zero errors.
4. Review the fixed random sample for exact meaning, direction, endpoint roles,
   and source plausibility.
5. Review the question-oriented sample separately. Mark each relation as direct
   answer evidence, context only, or insufficient.
6. After the developer supplies `gold.jsonl`, run the same graph version against
   all 56 questions and retain the question, tool payloads, retrieved evidence,
   final answer, and expected result.

Do not use the private Gold Set as a replacement for the broad random sample.
The random strata detect mapping-table faults that the 56 Agent questions may
never exercise.

## Limits

- v2.1 was replayed over the v1 assertion file. A graph exported directly with
  v2.1 does not yet exist in this folder.
- Draft node names and types are often missing or wrong. Type-pair counts are
  readiness diagnostics, not truth labels for the relations.
- The random sample can detect obvious defects. It cannot prove that all source
  values are correct.
- The private expected answers and full evaluation traces were not available.
- Geometry was not tested and is not needed for this relation-mapping check.
