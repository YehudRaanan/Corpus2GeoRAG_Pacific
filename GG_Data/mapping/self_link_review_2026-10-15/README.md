# Source self-link review and approved output exclusions

Date: 2026-10-15

## Decisions and verified scope

- **Three EventKG assertions are confirmed erroneous inputs and approved for exclusion from future assertion outputs.** The exact source-record keys and content guards are in [ASSERTION_EXCLUSIONS.csv](../ASSERTION_EXCLUSIONS.csv). Original source records remain preserved.
- **All 16 Wikidata-selected self-links were matched to their exact statement IDs in the saved Wikidata entity archive.** All already have the same QID as subject and main-statement target. Our relation mapping did not create these self-links.
- **Do not reject all self-links.** The official P17 documentation explicitly includes Germany → country → Germany. Three historical-country cases follow this convention; a fourth territorial case needs scope review.
- The 16 Wikidata rows have been reviewed and documented, but **no additional exclusion decision is activated for them in this change**. The user explicitly approved exclusion of the three EventKG examples and requested investigation of the 16 Wikidata cases.
- The existing CSV and draft graph have not been rewritten. The approved gate has been added to the shared mapping function in the existing assertion-building notebook. A dry run over the current 700,890 rows matches exactly three exclusions, leaving **700,887** retained rows. This is a verified filtering result, not a claim that a new graph has been generated.

## 1. The three approved exclusions

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
| 3 | 50th Guards Rifle Division, Q16625079 | P1365 replaces | Same entity is its own predecessor; source/import/identity review needed | Retain pending review |
| 4 | 162nd Fighter Aviation Regiment, Q21634743 | P1366 replaced by | Same entity is its own successor; source/import/identity review needed | Retain pending review |
| 5 | Kampfgeschwader 25, Q3192509 | P749 parent organization or unit | Strong input-error candidate: a unit is its own parent | Retain pending exclusion decision |
| 6 | Michiaki Kamada, Q3424805 | P40 child | Strong input-error candidate: a historical person is his own child | Retain pending exclusion decision |
| 7 | 16th Guards Fighter Aviation Regiment, Q4029011 | P1365 replaces | Same entity is its own predecessor | Retain pending review |
| 8 | 163rd Rifle Division, Q4029071 | P1365 replaces | Same entity is its own predecessor | Retain pending review |
| 9 | 39th Guards Rifle Division, Q4031132 | P1365 replaces | Same entity is its own predecessor | Retain pending review |
| 10 | 77th Guards Rifle Division, Q4032386 | P1365 replaces | Same entity is its own predecessor | Retain pending review |
| 11 | 77th Guards Rifle Division, Q4032386 | P1366 replaced by | Same entity is its own successor; distinct statement from row 10 | Retain pending review |
| 12 | Maxim Gorky Fortresses, Q4096918 | P1365 replaces | Same entity is its own predecessor; distinct fortifications/phases may need separation | Retain pending review |
| 13 | British occupation zone in Germany, Q55306 | P17 country | Territory points to itself as its country; review occupation-zone versus country scope | Retain pending review |
| 14 | Dutch Resistance Museum, Q828307 | P6379 has works in the collection | Review creator/collection-holder roles and the referenced photo-series record | Retain pending review |
| 15 | British Empire, Q8680 | P17 country | Historical-country self-reference convention; scope can still require separate review | Retain |
| 16 | Omaha-class cruiser, Q917282 | P176 manufacturer | Strong input-error candidate: ship class is its own manufacturer | Retain pending exclusion decision |

These are 16 statements about **15 entities**, because Q4032386 has both P1365 and P1366 self-statements. They are not duplicate rows.

### 2.1 Country self-links: four cases, different interpretations

