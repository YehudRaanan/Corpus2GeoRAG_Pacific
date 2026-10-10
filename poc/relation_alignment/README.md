# Finnish WWII relation alignment POC

Run `python poc/relation_alignment/run.py` from the repository root. The script
reads the public WarSampo SPARQL service and Wikidata API. It writes
`overlap.json`; it does not edit either knowledge graph or the Pacific data.
The live-source counts below were captured on 2026-10-11.

## Scope and method

1. Read WarSampo `owl:sameAs` links to Wikidata from military units that have
   [`warsa:hasConflict`](http://ldf.fi/schema/warsa/actors/hasConflict). Normalize
   `http://www.wikidata.org/entity/Q...` and `https://www.wikidata.org/wiki/Q...`
   forms to the same QID.
2. Match the conflict object by its WarSampo English label and exact war dates:
   [Winter War](http://ldf.fi/warsa/conflicts/WinterWar) =
   [Q134949](https://www.wikidata.org/wiki/Q134949), 1939-11-30 to 1940-03-13;
   [Continuation War](http://ldf.fi/warsa/conflicts/ContinuationWar) =
   [Q122100](https://www.wikidata.org/wiki/Q122100), 1941-06-25 to 1944-09-19.
   These dates agree between WarSampo `P4_has_time-span` and Wikidata `P580`/`P582`.
3. Compare the same actor–conflict pair with Wikidata
   [`P607`](https://www.wikidata.org/wiki/Property:P607). WarSampo calls
   `hasConflict` “participated in conflict” and gives it military-unit domain
   and conflict range. Wikidata defines `P607` as battles, wars, or military
   engagements in which a person or item participated. Both point from
   participant to conflict. Wikidata's matching `P607` statements have no
   time qualifiers; the war dates belong to the conflict objects, not to the
   relation type.
4. Review five identity examples manually before accepting a predicate mapping.
   `owl:sameAs` alone is only a candidate identity link.

## Counts and review

WarSampo has **159** distinct resources with a Wikidata `owl:sameAs` link
(separate count query). Of these, **77** linked unit QIDs have **93**
`hasConflict` rows for the mapped wars. **75** of those QIDs yield **87**
same-QID, same-war `P607` pair candidates. These are *candidate* overlaps, not
87 validated identities: one pair below has a wrong object identity despite
matching predicates. The other 6 WarSampo rows have no matching `P607` claim.

| Review | WarSampo actor → conflict | Wikidata actor → conflict | Evidence and decision |
| --- | --- | --- | --- |
| Accepted | [actor_465](http://ldf.fi/warsa/actors/actor_465) → [Winter War](http://ldf.fi/warsa/conflicts/WinterWar), `hasConflict` | [Q7043537](https://www.wikidata.org/wiki/Q7043537) → [Q134949](https://www.wikidata.org/wiki/Q134949), `P607` | “Lentolaivue 46” = “Squadron 46”; same unit, same war, same direction. Also matches Continuation War. |
| Accepted | [actor_464](http://ldf.fi/warsa/actors/actor_464) → [Continuation War](http://ldf.fi/warsa/conflicts/ContinuationWar), `hasConflict` | [Q7043512](https://www.wikidata.org/wiki/Q7043512) → [Q122100](https://www.wikidata.org/wiki/Q122100), `P607` | “Lentolaivue 44” = “Squadron 44”; same unit, same war, same direction. Also matches Winter War. |
| Accepted | [actor_463](http://ldf.fi/warsa/actors/actor_463) → [Winter War](http://ldf.fi/warsa/conflicts/WinterWar), `hasConflict` | [Q5463498](https://www.wikidata.org/wiki/Q5463498) → [Q134949](https://www.wikidata.org/wiki/Q134949), `P607` | “Lentorykmentti 4” = “Flying Regiment 4”; same unit, same war, same direction. Also matches Continuation War. |
| Rejected identity | [actor_2245](http://ldf.fi/warsa/actors/actor_2245) → Winter War, `hasConflict` | [Q2332854](https://www.wikidata.org/wiki/Q2332854) → Q134949, `P607` | WarSampo names one motor torpedo boat, “Moottoritorpedovene Sisu”; Wikidata names a *class* of boats. The pair matches by QID but the actor objects differ. Do not count this as a validated relation pair. |
| Rejected identity | [actor_313](http://ldf.fi/warsa/actors/actor_313) → Winter War, `hasConflict` | [Q10240708](https://www.wikidata.org/wiki/Q10240708), no matching `P607` | WarSampo identifies an air-defense headquarters; Wikidata identifies a Wikimedia category. This `owl:sameAs` link is unusable for relation alignment. |

The corresponding Wikidata `P607` statement IDs for the first four rows are
`Q7043537$b34265c3-4d5d-b77d-6cfe-f167276a9879`,
`Q7043512$b3639d36-4bd7-cd0f-1083-cfd0726afa1b`,
`Q5463498$f00029fa-480a-8d39-7577-aa77b8d7d9fe`, and
`Q2332854$9a75e9c6-4466-c49a-2d25-e1428097f63a`, respectively. The
machine-readable file retains all source actor IDs, conflict IDs, and matching
statement IDs.

**Mapping decision:** **1 accepted predicate mapping in the reviewed scope:**
WarSampo `hasConflict` ↔ Wikidata `P607`, for a validated military-unit →
conflict pair. It is an equivalent relation *within this scope*, with the same
direction. Three manually checked identities support it; they cover six
same-pair conflict rows. The table also records two rejected identity links.
One further candidate row was rejected because its actor identity is wrong.
The other 80 candidate rows have not had individual endpoint review, so they
are not accepted mappings or facts.

## Paavo Talvela and EventKG limits

[WarSampo person_50](http://ldf.fi/warsa/actors/person_50) explicitly links to
[Q2383184](https://www.wikidata.org/wiki/Q2383184). Its nearby
[event_161](http://ldf.fi/warsa/events/event_161) has
`P11_had_participant person_50` and `related_period WinterWar`, with date
1940-02-19. Wikidata has `Q2383184 P607 Q134949`. This is a **two-edge
WarSampo path versus a direct Wikidata statement**. `event_161` is a specific
command change, not the entire Winter War. Therefore `P11_had_participant` or
`related_period` must **not** be mapped to `P607` from this example.

[EventKG V3.2](https://eventkg.l3s.uni-hannover.de/data.html) advertises event
and relation files, but its [public SPARQL service](https://eventkginterface.l3s.uni-hannover.de/sparql)
returned HTTP 500 for a basic query on 2026-10-11. The full relevant relation
files are multi-gigabyte; the small preview files do not establish coverage of
these Finnish IDs. **EventKG overlap and mappings remain unresolved**. No
three-source mapping passed review. EventKG is derived in part from Wikidata,
so any future EventKG match must retain its source graph and must not be
treated as independent confirmation.

The result is a working two-source POC with one reviewed mapping, plus a clear
block on the proposed three-source comparison. The Pacific graph was not read
or changed.
