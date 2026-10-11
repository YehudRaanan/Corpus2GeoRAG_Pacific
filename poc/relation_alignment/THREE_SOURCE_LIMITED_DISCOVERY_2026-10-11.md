# Limited three-source discovery: Finnish WWII overlap

Status: local snapshot, 11 October 2026. The EventKG V3.2 scan was still
running. This is a small applicability check, not a complete alignment or an
import into the Pacific graph.

## Selection

Start with the **122 distinct QID endpoint pairs** on which the previous
[WarSampo–Wikidata audit](audit_2026-10-11/REPORT.md) found a relation in both
graphs after its identity screen. Keep the **19 pairs** for which both QIDs also
have EventKG resource IDs. This selects 14 unit-to-war pairs, two
unit-to-parent-unit pairs, and three war-to-WWII pairs. The WarSampo identity
screen includes provisional `screened` links; only some links were manually
`reviewed`. The 19 pairs are a test sample, not a coverage estimate for all
three sources.

## What the local data shows

| Shared pair group | WarSampo ↔ Wikidata overlap | EventKG result in completed files |
| --- | --- | --- |
| Unit → war: 14 pairs | `hasConflict` ↔ `P607` | All 14 have EventKG reified `P607` in its Wikidata graph. Five also have DBpedia English `battle` on the same directed pair. The Wikidata graph repeats Wikidata data; `battle` is a separate source claim and a mapping candidate. |
| Unit → parent unit: two pairs | `hasUpperUnit` ↔ `P361` and reverse `P527` | Both QID endpoints map to EventKG entities. Its `relations_entities_other` file was still scanning, so relation coverage is pending. The `P361` and `P527` records describe the same two pairs in opposite directions. |
| War → WWII: three pairs | `P10_falls_within` ↔ `P361`; two also have `P2348` | EventKG has direct `sem:subEventOf` links on all three pairs. Two also have reified `P2348` in its Wikidata graph. `subEventOf` needs a separate meaning check before it can be translated to either Wikidata property. |

Example for a unit-to-war pair: WarSampo
[`actor_439`](http://ldf.fi/warsa/actors/actor_439) →
[`ContinuationWar`](http://ldf.fi/warsa/conflicts/ContinuationWar) uses
`hasConflict`; Wikidata [Q5412831](https://www.wikidata.org/wiki/Q5412831) →
[Q122100](https://www.wikidata.org/wiki/Q122100) uses `P607` in statement
`Q5412831$ecfcb517-440c-c508-f218-9a079127fbb9`. EventKG has both a
Wikidata `P607` relation and DBpedia English `battle` relation
`relation_35536951` on that pair. The Q5412831 identity is screened, not
fully reviewed.

Example for a unit hierarchy pair: WarSampo `actor_17387` (VI Corps) →
`actor_18077` (Army of Karelia) uses `hasUpperUnit`; Wikidata
[Q11894949](https://www.wikidata.org/wiki/Q11894949) →
[Q4214925](https://www.wikidata.org/wiki/Q4214925) uses `P361` in statement
`Q11894949$2a6b2b69-41da-a571-a921-65449c1974b4`. Wikidata also has the
reverse `P527` statement. The Army of Karelia identity is still screened.

## EventKG enrichment and checks

For the [Continuation War](https://www.wikidata.org/wiki/Q122100), EventKG has
19 subevent QIDs. The selected Wikidata population has 15 subevent QIDs linked
by incoming `P361` or outgoing `P527`; one more outgoing `P527` target is
outside that population. Thirteen of the in-scope QIDs are shared, and **six are
EventKG-only as direct links under those two Wikidata properties**. Two of
the six already have a two-step Wikidata `P361` path through the
[Vyborg–Petrozavodsk Offensive, Q700533](https://www.wikidata.org/wiki/Q700533).
For example, EventKG links the
[Battle of Vyborg Bay, Q2081621](https://www.wikidata.org/wiki/Q2081621)
by `sem:hasSubEvent` from `event_834917` to `event_803096`.
Its Wikidata `P361` points to Q700533, which points to Q122100. These two
EventKG links may expose an existing Wikidata path rather than new facts.
The other four have no such path in the selected Wikidata records and need
individual review. The direct EventKG `hasSubEvent` triples in this file have
no named source graph. EventKG also provides
Wikipedia first sentences for the four war events examined (WWII, Winter War,
Continuation War, and Lapland War).

EventKG retains conflicting source dates. For the Winter War event
`event_735887`, `sem:hasEndTimeStamp` is **1940-03-13** in its Wikidata and
`event_kg` graphs, but **1939-11-30** in DBpedia English and **1939-12-31**
in YAGO. Wikidata `P582` is 1940-03-13. The source graph and time precision
must stay with each date; selecting an arbitrary EventKG value would produce
the wrong interval. Continuation War `event_834917` even has both 1941-06-25
and 1944-09-19 as begin timestamps in EventKG's Wikidata graph, while its
Wikidata `P580` is 1941-06-25.

## Decision for this small test

The plan is usable as a **source-preserving discovery workflow**: shared QIDs
make the WarSampo–Wikidata relation comparison possible, while EventKG adds
event hierarchy, text, and some non-Wikidata source claims. The extra edges
and dates need validation before graph export. Finish `relations_entities_other`
to assess the two unit-hierarchy pairs; then review the four Continuation War
subevent candidates without a Wikidata path and define a date selection rule.
No new relation-type mapping is accepted by this test.

Local evidence: `audit_2026-10-11/joint_relation_pairs.csv`,
`identity_candidates.csv`, `Data/external/wwii_task_force/wikidata_entities.jsonl.gz`,
the EventKG `events` and `entities` QID maps, and the completed
`relations_events_other`, `relations_entities_temporal`,
`relations_events_base`, and `events_first_sentences` files. The EventKG
files preserve source IDs and named graphs where the source has them.
