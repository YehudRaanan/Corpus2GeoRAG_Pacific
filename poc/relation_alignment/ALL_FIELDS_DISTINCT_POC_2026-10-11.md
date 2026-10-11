# Full-field adaptive distinct POC for `hasPlace`

## Scope

This run applies the adaptive split process to all 317 saved EventKG
`hasPlace` pairs. It extracts fields for every pair. The split selection and
validation use the 101 pairs that have a recorded same-pair Wikidata code.
The other 216 pairs remain unknown and are assigned only after the split is
learned.

The input includes 343 Wikidata items and all complete local EventKG field
families: structure, types, claims, qualifiers, references, dates, source
graphs, labels, English descriptions, nearby relation roles, and pair text
context. Five incomplete EventKG folders are excluded and reported in the JSON
output. WarSampo adds no field to this run because it has zero screened
identity QIDs and zero same relation pairs in this 317-pair population.

Identifiers, EventKG resource IDs, the target `P17`/`P276`/`P710` claims,
previous model outputs, and technical revision metadata are not predictors.
Copied Wikidata target relations inside EventKG are also excluded.

## Result

The scan produced 16,508 distinct fields across all pairs. Of these, 6,497
meet the minimum frequency rule on the 101 coded pairs. The process selected
four fields before no unused field could make a supported split and reduce
the mixed population.

| Step | Selected field | New groups | Coded pairs still mixed | Coded pairs in consistent groups |
| --- | --- | ---: | ---: | ---: |
| Start | None | - | 101 | 0 |
| 1 | Object has a non-Wikidata EventKG `participatedIn` relation | 1 | 66 | 35 |
| 2 | Subject `P950` reference contains `P1476` | 1 | 60 | 41 |
| 3 | Subject EventKG label contains `invasion` | 1 | 55 | 46 |
| 4 | Subject English EventKG description contains `off` | 1 | 52 | 49 |

The first field is the main result. It was selected first in all five
object-held-out folds. The other fields changed between folds and can be
accidental metadata or wording patterns.

## Groups after applying the split to all 317 pairs

The pattern bits follow the four selected fields in the table above.

| Pattern | All pairs | Coded | Unknown | Recorded code evidence |
| --- | ---: | ---: | ---: | --- |
| `0000` | 81 | 35 | 46 | All 35 are `P276` |
| `0100` | 6 | 0 | 6 | No coded evidence |
| `1000` | 196 | 52 | 144 | Mixed: `P17`, `P276`, `P710`, and combinations |
| `1001` | 5 | 3 | 2 | All 3 are `P710` |
| `1010` | 14 | 5 | 9 | All 5 are `P710` |
| `1100` | 15 | 6 | 9 | All 6 are `P710` |

The full fitted split places 49/101 coded pairs in consistent groups and
leaves 52/101 mixed. Object-held-out validation applies a supported consistent
rule to 37/101 pairs and matches the recorded code set for 32/37 applications
(86.5%). It abstains on 64/101 pairs.

## Interpretation

The process found useful structure, but it did not fully resolve `hasPlace`.
The `participatedIn` field is a strong separator and is the only stable field.
Its absence cannot prove a location relation because a knowledge graph can
omit a true participation fact. Therefore, use it to rank candidates and to
request evidence, not as a final automatic relation mapping.

The later fields should not become production rules. They improve the fitted
sample, but their meanings are weak and their fold selection is unstable. A
safe automatic process should keep these cases unresolved until source text
or another explicit relation confirms the role.

## Reproduce

Run:

```powershell
python poc/relation_alignment/run_all_fields_distinct_poc.py
```

Machine-readable results are in `all_fields_distinct_summary.json`. Pair-level
group assignments are in `all_fields_distinct_assignments.csv`.
