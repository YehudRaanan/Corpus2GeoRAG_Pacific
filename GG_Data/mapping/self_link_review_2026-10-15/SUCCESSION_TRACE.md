# Why eight succession assertions point back to their own subject

Date: 2026-10-15. Scope: eight saved Wikidata assertions, seven entities. All eight self-targets are now excluded by exact source-record key from future assertion output. Raw assertions and source fields remain preserved. No new entity or replacement endpoint is invented.

## Result

**Five of the eight assertions have a verified source-field and present-day redirect path that resolves a differently named predecessor/successor to the subject's own QID.** Four have direct historical redirects back to the source article at the referenced revision time. The fifth has historical redirect evidence to an earlier unit name and current resolution to the subject QID. This is evidence of a lost distinction between names/phases within a continuing article identity; it does not establish the exact Wikidata bot/edit that created each claim.

**The other three have now been traced through Wikidata creation revisions and contemporaneous Russian Wikipedia history.** The 163rd Division's predecessor was a motorized-division name that already redirected to the rifle-division article. The 77th Division's predecessor (173rd Division, second formation) and one successor stage (77th Motor Rifle Division) also already redirected to its own article. The exact missing citation revision for the 77th Division is still unavailable; contemporaneous pages are explicitly treated as alternative evidence, not as that missing revision.

**Fix applied:** the five initially traced records and these three additional records are all added to the existing exact-record exclusion ledger. This removes eight invalid unqualified self-links before forward or reverse views can be generated. Together with six earlier exclusions, the gate excludes **14** rows and retains **700,876** of the original 700,890. This is an output suppression fix; the missing historical phase relationships have not been reconstructed. The existing CSV and graph remain the unfiltered baseline.

This is an assertion/entity representation problem. The deterministic translation of `P1365` or `P1366` preserves the faulty self-target already in the saved source. Changing the relation name or generating its reverse cannot recover the missing predecessor/successor identity.

## What was checked

1. Match all eight exported rows to their exact saved Wikidata statement IDs. All already point to their own QID; all are normal rank, unqualified, and reference Russian Wikipedia.
2. Read each pinned Russian Wikipedia revision through its official API. Seven statements provide six distinct revision IDs; five revisions are accessible and one is reported missing. Together the five accessible revisions cover five statements. The two 77th Division statements share the missing revision.
3. Extract only the predecessor (`предшественник`) and successor (`преемник`) fields with their original link targets and source line numbers. The 163rd Division has no pinned revision; its current page is separate context evidence.
4. Resolve linked titles through the current official Wikipedia redirects and `wikibase_item` page property. This proves the current article/QID path, not the historical QID assignment.
5. Query the predecessor/successor target page's revision at or before the source-revision timestamp. Preserve the exact API request, revision ID, timestamp and content prefix. This distinguishes historical redirect evidence from current resolution.
6. For the three initially unresolved statements, find the Wikidata creation edits, match their exact statement IDs and self-targets, then inspect Russian Wikipedia at or before those edit times and the historical target redirects. These pages are contemporaneous context, not a recovered original import revision.
7. Replay all 700,890 saved assertions through the gate. Check that each of the 14 exclusions matches once and that the separate 77th Division → P1366 → Q16161496 successor assertion is retained.

The audit examines Wikipedia and Wikidata as the actual source systems used here. It does not independently establish military history or decide whether historical formations require separate graph entities.

## All eight assertions

| Saved subject / QID | Saved property | Source field and original target | Verified result | Limit / disposition |
|---|---|---|---|---|
| 50th Guards Rifle Division / Q16625079 | P1365 replaces | Predecessor = **124th Rifle Division, 2nd formation** | Source revision 134503510, line 11, links the 124th title. Target revision 64687574 already redirects to the 50th article. Current target resolution gives Q16625079. | Exclude self-target. Historical direct return path established; original import edit not traced. |
| 162nd Fighter Aviation Regiment / Q21634743 | P1366 replaced by | Successor = **162nd Fighter Aviation Regiment PVO** | Source revision 138985762, line 11, links the PVO title. Target revision 74659281 already redirects to the 162nd article. Current resolution gives Q21634743. | Exclude self-target. Whether the stages should be separate entities is not decided. |
| 16th Guards Fighter Aviation Regiment / Q4029011 | P1365 replaces | Predecessor = **55th Fighter Aviation Regiment** | Source revision 128844657, line 12, links the 55th title. Historical target revision 44327647 redirects to the **16th Guards** title. Present resolution reaches the **689th Guards** article, Q4029011. | Exclude self-target. Complete move history between 16th and 689th is not traced. |
| 163rd Rifle Division / Q4029071 | P1365 replaces | Contemporaneous predecessor = **163rd Motorized Division**, linked | Creation revision 466095806 contains the exact self-statement. Russian revision 83854655, line 9, links the motorized name; target revision 19570814 already redirects to the rifle division. | Exclude self-target. Original reference has no revision URL; contemporaneous source is alternative evidence. |
| 39th Guards Rifle Division / Q4031132 | P1365 replaces | Predecessor chain = **5th Airborne Corps (1941) → 39th Guards Rifle Division (1942–1957)** | Source revision 134502410, line 13; rifle-division target revision 33253658 already redirects to the motor-rifle article. Current resolution gives Q4031132; the corps resolves to Q4031595. | Exclude self-target. Do not replace it with an arbitrary member of the chain. |
| 77th Guards Rifle Division / Q4032386 | P1365 replaces | Contemporaneous predecessor = **173rd Rifle Division, second formation** | Exact self-statement created in revision 1802941904. Russian revision 126813872, line 13, links the 173rd title; historical target revision 64807950 redirects to the 77th article. | Exclude self-target. Cited revision 122348199 remains unavailable; alternative contemporaneous evidence is preserved. |
| 77th Guards Rifle Division / Q4032386 | P1366 replaced by | Contemporaneous successor chain includes **77th Guards Motor Rifle Division** | Exact self-statement created in revision 1802941954. Russian revision 126813872, line 14, includes the motor-rifle title; historical target revision 104417582 redirects to the subject article. | Exclude self-target. Preserve separate P1366 assertion to Q16161496. Cited revision remains unavailable. |
| Maxim Gorky Fortresses / Q4096918 | P1365 replaces | Predecessor = **Separate Battery No. 8, 6th Fortress Artillery Regiment, Black Sea Coastal Defence**, under construction | Source revision 138040864, line 10; target revision 127080909 already redirects to **Coastal Battery No. 35**. Current resolution gives Q4096918. | Exclude self-target. Broader English identity versus narrower Russian title still needs scope review before any entity split. |

