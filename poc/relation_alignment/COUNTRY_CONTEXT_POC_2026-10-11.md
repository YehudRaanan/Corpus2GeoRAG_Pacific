# Data-driven `country` relation split POC

Date: 2026-10-11

## Question

Can graph context split the DBpedia EventKG `country` predicate into Wikidata
`P17` and `P8047` without using relation names?

This is a method test on the local WWII population. It does not create or
accept graph relations.

## Data

The EventKG group contains 3,099 entity-to-entity QID pairs.

| Observed Wikidata codes on the same pair | Pairs |
|---|---:|
| `P17` only | 1,359 |
| `P8047` only | 1,123 |
| Both | 17 |
| Neither recorded | 600 |

An absent Wikidata code is unknown. It is not a negative fact.

## Features

The model uses 227 context features:

- subject and object `P31` types;
- available one-level `P279` parent types;
- other item-valued Wikidata properties around each endpoint.

`P17` and `P8047` are removed from the features. Predicate names, property
labels, and descriptions are also excluded. Labels are attached only after
training for human review.

Two independent binary trees predict `P17` and `P8047`. This permits either
code, both codes, or neither. Five validation folds hold out complete subject
`P31` signatures.

## Result

| Feature set | Exact code-set match | Macro label F1 |
|---|---:|---:|
| Types and nearby properties | 98.9% | 99.2% |
| Nearby properties only | 98.9% | 99.2% |
| All features except subject `P137` | 98.7% | 99.0% |
| Types only | 56.1% | 39.5% |

The main split is whether the subject has Wikidata `P137`, `operator`:

| Observed code set | `P137` present | `P137` absent |
|---|---:|---:|
| `P17` only | 6 | 1,353 |
| `P8047` only | 1,118 | 5 |
| Both | 17 | 0 |
| Neither recorded | 136 | 464 |

The result is not dependent on `P137` alone. Exact agreement stays at 98.7%
when that feature is removed. Other nearby properties contain similar object
context.

## Important failure

The grouped validation finds:

- 1,353 of 1,359 `P17`-only pairs;
- 1,118 of 1,123 `P8047`-only pairs;
- **0 of 17 pairs that contain both codes**.

The high average score therefore describes the two large single-code groups.
It does not solve the rare multi-relation case.

## Unrecorded pairs

For the 600 pairs without either recorded code, the context model suggests:

- 464 `P17` candidates;
- 136 `P8047` candidates.

These are saved as `CANDIDATE_FOR_TEXT_CHECK`. None is accepted. The model has
not shown that a missing Wikidata statement is a true relation.

## Decision

Graph context can automatically separate the two dominant meanings of this
source predicate. It is suitable for candidate routing.

The next step is narrow: collect Wikipedia sentences for the 17 known
multi-code pairs and a sample of the 600 unrecorded pairs. Test whether text
can detect both relations and confirm or reject the context candidates. Keep
abstention as an allowed result.

The method must also be tested on another source graph before production. All
pairs in this POC come from the DBpedia English graph, so the result can still
contain source-specific patterns.

## Files

- `country_context_poc/cases.csv`: pair-level evidence and candidate status.
- `country_context_poc/feature_importance.csv`: features used by each binary
  model.
- `country_context_poc/summary.json`: validation results and tree rules.

Run:

```powershell
python poc/relation_alignment/run_country_context_poc.py
```
