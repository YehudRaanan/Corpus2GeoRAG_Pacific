# Discovery for an automatic relation-mapping process

Snapshot: 11 October 2026. **The deliverable is mapping logic and its failure
conditions, not extracted graph facts.** The diagnostic runner is
[`run_mapping_discovery.py`](run_mapping_discovery.py); its compact type-level
outputs are in [`mapping_discovery`](mapping_discovery/). It can run again after
the remaining EventKG files finish. This run used complete local files only.

## What was tested

The input population has 53,857 Wikipedia WWII task-force Wikidata QIDs. The
local Wikidata snapshot has all 53,857 requested records. EventKG has QID maps
for 38,517 of them (2,467 events and 36,050 entities). The older WarSampo
audit has 122 distinct co-connected QID pairs after its identity screen. This
run compared EventKG source-specific relation roles with Wikidata properties
on the **same directed QID pair**, checked the reverse direction, and checked
the screened WarSampo pairs against EventKG roles. EventKG's Wikidata named
graph was excluded from independent mapping evidence.

The local Wikidata records contain 572,283 non-deprecated item-valued claims:
108,250 point to another QID in the chosen population and 464,033 point
outside it. The latter are a **scope boundary**, not evidence that the
relationships are absent. Of the in-population claims, 104,588 distinct
directed QID pairs are available for comparison. Some EventKG relation and
link files are still scanning. In particular, `relations_entities_other` and
`relations_entities_base` were incomplete in this run. Do not call these
results complete EventKG coverage.

The runner found 244 EventKG–Wikidata candidate rows, stratified by EventKG
source graph, endpoint kind, and direct versus reified relation. A row is a
**candidate**, not an accepted semantic mapping. Only eight screened
WarSampo pairs also had a **non-Wikidata** EventKG role in completed files:
five `hasConflict`/DBpedia `battle` pairs and three `P10_falls_within`/EventKG
subevent pairs. EventKG's copied Wikidata relations are deliberately not
counted as a third vote. EventKG's missing unit relation file can change these
numbers.

## Findings that determine the method