All eight output actions are now `EXCLUDE_APPROVED_INPUT_ERROR` in the row-level review table. This is a record-specific quality decision. It is not a new deterministic mapping between relation codes and not a claim that Wikidata declares a formal irreflexivity constraint for these properties.

## The other three: recovered historical evidence

### 163rd Division: one statement

- [Wikidata creation revision 466095806](https://www.wikidata.org/w/index.php?title=Q4029071&oldid=466095806), 2017-03-14 03:14:53 UTC, contains the exact saved statement ID `Q4029071$1d576372-4433-3e7e-e976-818a285e47fb` and the same self-target. Its edit comment records creation of P1365 → Q4029071.
- The latest available [Russian article revision before that edit, 83854655](https://ru.wikipedia.org/w/index.php?oldid=83854655), 2017-02-23, has a linked predecessor **163rd Motorized Division** on line 9. Unlike the later current-page context, this older field still has a wiki link.
- That target had [redirected back to the rifle division since revision 19570814](https://ru.wikipedia.org/w/index.php?oldid=19570814), dated 2009-11-02.
- The absence of an original import revision remains a provenance gap. However, there is now a concrete contemporaneous redirect path consistent with the observed creation edit. The self-target is excluded; a new motorized-phase entity is not inferred.

### 77th Division: two statements, plus a distinct successor to preserve

- The exact P1365 self-statement is present in its [creation revision 1802941904](https://www.wikidata.org/w/index.php?title=Q4032386&oldid=1802941904), 2023-01-04 17:19:48 UTC. The exact P1366 self-statement is present in [creation revision 1802941954](https://www.wikidata.org/w/index.php?title=Q4032386&oldid=1802941954), five seconds later. Both carry the same unavailable citation revision URL already found in the saved archive.
- The latest available [Russian source page at those times, revision 126813872](https://ru.wikipedia.org/w/index.php?oldid=126813872), names **173rd Rifle Division, second formation** as predecessor and lists a sequence of successor stages. The [173rd target revision 64807950](https://ru.wikipedia.org/w/index.php?oldid=64807950) already redirects to the 77th article. The [77th Motor Rifle target revision 104417582](https://ru.wikipedia.org/w/index.php?oldid=104417582) also already redirects to it.
- The successor field is a chain, not a single entity. Its coastal-defence stage redirects to the marine-brigade article, while its motor-rifle stage redirects to the original rifle division. It is therefore incorrect to treat every link in the field as the same target.
- A further creation edit, revision **1802941961**, adds P1366 → **Q16161496**, a distinct marine-brigade identity. The saved archive also contains that separate non-self statement: `Q4032386$59d1f104-45e5-53bc-90f2-e254f0f4873c`. The full replay verifies that it is present exactly once in the current assertion CSV and is retained. This is an existing assertion; the fix does not invent or duplicate it. Its presence is not proof that every transition in the chain has been modeled completely.
- The exact original revision 122348199 is still not recovered. These contemporaneous revisions establish a compatible source structure and historical redirects, not a byte-for-byte reconstruction of that missing citation or the importer code.

## Two examples in detail

### 50th Guards: a predecessor name becomes the subject identity

The [referenced source revision](https://ru.wikipedia.org/w/index.php?oldid=134503510) has a predecessor field linked to the 124th Rifle Division, 2nd formation. At that source time, the [target page revision](https://ru.wikipedia.org/w/index.php?oldid=64687574) already redirected to the 50th Guards Rifle Division article. The current resolved article's QID is Q16625079, also the saved statement's subject.

The source field distinguishes **124th → 50th**. At the article/QID level, both ends can become **Q16625079 → Q16625079**. This is a demonstrated collapse path. The original Wikidata creation edit has not been inspected, so the exact implementation that followed it is not proven.

It would be wrong to invent a separate QID or to use the first different entity with a similar name. It would also be wrong to assume that every 124th Division formation is the same unit. The original field explicitly says **2nd formation**.

### 39th Guards: one field contains a historical chain

The [referenced revision](https://ru.wikipedia.org/w/index.php?oldid=134502410) describes a motor-rifle division. Its predecessor field contains two earlier stages: a corps in 1941, followed by a rifle division in 1942–1957. The rifle-division link already [redirected to the motor-rifle article](https://ru.wikipedia.org/w/index.php?oldid=33253658).

The saved Wikidata English label is **39th Guards Rifle Division**, while both saved sitelinks identify **39th Guards Motor Rifle Division**. Therefore a person reading only the English label cannot see which period or unit form a relation concerns. A relation to Q4031132 alone does not distinguish these stages. The field's corps link resolves to another QID, but this does not prove it is the immediate predecessor intended by the self-statement.

## Wider failure patterns found

- **Article identity is not automatically a historical phase identity.** An article can hold several names and transformations. A graph that stores only the article's QID can lose the distinction required by succession relations.
- **A redirect is a navigation/identity signal, not proof that a predecessor transition should become an unqualified self-relation.** The relation still needs the unit phase or continuing-unit interpretation.
- **One source field can encode several transitions.** The 39th Division field contains a dated chain, not a single atomic relation. Reducing it to one target discards structure.
- **Names can describe different periods from the linked article title.** Both the 16th/689th and 39th rifle/motor-rifle cases show this in the saved entity data. A label mismatch is an audit signal, not automatic evidence that a merge was incorrect.
- **Provenance can be insufficient for replay.** A project-only reference cannot reproduce the imported source revision. A pinned revision can also become unavailable. Both occur in this group.
- **Unqualified self-targets have no recoverable transition detail.** None of these eight statements has qualifiers. Dates and intermediate designations visible in the source cannot be recovered from their endpoints alone.

These findings describe this eight-statement group. They are not a measured prevalence across every succession assertion in the corpus.

## Conclusion and next decision

All eight self-targets now have source evidence sufficient for the same output-quality decision: exclude these unqualified self-succession assertions. For five, the evidence uses the referenced source revision. For three, it uses exact Wikidata creation revisions and contemporaneous Wikipedia source/redirect history. The exact missing citation and original importer implementation remain evidence limits.

Restoring historical transitions is a separate remaining task. Start with **one real example**, such as 124th Division, 2nd formation → 50th Guards. Decide from historical identity evidence whether to represent dated names/phases of a continuing unit or separate predecessor/successor entities. Keep the original source statement and source field. Do not create an identity from relation labels alone.

The correction uses eight exact source-record exclusions, with predicate and original-endpoint content guards. It does not reject all self-links or all relations about these units. It does not split entities, change relation mapping or infer replacement targets. The gate runs before either directional view is generated.

## Evidence and reproduction

- [source_evidence.json](source_evidence.json): original eight assertions and complete saved Wikidata statements, among the full self-link audit.
- [succession_entities.json](succession_entities.json): saved entity labels, sitelinks, aliases, dates/types and succession claims for all seven entities.
- [succession_source_trace.json](succession_source_trace.json): five accessible pinned revisions, current-only context for the unpinned case, the missing revision response, original field strings and current redirect/QID API response. Revision-query `title` is the page title returned at retrieval; it does not by itself prove that title was used at the revision timestamp.
- [succession_historical_redirects.json](succession_historical_redirects.json): five target revisions at or before the source time. `content_start` and the response content string are capped at 600 characters; these are excerpts, not full article snapshots. The redirect statements fit inside those excerpts.
- [succession_remaining_three_research.json](succession_remaining_three_research.json): public edit-history metadata, exact statement-creation states, contemporaneous source excerpts, historical redirects and current target/QID resolution for the three additional cases. Each query records its full request URL. Wikidata content is reduced to entity ID and P1365/P1366 claims; contemporaneous article content is limited to the first 35 lines, as stated in the evidence metadata.
- [trace_succession_sources.py](../trace_succession_sources.py): repeatable source-field/current-resolution retrieval using `requests`, already installed in the project environment. Does not edit source data or mapping rules. An inaccessible source is saved as an error, not replaced with a guessed field.

```powershell
& 'Agent/.venv/Scripts/python.exe' 'GG_Data/mapping/test_trace_succession_sources.py'
& 'Agent/.venv/Scripts/python.exe' 'GG_Data/mapping/trace_succession_sources.py'
```

The local parser check verifies that indentation is accepted and an empty predecessor does not absorb the following successor field. The historical checks are reproducible using the exact `request_url` values in their evidence file. API responses and current redirect/QID assignments can change after the retrieval date. Saved evidence is the basis for this report.
