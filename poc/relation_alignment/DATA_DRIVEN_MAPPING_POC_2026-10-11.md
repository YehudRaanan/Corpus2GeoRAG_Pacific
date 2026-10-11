# Data-driven relation mapping POC

Date: 2026-10-11

## Question

Can shared relation records map source predicates to Wikidata properties
without using predicate names as model features?

This is a small method test. It does not accept final ontology mappings and it
does not change source data.

## Data and method

The POC uses ten EventKG relation groups from the local WWII population. A
group has one source graph, subject kind, object kind, and direction. It uses
the existing EventKG-Wikidata QID-pair overlap and the earlier `hasPlace`
context test. It also tests the three available WarSampo-EventKG overlap paths.

The score uses only:

- percentage of co-connected QID pairs that share the Wikidata property;
- stability after removal of the largest target QID;
- stability on a target-held-out sample;
- number of shared pairs.

The score does not use predicate names, property labels, or definitions.
Names are used only to select and display the POC cases. A test changes the
names while keeping the numeric evidence fixed and confirms that the score is
unchanged.

The score is:

```text
45% pair coverage
+ 25% stability after the largest target
+ 20% held-out stability
+ 10% sample support, capped at 100 pairs
```

A strong candidate needs at least 20 shared pairs, five held-out pairs, five
distinct targets, 90% pair coverage, 80% stability after the largest target,
and 80% held-out stability. A provisional map also needs a 15-point lead over
the next candidate.

Pair coverage uses the co-connected denominator: EventKG pairs for which
Wikidata has at least one same-direction or reverse-direction property. It is
not coverage of every EventKG record.

## Results

| EventKG group | Top Wikidata candidate | Direction | Score | Result |
|---|---|---:|---:|---|
| `award`, DBpedia, entity→entity | `P166` | same | 98.5 | provisional map |
| `battle`, DBpedia, entity→event | `P607` | same | 98.1 | provisional map |
| `hasWonPrize`, YAGO, entity→entity | `P166` | same | 100.0 | provisional map |
| `usedInWar`, DBpedia, entity→event | `P607` | same | 100.0 | provisional map |
| `subEventOf`, direct, event→event | `P361` | same | 98.2 | provisional map |
| `hasSubEvent`, direct, event→event | `P361` | reverse | 98.2 | provisional map; equivalent direction to `P527` |
| `country`, DBpedia, entity→entity | `P17` | same | 72.6 | unresolved mixed relation |
| `hasPlace`, DBpedia, event→entity | `P276` | same | 46.2 | unresolved mixed relation |
| `hasPlace`, YAGO, event→entity | `P710` | same | 46.9 | unresolved mixed relation |
| `isCitizenOf`, YAGO, entity→entity | `P27` | same | 91.6 | unresolved: only 16 shared pairs and two target QIDs |

The result correctly permits different mappings for the same source predicate
under different source graphs. The two `hasPlace` groups choose different top
candidates, but neither passes the gates.

## Context check for `hasPlace`

The earlier context test used Wikidata endpoint types and EventKG source
indicators. It contained 317 pairs, of which 101 had one or more selected
Wikidata codes.

- Type-only grouped validation: 49.5% exact match.
- All context features: 47.5% exact match.
- Most-common-code baseline: 28.7%.

Context adds information, but it does not separate `P17`, `P276`, and `P710`
well enough. Nine coded pairs have more than one valid code. The production
method must allow several relations or abstain.

## WarSampo bridge

| WarSampo predicate | EventKG bridge | Wikidata candidate | Direction | Shared pairs | Result |
|---|---|---|---:|---:|---|
| `hasConflict` | `battle` | `P607` | same | 5 | insufficient support |
| CIDOC `falls within` | `subEventOf` | `P361` | same | 3 | insufficient support |
| CIDOC `falls within` | `hasSubEvent` | `P361` | same after two direction reversals | 3 | insufficient support |

The two `falls within` paths use the same three endpoint pairs. They are two
consistent paths, not independent samples.

## Decision

The method can find strong mapping candidates without relation names. It also
detects mixed relations and small samples that must remain unresolved.

This POC supports a two-stage automatic process:

1. Use endpoint overlap, direction, source graph, endpoint kinds, and stability
   tests to make provisional mappings.
2. Use endpoint types, graph context, and co-mention text only for unresolved
   groups. Permit multiple results and abstention.

The numeric weights and gates are POC settings. They need validation on more
relations before production use. Repeated pairs show structural agreement;
they do not prove that two predicate definitions are exactly equal.

## Files

- `data_driven_mapping_poc/candidate_rankings.csv`: top five Wikidata
  candidates for each EventKG group.
- `data_driven_mapping_poc/group_decisions.csv`: one automatic decision per
  group.
- `data_driven_mapping_poc/warsampo_transitive_candidates.csv`: WarSampo paths
  through EventKG.
- `data_driven_mapping_poc/summary.json`: machine-readable summary.

Run:

```powershell
python poc/relation_alignment/run_data_driven_mapping_poc.py
```
