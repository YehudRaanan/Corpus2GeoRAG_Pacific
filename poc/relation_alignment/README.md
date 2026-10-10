# Finnish WWII relation-type alignment POC

The [executed two-source overlap audit](audit_2026-10-11/REPORT.md) checks the
broader WarSampo–Wikidata candidate set and records the remaining identity and
event-link gaps. This README preserves the original smaller POC.

The [full WarSampo–Wikidata mapping process](../../docs/WARSAMPO_WIKIDATA_RELATION_MAPPING_PROCESS.md)
defines the complete-coverage audit. This file records the smaller POC.

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
| CIDOC CRM [`P11 had participant`](https://cidoc-crm.org/Property/p11-had-participant/version-7.1) (WarSampo event → actor) ← Wikidata [`P710 participant`](https://www.wikidata.org/wiki/Property:P710) (event → actor) | **One-way candidate; no shared event pair checked** | `P710` requires active participation. `P11` permits active or passive participation. For the same event and actor, `P710` can map to `P11`; the reverse may lose this distinction. Wikidata also recommends role qualifier `P3831`, which must be retained. |
| CIDOC CRM [`P7 took place at`](https://cidoc-crm.org/html/cidoc_crm_v7.1.3.html) (WarSampo event → place) ↔ Wikidata [`P276 location`](https://www.wikidata.org/wiki/Property:P276) ↔ EventKG [`sem:hasPlace`](https://eventkg.l3s.uni-hannover.de/tutorial.html) | **Scoped location candidate; no shared event/place pair checked** | All can express an event's place. `P276` also covers non-events; CIDOC `P7` can name a broad area. EventKG's [Wikidata location mapping](https://github.com/sgottsch/eventkg/blob/master/src/resource/meta_data/wikidata/property_names_locations.tsv) lists `P276`. Check the exact event and place before declaring equivalence. |
| CIDOC CRM [`P10 falls within`](https://cidoc-crm.org/html/cidoc_crm_v7.1.3.html) (WarSampo conflict → period) ↔ Wikidata [`P361 part of`](https://www.wikidata.org/wiki/Property:P361) (war → larger war) | **Related; not equivalent** | [Winter War](http://ldf.fi/warsa/conflicts/WinterWar) and [Continuation War](http://ldf.fi/warsa/conflicts/ContinuationWar) each fall within WarSampo's Second World War and have Wikidata `P361` → [Q362](https://www.wikidata.org/wiki/Q362). `P10` concerns a period within a larger period's spacetime; `P361` states a part–whole relation. The shared pairs suggest a useful translation only after its intended meaning is specified. |
| EventKG [`sem:hasSubEvent`](https://eventkg.l3s.uni-hannover.de/tutorial.html) (whole event → subevent) ↔ Wikidata [`P361 part of`](https://www.wikidata.org/wiki/Property:P361) (subevent → whole) | **Inverse candidate; no shared pair checked** | The directions reverse. Restrict to events and verify that “subevent” and “part of” refer to the same event boundary. Do not infer this from labels alone. |
| CIDOC CRM [`P11 had participant`](https://cidoc-crm.org/Property/p11-had-participant/version-7.1) (WarSampo event → actor) ↔ Wikidata `P607` (actor → conflict) | **Unresolved for these data; conditional inverse and broader meaning** | `P11` covers participation in any event and reverses `P607`'s direction. It can describe a `P607` pair only if the actor and event are the **same actor and conflict**, and the actor meets CIDOC CRM's actor type. A smaller event during the conflict is insufficient. WarSampo [event_161](http://ldf.fi/warsa/events/event_161) is a command change within the Winter War, so its `P11` edge to [Paavo Talvela](http://ldf.fi/warsa/actors/person_50) does not directly map to [Talvela's `P607` Winter War claim](https://www.wikidata.org/wiki/Q2383184). |
| WarSampo [`related_period`](http://ldf.fi/schema/warsa/events/related_period) ↔ Wikidata `P607` | **Rejected** | `related_period` links an event to its period. `P607` links a participant to a conflict. Their subject types and meanings differ, even when the period is a war. |
| EventKG [`sem:hasActor`](https://eventkg.l3s.uni-hannover.de/tutorial.html) ↔ `P11` or `P710` | **Rejected as a general mapping** | EventKG also uses `sem:hasActor` to link text events with entities named in their descriptions. Such a link alone does not prove participation. |

Time is a separate **attribute transformation**, not another relation mapping:
WarSampo/CIDOC `P4_has_time-span`, Wikidata `P580`/`P582`, and EventKG
`sem:hasBeginTimeStamp`/`sem:hasEndTimeStamp` can supply dates, subject to
precision and source checks. EventKG's [time-property mapping](https://github.com/sgottsch/eventkg/blob/master/src/resource/meta_data/wikidata/temporal_property_names.tsv)
lists `P580` and `P582`.

**Result:** one scoped mapping checked against shared objects; three more
relation-type candidates identified from definitions; one same-pair relation
found to be only related; two generic mappings rejected. The EventKG service
returned HTTP 500 during this POC, so no three-source pair has been checked.
Existing source facts stay in their original graphs. This POC does not enrich
the Pacific graph.
