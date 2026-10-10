# Finnish WWII relation-type alignment POC

## Purpose

Find rules that translate **relation types** between WarSampo, Wikidata, and
EventKG. Do not copy their instance data into the Pacific graph. A few shared
Finnish WWII objects are checks on the rules, not an extraction target.

## Mapping rule

For each candidate pair of source predicates:

1. Read each property's definition, domain, range, and known superproperties.
   Record its native source and identifier. For EventKG, also record the named
   source graph: a Wikidata-derived EventKG fact is not independent evidence.
   If EventKG retains Wikidata `P607`, record it as a source-preserving reuse
   of that predicate, not as a new semantic alignment.
2. Check the subject and object types. Align a source pair only when both
   endpoints are the **same real objects**. A matching QID or label is not enough:
   an individual boat and a boat class, for example, are different objects.
3. Compare relation meaning and direction. Test both same-direction and
   reversed subject–object order. Compare time qualifiers as attributes of a
   statement; do not treat a date as part of the relation type.
4. Use several valid shared pairs to find a candidate mapping. Frequency ranks
   candidates for review; it never proves their meaning. A missing relation in
   one source is not a negative example.
5. Assign one decision:

   - **Equivalent within a stated scope:** each predicate implies the other for
     the allowed subject and object types.
   - **Narrower / broader:** one predicate implies the other, but not conversely.
   - **Inverse:** the same meaning with subject and object reversed. State any
     narrower or broader scope as well.
   - **Related:** the predicates often occur near the same objects but assert
     different things.
   - **Rejected:** definitions or verified endpoints conflict.
   - **Unresolved:** definitions, endpoint identity, or source evidence is
     insufficient.

The output is a small **mapping registry**, not a new set of extracted facts.
Each registry entry needs the two native predicate IDs, mapping class, allowed
subject/object types, direction, time-attribute rule, source definitions,
reviewed examples, and a reason for the decision. Keep original statements and
provenance when a mapping is used later.

## Decisions from this POC

| Source relation types | Decision | Reason and scope |
| --- | --- | --- |
| WarSampo [`hasConflict`](http://ldf.fi/schema/warsa/actors/hasConflict) ↔ Wikidata [`P607`](https://www.wikidata.org/wiki/Property:P607) | **Equivalent within scope** | Both mean “participated in conflict” and point **military unit → conflict**. WarSampo defines that domain and range; Wikidata's broader subject allowance does not make the properties globally identical. [Squadron 46](http://ldf.fi/warsa/actors/actor_465) ↔ [Q7043537](https://www.wikidata.org/wiki/Q7043537) and [Squadron 44](http://ldf.fi/warsa/actors/actor_464) ↔ [Q7043512](https://www.wikidata.org/wiki/Q7043512) are checks on the same Winter/Continuation War pairs. Conflict dates match at the conflict object; they are not relation types. |
| CIDOC CRM [`P11 had participant`](https://cidoc-crm.org/Property/p11-had-participant/version-7.1) (WarSampo event → actor) ↔ Wikidata `P607` (actor → conflict) | **Unresolved for these data; conditional inverse and broader meaning** | `P11` covers participation in any event and reverses `P607`'s direction. It can describe a `P607` pair only if the actor and event are the **same actor and conflict**, and the actor meets CIDOC CRM's actor type. A smaller event during the conflict is insufficient. WarSampo [event_161](http://ldf.fi/warsa/events/event_161) is a command change within the Winter War, so its `P11` edge to [Paavo Talvela](http://ldf.fi/warsa/actors/person_50) does not directly map to [Talvela's `P607` Winter War claim](https://www.wikidata.org/wiki/Q2383184). |
| WarSampo [`related_period`](http://ldf.fi/schema/warsa/events/related_period) ↔ Wikidata `P607` | **Rejected** | `related_period` links an event to its period. `P607` links a participant to a conflict. Their subject types and meanings differ, even when the period is a war. |
| EventKG relation type ↔ WarSampo/Wikidata type | **Unresolved** | Inspect EventKG's original predicate and named source graph before any mapping. Its [public schema and data](https://eventkg.l3s.uni-hannover.de/data.html) identify those sources; the query service returned HTTP 500 during this POC. Do not count a Wikidata-derived EventKG edge as a second independent match. |

**Result:** one scoped two-source mapping accepted, one candidate rejected, and
two candidates unresolved. There is no approved three-source mapping yet.
Existing source facts stay in their original graphs. This POC does not enrich
the Pacific graph.