| Candidate and scope | Same-pair evidence | What it teaches the mapping process |
| --- | ---: | --- |
| DBpedia English `battle` → Wikidata `P607`, entity → event, same direction | 7,178 / 7,263 co-connected DBpedia pairs; 20,484 DBpedia pairs with both QIDs | [DBpedia explicitly declares `owl:equivalentProperty` to `P607`](https://dbpedia.org/ontology/battle). This is a published schema alignment, not an independent observation derived from these pairs. 78.4% of matching pairs target WWII Q362. After removing Q362, the co-connected match rate is still 94.9%. Check source versions and instance scope before compiling the declared alignment into an operational rule. |
| DBpedia English `usedInWar` → `P607`, entity → event | 507 / 507 co-connected; 686 total; 84.6% of matches target Q362 | [DBpedia defines `usedInWar` for weapons and conflicts](https://dbpedia.org/ontology/usedInWar), not as an equivalent property of `P607`. A perfect local match cannot override that narrower meaning. |
| EventKG `subEventOf` → `P361`, event → event, same direction | 1,244 / 1,270 co-connected; 1,821 EventKG pairs | Promising event-only rule. The inverse EventKG `hasSubEvent` gives the same 1,244 pairs in reverse, not independent support. These direct triples lack a named source graph, so their derivation must be checked. |
| DBpedia English `commander` → reverse `P607` | 320 / 417 co-connected | [DBpedia `commander` has a person as its object](https://dbpedia.org/ontology/commander). A commander and a participant can be the same person and conflict, but command is a different role. This is a semantic counterexample to pair-frequency equivalence. |
| EventKG `hasPlace` → Wikidata `P17`, `P276`, or `P710` | 125, 86, and 43 same-direction pairs in the `event_kg` graph | [EventKG calls `hasPlace` an event location](https://eventkg.l3s.uni-hannover.de/tutorial.html), while Wikidata defines [`P17` as country](https://www.wikidata.org/wiki/Property:P17), [`P276` as location](https://www.wikidata.org/wiki/Property:P276), and [`P710` as active participant](https://www.wikidata.org/wiki/Property:P710). For example, Winter War Q134949 and Soviet Union Q15180 are connected by both EventKG `hasPlace` and Wikidata `P710`. Pair overlap alone cannot select the intended Agent edge. |
| YAGO `participatedIn` → reverse `P710` | 179 / 213 co-connected | Plausible inverse candidate. Check active/passive role and event granularity before accepting it. |

The earlier WarSampo–Wikidata audit already accepted `hasConflict` ↔ `P607`
**only for military unit → conflict**. This wider scan found **one published
schema alignment**, DBpedia `battle` ↔ Wikidata `P607`, but has not yet
validated it as an operational rule on all subject classes. It confirms why a
global predicate-to-predicate dictionary would be unsafe. The older
`owl:differentFrom` versus succession-property match also shows that even a
100% rate on one shared pair can be false.

Time needs a separate rule. Among 4,054 EventKG event/date-field combinations
with local values, 1,002 have multiple values **within at least one source
graph**, and 1,851 have multiple values across all graphs. These are counts of
different strings, **not counts of historical errors**: year-level dates and
day-level dates can differ in representation. Winter War Q134949 has several
end values across graphs; Continuation War Q122100 has two begin values in its
Wikidata graph. Preserve graph, precision, and original Wikidata qualifiers;
do not choose an arbitrary date.

## Proposed executable decision logic

1. **Require an identity gate.** Normalize each source endpoint to a QID, but
   keep the native ID and identity evidence. `approved` identities may support
   a rule; `screened` identities may rank candidates only; `unresolved` and
   `rejected` identities cannot vote. Check historical unit stage and exact
   event scale. The WarSampo audit has 7 reviewed, 243 screened, 323
   unresolved, and 3 rejected links, so this gate is currently the largest
   WarSampo constraint.
2. **Normalize claims without losing source meaning.** Represent each claim
   as native predicate, native subject/object IDs, QID subject/object, source
   graph, direct/reified/path form, endpoint classes, statement ID, role and
   time qualifiers, precision, and source revision. Deduplicate copied
   Wikidata claims across EventKG. Do not turn literals or dates into relation
   types.
3. **Generate candidates automatically from two channels.** First harvest
   published ontology links such as `owl:equivalentProperty`, inverses,
   subproperties, domain, and range. Record the ontology version; an ontology
   declaration is a candidate rule, not independent instance evidence. Then,
   for each exact approved QID pair, compare same and reverse directions.
   Group by endpoint class and event granularity. Compare direct relations
   only with direct relations; compare event paths under a separate path-rule
   hypothesis. Keep rare predicates and zero-overlap properties in the
   coverage report.
4. **Rank, then challenge.** Calculate shared distinct pairs, both eligible
   source denominators, number of subjects and targets, largest-target share,
   and rates after the dominant target is removed. Split evaluation by whole
   events or conflicts, not random duplicate statements. A missing statement
   is unknown, not a negative example. Check official property definitions,
   domain/range, inverse relationships, roles, and qualifiers. Seek known
   wrong matches on the same pairs.
5. **Decide with explicit conditions.** Output one of `equivalent_in_scope`,
   `inverse_in_scope`, `one_way`, `path_rule`, `related_only`, `rejected`, or
   `abstain`. An executable rule must include allowed endpoint types, event
   scale, direction, role constraints, time handling, source versions, and
   counterexamples. Frequency can propose a rule but cannot, by itself,
   accept one. Where formal definitions and reviewed examples do not settle
   meaning, the machine abstains.
6. **Measure automation before deployment.** Build a small blinded review set
   stratified by source, role, rare/common frequency, event group, and likely
   hard negatives. Hold out whole conflicts or event families. Report
   precision of **mapping decisions**, coverage, abstention rate, and
   disagreements by rule and scope, with uncertainty intervals. Tune any
   acceptance threshold on the review set, then freeze it before a separate
   holdout test. The current co-occurrence rates are not those accuracy
   measures.
7. **Compile only accepted rules.** The later code run applies a rule only
   when all conditions pass, retains source IDs and provenance, and sends
   every other case to a review queue. The rule registry is versioned. A
   changed source revision or new counterexample triggers revalidation.

## Attention order for the next run

| Priority | Weak point | Required check |
| --- | --- | --- |
| 1 | WarSampo event/place/unit identities | Resolve a stratified set of the 323 uncertain links and seek event/place QID bridges. Report how many candidate mappings remain blocked. |
| 2 | Incomplete EventKG relation/link scans and population boundary | Finish manifests; rerun diagnostics. Measure how many relevant relation endpoints lack QID maps or lie outside the task-force population. |
| 3 | Source reuse and missing provenance | Separate Wikidata-derived EventKG records; trace ungraphed `subEventOf` to its derivation before counting it as added evidence. |
| 4 | Predicate collisions and role specificity | Review `hasPlace`, `commander`, `usedInWar`, `hasUpperUnit`, and event participation with hard negative same-pair examples. |
| 5 | Conflict concentration and generalization | Hold out WWII Q362 and whole other conflicts; inspect subject classes and rare events. |
| 6 | Time and Agent vocabulary gaps | Reconcile precision and qualifier rules; identify Agent types such as `ATTACKED` and `DEFENDED` that the structured relations cannot establish. Test text evidence separately for those types. |

**Success condition:** a reviewed, versioned conditional rulebook with measured
mapping-decision accuracy and an explicit abstention path. This report and its
diagnostic CSVs are evidence for building that process; they are not the
Pacific graph or a completed semantic mapping registry.