The official [P17 documentation](https://www.wikidata.org/wiki/Property:P17#P1855) includes Germany → country → Germany as a property example. Therefore, equality of subject and object is not sufficient to reject P17.

The Soviet Union, Independent State of Croatia and British Empire rows are compatible with this historical-country convention. This does not establish all historical or geopolitical claims about these entities. The British occupation zone is a territorial case; its suitability as its own country remains unresolved here. No modern Germany replacement is guessed.

### 2.2 Succession: eight cases share an import clue

- Six P1365 statements and two P1366 statements point to the same item as their subject.
- All eight carry an `imported from Wikimedia project` reference to Russian Wikipedia (Q206855). Seven also contain a pinned Russian Wikipedia revision URL; one contains only the project pointer.
- None of the eight has statement qualifiers. Their exported form cannot distinguish predecessor and successor phases or date intervals.
- [P1365's documented meaning](https://www.wikidata.org/wiki/Property:P1365) distinguishes replacement from a sequence in which the predecessor and successor are identical. It points to P155 for that latter case. [P1366](https://www.wikidata.org/wiki/Property:P1366) describes an entity that replaces the subject in its role.

**Interpretation:** these are unsuitable as straightforward links between distinct predecessor/successor entities without further review. An import may have followed a link or redirect back to the same item; alternatively, one item may cover multiple historical formations or phases. These are hypotheses, not verified causes. The import pointer alone does not show the exact earlier Wikipedia field or establish a bot error.

**Next evidence:** inspect the pinned source revision, its predecessor/successor field and original link target, then Wikidata statement/item history. Do not automatically substitute P155, reverse endpoints, split an entity, or invent a new target.

### 2.3 Three strong value-error candidates

- **Michiaki Kamada → P40 child → Michiaki Kamada.** The exact saved main statement contains the same QID. There are no qualifiers or references. This fails the ordinary historical-person child role; the source gives no evidence for a correct child target. [P40 definition](https://www.wikidata.org/wiki/Property:P40).
- **Kampfgeschwader 25 → P749 parent organization or unit → Kampfgeschwader 25.** The exact saved main statement contains the same QID. There are no qualifiers or references. A parent-organization link to itself does not identify a superior unit. [P749 definition](https://www.wikidata.org/wiki/Property:P749).
- **Omaha-class cruiser → P176 manufacturer → Omaha-class cruiser.** The exact saved main statement contains the same QID. There are no qualifiers or references. The target is the class being manufactured, not a manufacturer. [P176 definition](https://www.wikidata.org/wiki/Property:P176).

Their target values are already present in the source snapshot. None requires a change in relation translation to explain the fault. They are documented for the next exclusion decision; the active ledger remains limited to the three user-approved EventKG records.

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

The existing [assertion notebook](../RELATION_MAPPING_ALL_ITEMS_v1.0.0.ipynb) loads this ledger and calls the policy inside `map_relation`, the shared function used by all three source readers. Exclusions are counted separately as `EventKG.excluded_reviewed_input`. They are not counted as mapped/written assertions.

**Version boundary:** this notebook still uses the legacy v1 relation mapping. This change implements the assertion exclusion gate only; it does not promote the notebook to a v2.1 exporter. The later v2.1 assertion/export builder must use the same source-oriented gate before applying the current mapping and before creating both directional views. Rebuilding mapping catalogs alone does not create filtered assertion data.

**Existing-artifact boundary:** the already-built 700,890-row CSV, original EDA and draft graph retain the three rows as historical audit evidence. Running a graph builder against that old CSV would still include them. The assertion output must be regenerated through the gate before a new graph is built. No new filtered graph or assertion CSV was generated in this review.

## 4. Verification and reproduction

```powershell
& 'Agent/.venv/Scripts/python.exe' 'GG_Data/mapping/test_assertion_exclusions.py'
& 'Agent/.venv/Scripts/python.exe' 'GG_Data/mapping/audit_self_link_inputs.py'
```

The regression check exercises the actual notebook mapping/writer cell and proves that the three approved records emit no rows. It also checks that unreviewed IDs and other sources are retained, and changed contents under an excluded ID stop with an error. The audit reads all 700,890 existing assertions and confirms exactly three ledger matches, then checks the raw EventKG records and all 16 Wikidata statements.

| Check | Result |
|---|---:|
| Current input assertions | 700,890 |
| Approved exclusions matched exactly once | 3 |
| Retained by a replay of this gate | 700,887 |
| Self-links in original input | 45 |
| Self-links retained by this gate | 42 |
| EventKG raw self-links checked / identical endpoints | 29 / 29 |
| Wikidata saved statement IDs checked / self-targets confirmed | 16 / 16 |
| New Wikidata exclusions activated | 0 |

All writes are inside `GG_Data`. No original source, existing assertion CSV, graph, geocoding result or Agent contract request is changed. Counts refer to the saved local snapshot; live Wikidata statement persistence and earlier source-edit causes are not established by this audit.

## Files

- `source_evidence.json`: complete approved rejected rows, raw N-Quad evidence for all 29 EventKG self-links, and full saved statements/references for all 16 Wikidata self-links.
- `wikidata_review.csv`: one review row for each of the 16 Wikidata statements, with revision-pinned entity links and source pointers.
- `summary.json`: reconciled counts and explicit generation/verification boundaries.
- `../ASSERTION_EXCLUSIONS.csv`: the three approved source-record exclusions.

The earlier [EDA](../assertion_eda_v2_1_2026-10-15/README.md) remains the unfiltered baseline.
