# EventKG conflict and broader-mapping resolution

## Result

All five conflict or broader EventKG predicates in the declared-mapping audit
can be resolved for the current EventKG data. The public ontology declarations
provide candidate paths. Endpoint data types and local observations select the
valid meaning where the public declarations conflict.

`schema:containedInPlace` is also handled here because EventKG deliberately
normalizes eight Wikidata properties into this one predicate.

| EventKG Level 2 | Observations | Public map | Data evidence | Project Level 2 decision |
| --- | ---: | --- | --- | --- |
| `dbo:locationCity` | 29 | `dbo:locationCity` is below `dbo:location`; `dbo:location` and Wikidata `P276` both map to `schema:location` | Objects are cities, towns, or settlements | `P276+OBJECT_TYPE_CITY` |
| `dbo:locationCountry` | 18 | `dbo:locationCountry` is below `dbo:location`; `dbo:location` and Wikidata `P276` both map to `schema:location` | Objects are countries, states, or historical countries | `P276+OBJECT_TYPE_COUNTRY` |
| `dbo:nextEvent` | 16 | `dbo:nextEvent` is below `dbo:followedBy` and DUL `precedes`; Wikidata `P156` also maps to DUL `precedes` | Every observed edge is event to event | `P156+EVENT_TO_EVENT` |
| `dbo:position` | 30 | DBpedia declares both Wikidata `P413` and `schema:position`; Wikidata maps `schema:position` to `P1545` | The EventKG objects are entity IRIs for sports positions. The subjects are athletes. `P413` takes an Item. `P1545` takes a String ordinal | `P413` |
| `dbo:voice` | 58 | DBpedia declares `P990`; current Wikidata declares DBpedia `dbo:voice` equivalent to `P725` | The EventKG objects are people or actors. `P725` takes a person Item. `P990` takes a Commons audio file | `P725` |
| `schema:containedInPlace` | 3,122 | EventKG's own manual map merges eight Wikidata properties | EventKG does not retain the original property in the normalized base edge | `COMBINED[P17|P131|P706|P1376|P3018|REV(P36)|REV(P150)|REV(P1383)]` |

## Resolution rules

1. Use an explicit exact property map when its domain, range, and observed
   object data type agree.
2. If two declared targets conflict, compare their data types and the actual
   EventKG endpoints. Keep the target that can represent those endpoints.
3. For a broader target, keep the missing restriction in the Level 2 key. This
   produces `P276+OBJECT_TYPE_CITY`, `P276+OBJECT_TYPE_COUNTRY`, and
   `P156+EVENT_TO_EVENT` instead of losing the EventKG detail.
4. If EventKG deliberately merged several valid source relations and the
   original source predicate is absent, create one deterministic combined Level
   2 key. Sort member IDs. Mark reverse members with `REV(...)`.
5. Keep different Level 2 meanings as separate relations under the same Level 1
   family. A shared Level 1 family is not a reason to merge Level 2 meanings.

## Why the two conflicts are resolved

### `dbo:voice`

DBpedia describes this property as a voice artist and gives it a `Person`
range. Wikidata `P725` means the performer of a spoken role and explicitly maps
to `dbo:voice`. Wikidata `P990` means an audio file of a subject's voice and has
the Commons-media-file data type. The current EventKG objects are people, so
`P725` is the valid target. The DBpedia `P990` declaration is rejected for this
data.

### `dbo:position`

DBpedia declares both `P413` and `schema:position`. The second path reaches
Wikidata `P1545`. `P413` is a sports position and takes an Item. `P1545` is a
String ordinal in a series. The current EventKG edges connect athletes to
position entities, so `P413` is the valid target. `P1545` remains valid only for
literal ordinal uses outside this observed EventKG set.

## `containedInPlace` direction

The combined key represents one canonical direction: **contained object to
containing place**.

- Keep the direction of `P17`, `P131`, `P706`, `P1376`, and `P3018`.
- Reverse `P36`, `P150`, and `P1383` before creating the canonical edge.

This preserves direction while meeting the decision to use one merged Level 2
relation.

## SEM to CIDOC CRM and the 323 unresolved identity links

The official SEM model gives class-level close matches:

- `sem:Event` to CIDOC CRM `E5 Event`
- `sem:Actor` to CIDOC CRM `E39 Actor`
- `sem:Place` to CIDOC CRM `E53 Place`

It does not publish exact property equivalences for `sem:hasActor`,
`sem:hasPlace`, or `sem:hasSubEvent`. We can use their domain and range to make
a scoped relation crosswalk to CIDOC CRM `P11`, `P7`, and event part relations.
This crosswalk can make relation context comparable. It cannot prove identity.

The local identity audit explains the largest problem:

- 323 candidate links are unresolved.
- 220 of them point to the same Wikidata item, `Q11866226`, which is a page
  about Finnish anti-aircraft units. Individual WarSampo units linked from that
  page are not automatically identical to the page item.
- The remaining candidates can use normalized relation context as evidence:
  unit hierarchy, conflict participation, event place, active dates, and unit
  type. Accept a QID only when this evidence identifies one existing Wikidata
  item. If no such item exists, keep the WarSampo identity unlinked.

Thus, the SEM-CIDOC CRM crosswalk is useful after the page-scope filter. It is
not a replacement for entity resolution.

## Public mapping evidence

- [EventKG mapping documentation](https://github.com/sgottsch/eventkg/blob/master/README.md#manual-configuration)
- [EventKG Wikidata sublocation map](https://github.com/sgottsch/eventkg/blob/0face5765ffc3e16a8746f9ed98877dc86de2bef/src/resource/meta_data/wikidata/properties_sublocations.tsv)
- [DBpedia `location`](https://dbpedia.org/ontology/location)
- [DBpedia `locationCountry`](https://dbpedia.org/ontology/locationCountry)
- [DBpedia `nextEvent`](https://dbpedia.org/ontology/nextEvent)
- [DBpedia `position`](https://dbpedia.org/ontology/position)
- [DBpedia `voice`](https://dbpedia.org/ontology/voice)
- [Wikidata `P276`](https://www.wikidata.org/wiki/Property:P276)
- [Wikidata `P156`](https://www.wikidata.org/wiki/Property:P156)
- [Wikidata `P413`](https://www.wikidata.org/wiki/Property:P413)
- [Wikidata `P1545`](https://www.wikidata.org/wiki/Property:P1545)
- [Wikidata `P725`](https://www.wikidata.org/wiki/Property:P725)
- [Wikidata `P990`](https://www.wikidata.org/wiki/Property:P990)
- [Simple Event Model specification](https://semanticweb.cs.vu.nl/2009/11/sem/)
- [CIDOC CRM 7.1.3](https://cidoc-crm.org/sites/default/files/Documents/cidoc_crm_version_7.1.3.html)

## Output

The machine-readable decision table is
`eventkg_wikidata_declared_mapping_audit/conflict_broader_resolutions.csv`.
The original source statements and predicates remain unchanged.
