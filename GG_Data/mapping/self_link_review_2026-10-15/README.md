# Source self-link review and approved output exclusions

Date: 2026-10-15

## Status verified on 2026-10-18

A read-only replay of all 700,890 saved assertions matched each of the 14 approved
exclusions exactly once. It retained 700,876 assertions, including 31 self-links
and the separate 77th Division successor statement to `Q16161496`. Every input
source/predicate key had exactly one v2.1 mapping. The three exclusion tests, six
mapping tests, and succession field parser check passed.

This verifies the existing gate and mapping coverage. It does not add exclusions,
repeat the historical source investigation, or resolve the pending occupation-zone,
museum, or historical-phase identity questions below. The current CSV and graph
still contain the excluded records. The next export must apply the gate before
v2.1 translation and reverse views, then rebuild the graph from the new assertions.
See the [mapping status and export sequence](../RELATION_MAPPING_SANITY_CHECK_2026-10-15.md#status-verified-on-2026-10-18).

## Decisions and verified scope

- **Three EventKG assertions are confirmed erroneous inputs and approved for exclusion from future assertion outputs.** The exact source-record keys and content guards are in [ASSERTION_EXCLUSIONS.csv](../ASSERTION_EXCLUSIONS.csv). Original source records remain preserved.
- **All 16 Wikidata-selected self-links were matched to their exact statement IDs in the saved Wikidata entity archive.** All already have the same QID as subject and main-statement target. Our relation mapping did not create these self-links.
- **Do not reject all self-links.** The official P17 documentation explicitly includes Germany → country → Germany. Three historical-country cases follow this convention; a fourth territorial case needs scope review.
- **Eleven Wikidata assertions are approved for exclusion:** Kampfgeschwader 25 as its own parent unit, Michiaki Kamada as his own child, Omaha-class cruiser as its own manufacturer, and eight unqualified succession self-links. The active ledger therefore has **14 exclusions: three EventKG and eleven Wikidata**. Source history for all eight succession cases is documented below; their missing historical phase relationships have not been reconstructed.
- The existing CSV and draft graph have not been rewritten. The approved gate has been added to the shared mapping function in the existing assertion-building notebook. A dry run over the current 700,890 rows matches exactly 14 exclusions, leaving **700,876** retained rows. This is a verified filtering result, not a claim that a new graph has been generated.

## 1. The three approved EventKG exclusions

| Person | Original relation | Original EventKG resource on both ends | Source relation record | Decision |
|---|---|---|---|---|
| Omar Bradley, Q207955 | DBpedia `honours` | `entity_5706258` | `relation_3670253` | Exclude: the honour target is the person himself |
| Bill Stone, Q2607384 | DBpedia `militaryUnit` | `entity_13327440` | `relation_34200996` | Exclude: the unit target is the person himself |
| Alastair Mars, Q4708746 | DBpedia `occupation` | `entity_6940957` | `relation_10823606` | Exclude: the occupation target is the person himself |

All three specify the graph `https://eventkg.l3s.uni-hannover.de/graph/dbpedia_en`. Original subject/object N-Quads, decompressed line numbers, original exported rows, and record IDs are saved in [source_evidence.json](source_evidence.json).

### Where the fault is already visible

For Alastair Mars, the saved input literally contains these endpoints:

```text
relation_10823606 rdf:subject entity_6940957
relation_10823606 rdf:object  entity_6940957
relation_10823606 sem:roleType http://dbpedia.org/ontology/occupation
```

The same applies to the other two records. The source filter preserves the selected N-Quad group without rewriting its endpoints (`scripts/filter_eventkg_related.py`, `filter_content` / `emit`). The mapping notebook reads `rdf:subject` and `rdf:object` independently, resolves their explicit source identity links, and then maps the relation code. The identical endpoints are present before those steps.

**Established boundary:** these are faulty values in the saved EventKG input. It is not established whether DBpedia already had the faulty target or whether EventKG's earlier processing introduced it. Current DBpedia retrieval failed with HTTP 502 during the preceding trace. No replacement target is inferred.

The wider check matched all **29 EventKG self-links** to their raw relation records; all 29 already have identical EventKG endpoint resources. This does not classify all 29 as errors and does not authorize their blanket removal.

## 2. All 16 Wikidata-selected self-links

Each row below has the same QID on both ends. The full statement, rank, references, entity revision, archive line, and original export row are retained in `source_evidence.json`. The flat review table is [wikidata_review.csv](wikidata_review.csv).

| # | Subject / target | Property | Assessment | Output decision in this change |
|---|---|---|---|---|
| 1 | Soviet Union, Q15180 | P17 country | Country self-reference convention; self-link alone is not an error | Retain |
| 2 | Independent State of Croatia, Q153128 | P17 country | Historical-country self-reference convention; does not assert modern political recognition | Retain |
| 3 | 50th Guards Rifle Division, Q16625079 | P1365 replaces | Predecessor name resolves back to subject identity | Exclude, approved |
| 4 | 162nd Fighter Aviation Regiment, Q21634743 | P1366 replaced by | Successor name resolves back to subject identity | Exclude, approved |
| 5 | Kampfgeschwader 25, Q3192509 | P749 parent organization or unit | Confirmed input error: a unit is its own parent | Exclude, approved |
| 6 | Michiaki Kamada, Q3424805 | P40 child | Confirmed input error: a historical person is his own child | Exclude, approved |
| 7 | 16th Guards Fighter Aviation Regiment, Q4029011 | P1365 replaces | Same entity is its own predecessor | Exclude, approved |
| 8 | 163rd Rifle Division, Q4029071 | P1365 replaces | Same entity is its own predecessor; historical redirect recovered | Exclude, approved |
| 9 | 39th Guards Rifle Division, Q4031132 | P1365 replaces | Same entity is its own predecessor; source field contains a historical chain | Exclude, approved |
| 10 | 77th Guards Rifle Division, Q4032386 | P1365 replaces | Same entity is its own predecessor; historical redirect recovered | Exclude, approved |
| 11 | 77th Guards Rifle Division, Q4032386 | P1366 replaced by | Same entity is its own successor; separate distinct-QID successor is retained | Exclude, approved |
| 12 | Maxim Gorky Fortresses, Q4096918 | P1365 replaces | Same entity is its own predecessor; distinct fortifications/phases may need separation | Exclude, approved |
| 13 | British occupation zone in Germany, Q55306 | P17 country | Territory points to itself as its country; review occupation-zone versus country scope | Retain pending review |
| 14 | Dutch Resistance Museum, Q828307 | P6379 has works in the collection | Review creator/collection-holder roles and the referenced photo-series record | Retain pending review |
| 15 | British Empire, Q8680 | P17 country | Historical-country self-reference convention; scope can still require separate review | Retain |
| 16 | Omaha-class cruiser, Q917282 | P176 manufacturer | Confirmed input error: ship class is its own manufacturer | Exclude, approved |

These are 16 statements about **15 entities**, because Q4032386 has both P1365 and P1366 self-statements. They are not duplicate rows.

### 2.1 Country self-links: four cases, different interpretations

The official [P17 documentation](https://www.wikidata.org/wiki/Property:P17#P1855) includes Germany → country → Germany as a property example. Therefore, equality of subject and object is not sufficient to reject P17.

The Soviet Union, Independent State of Croatia and British Empire rows are compatible with this historical-country convention. This does not establish all historical or geopolitical claims about these entities. The British occupation zone is a territorial case; its suitability as its own country remains unresolved here. No modern Germany replacement is guessed.

### 2.2 Succession: eight cases share an import clue

- Six P1365 statements and two P1366 statements point to the same item as their subject.
- All eight carry an `imported from Wikimedia project` reference to Russian Wikipedia (Q206855). Seven also contain a pinned Russian Wikipedia revision URL; one contains only the project pointer.
- None of the eight has statement qualifiers. Their exported form cannot distinguish predecessor and successor phases or date intervals.
- [P1365's documented meaning](https://www.wikidata.org/wiki/Property:P1365) distinguishes replacement from a sequence in which the predecessor and successor are identical. It points to P155 for that latter case. [P1366](https://www.wikidata.org/wiki/Property:P1366) describes an entity that replaces the subject in its role.

**Source investigation after approval:** five statements now have a demonstrable source-field → link → redirect → same current QID path. The original fields name a predecessor or successor differently from the subject, but the linked article resolves to the same graph identity. Four of those target pages already redirected directly back to the source article at the referenced source-revision time. The fifth has an older redirect to the 16th Guards name and a current resolution to the 689th Guards article under the same QID. Details and evidence limits are in [SUCCESSION_TRACE.md](SUCCESSION_TRACE.md).

The other three statements now have exact Wikidata creation revisions and contemporaneous Russian article/redirect evidence. The 163rd Division's motorized predecessor name redirects to the rifle division. The 77th Division's predecessor and one motor-rifle successor stage also redirect to its own article. The 163rd reference still has no revision pointer, and the exact citation revision shared by the two 77th statements remains unavailable. The contemporaneous pages are alternative evidence, not the recovered missing citation.

**Interpretation:** a Wikipedia article can cover a unit through several names or organizational phases. Resolving article links to one QID can remove the distinction expressed by the original predecessor/successor field. The resulting unqualified self-link cannot represent that transition between phases. Five cases use their cited revision; three use creation edits and contemporaneous source history. The original importer implementation is not established. All eight exact records are now excluded from future output before mapping and reverse views. No replacement endpoint or historical phase entity is invented.

**Preserved assertion:** the 77th Division also has a separate P1366 successor statement to Q16161496. The full CSV replay verifies that this statement occurs once and is retained. Suppressing its self-target statement does not remove this distinct successor.

**Remaining historical repair:** decide whether the data should represent a continuing unit with dated names or separate predecessor/successor entities. Do not automatically substitute P155, reverse endpoints, split an entity, or invent a new target. Relation-code translation cannot restore missing entity-phase distinctions.

### 2.3 Three approved Wikidata value-error exclusions

- **Michiaki Kamada → P40 child → Michiaki Kamada.** The exact saved main statement contains the same QID. There are no qualifiers or references. This fails the ordinary historical-person child role; the source gives no evidence for a correct child target. [P40 definition](https://www.wikidata.org/wiki/Property:P40).
- **Kampfgeschwader 25 → P749 parent organization or unit → Kampfgeschwader 25.** The exact saved main statement contains the same QID. There are no qualifiers or references. A parent-organization link to itself does not identify a superior unit. [P749 definition](https://www.wikidata.org/wiki/Property:P749).
- **Omaha-class cruiser → P176 manufacturer → Omaha-class cruiser.** The exact saved main statement contains the same QID. There are no qualifiers or references. The target is the class being manufactured, not a manufacturer. [P176 definition](https://www.wikidata.org/wiki/Property:P176).

Their target values are already present in the source snapshot. None requires a change in relation translation to explain the fault. Following user approval, their exact source statement IDs and original endpoint guards have been added to the active ledger. Including the eight succession cases and three EventKG cases, there are now 14 approved exclusions in total. No corrected target is invented.

### 2.4 Museum: one case needs its reference inspected

P6379 describes a collection containing works of the subject person or organization. An organization can create works and hold them, so a self-link alone does not prove impossibility. See the [official definition and usage guidance](https://www.wikidata.org/wiki/Property:P6379).

The saved museum statement points to itself and cites a [collection record](https://collectie.verzetsmuseum.org/ais6/Details/collect/5552). Its saved reference title concerns a series of 24 photographs of anti-German / pro-Orange drawings and slogans. That is a useful clue that creator, depicted subject and collection-holder roles may have been mixed. The original collection page was not verified in this audit; the title is evidence saved inside the Wikidata reference, not proof of the cause.

### 2.5 Rank, references and qualifiers

- All 16 are present in the exact saved statements and all are non-deprecated: **15 normal rank, one preferred rank** (British Empire P17).
- **Nine** contain references: the eight succession statements and the museum statement. The other seven have no references in this snapshot.
- **None** has qualifiers. Missing qualifiers cannot be used to repair or disambiguate these records from the final CSV.
- A normal/preferred rank and a reference pointer are not independent proof of assertion quality.

## 3. Output policy and integration

The policy is implemented in [assertion_exclusions.py](../assertion_exclusions.py):

1. Look up the exact `(source, source_record_id)` in the approved ledger.
2. Require exact original predicate, original subject QID and original object QID to match the reviewed values.
3. On a match, omit the assertion from newly written output. Apply this before relation translation, aggregation or reverse-view generation, so neither direction of an excluded assertion becomes Agent evidence.
4. If the same source record ID now has corrected/different contents, stop for review. Do not silently suppress the changed record under an old exclusion decision.
5. Unlisted records, including other self-links and other assertions about the same people, remain unaffected.

The existing [assertion notebook](../RELATION_MAPPING_ALL_ITEMS_v1.0.0.ipynb) loads this ledger and calls the policy inside `map_relation`, the shared function used by all three source readers. Exclusions are counted separately as `<source>.excluded_reviewed_input`, currently three for EventKG and eleven for Wikidata. They are not counted as mapped/written assertions.

**Version boundary:** this notebook still uses the legacy v1 relation mapping. This change implements the assertion exclusion gate only; it does not promote the notebook to a v2.1 exporter. The later v2.1 assertion/export builder must use the same source-oriented gate before applying the current mapping and before creating both directional views. Rebuilding mapping catalogs alone does not create filtered assertion data.

**Existing-artifact boundary:** the already-built 700,890-row CSV, original EDA and draft graph retain the 14 rows as historical audit evidence. Running a graph builder against that old CSV would still include them. The assertion output must be regenerated through the gate before a new graph is built. No new filtered graph or assertion CSV was generated in this review.

## 4. Verification and reproduction

```powershell
& 'Agent/.venv/Scripts/python.exe' 'GG_Data/mapping/test_assertion_exclusions.py'
& 'Agent/.venv/Scripts/python.exe' 'GG_Data/mapping/audit_self_link_inputs.py'
```

The regression check exercises the actual notebook mapping/writer cell and proves that all 14 approved records emit no rows across both source readers. It also checks that unreviewed IDs and other sources have no exclusion match, changed contents under an excluded ID stop with an error, and the separate distinct-QID successor remains available. The audit reads all 700,890 existing assertions and confirms exactly 14 ledger matches, then checks the raw EventKG records, all 16 Wikidata statements and the retained successor record.

| Check | Result |
|---|---:|
| Current input assertions | 700,890 |
| Approved exclusions matched exactly once | 14 |
| Retained by a replay of this gate | 700,876 |
| Self-links in original input | 45 |
| Self-links retained by this gate | 31 |
| EventKG raw self-links checked / identical endpoints | 29 / 29 |
| Wikidata saved statement IDs checked / self-targets confirmed | 16 / 16 |
| Approved Wikidata exclusions activated | 11 |
| Of these: succession self-links excluded | 8 |
| Separate 77th Division distinct-QID successor retained | 1 |

All writes are inside `GG_Data`. No original source, existing assertion CSV, graph, geocoding result or Agent contract request is changed. Counts refer to the saved local snapshot. Creation edits for the three additional succession cases are documented; live statement persistence and the original importer implementation are not established by this audit.

## Files

- `source_evidence.json`: complete approved rejected rows, raw N-Quad evidence for all 29 EventKG self-links, full saved statements/references for all 16 Wikidata self-links, and the retained distinct successor assertion.
- `wikidata_review.csv`: one review row for each of the 16 Wikidata statements, with revision-pinned entity links and source pointers.
- `summary.json`: reconciled counts and explicit generation/verification boundaries.
- `../ASSERTION_EXCLUSIONS.csv`: the 14 approved source-record exclusions.
- `SUCCESSION_TRACE.md`: case-by-case source investigation for the eight succession self-links.
- `succession_entities.json`: selected identity, sitelink and succession fields from the seven saved source entities.
- `succession_source_trace.json`: pinned source fields, line numbers, retrieval URLs, current redirect/QID resolution and the missing-revision response.
- `succession_historical_redirects.json`: target-page revisions at or before the referenced source time; response content is limited to the first 600 characters, explicitly recorded as `content_start`.
- `succession_remaining_three_research.json`: creation-edit history, exact succession claim states, contemporaneous article excerpts and historical redirects for the other three cases, with reproducible request URLs and explicit excerpt scopes.
- `../trace_succession_sources.py`: repeatable retrieval of the source fields and current target resolution. Historical redirect queries can be repeated with the exact request URLs in their evidence file.

The earlier [EDA](../assertion_eda_v2_1_2026-10-15/README.md) remains the unfiltered baseline.
