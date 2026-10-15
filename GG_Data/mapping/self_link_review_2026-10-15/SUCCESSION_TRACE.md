# Why eight succession assertions point back to their own subject

Date: 2026-10-15. Scope: eight saved Wikidata assertions, seven entities. All raw assertions remain preserved. No new exclusion or endpoint correction is made for this group.

## Result

**Five of the eight assertions have a verified source-field and present-day redirect path that resolves a differently named predecessor/successor to the subject's own QID.** Four have direct historical redirects back to the source article at the referenced revision time. The fifth has historical redirect evidence to an earlier unit name and current resolution to the subject QID. This is evidence of a lost distinction between names/phases within a continuing article identity; it does not establish the exact Wikidata bot/edit that created each claim.

The remaining three assertions lack enough historical source evidence. One has no pinned source revision. Two share a revision that the API reports missing. They remain unresolved, rather than being treated as correct.

This is an assertion/entity representation problem. The deterministic translation of `P1365` or `P1366` preserves the faulty self-target already in the saved source. Changing the relation name or generating its reverse cannot recover the missing predecessor/successor identity.

## What was checked

1. Match all eight exported rows to their exact saved Wikidata statement IDs. All already point to their own QID; all are normal rank, unqualified, and reference Russian Wikipedia.
2. Read each pinned Russian Wikipedia revision through its official API. Seven statements provide six distinct revision IDs; five revisions are accessible and one is reported missing. Together the five accessible revisions cover five statements. The two 77th Division statements share the missing revision.
3. Extract only the predecessor (`предшественник`) and successor (`преемник`) fields with their original link targets and source line numbers. The 163rd Division has no pinned revision; its current page is separate context evidence.
4. Resolve linked titles through the current official Wikipedia redirects and `wikibase_item` page property. This proves the current article/QID path, not the historical QID assignment.
5. Query the predecessor/successor target page's revision at or before the source-revision timestamp. Preserve the exact API request, revision ID, timestamp and content prefix. This distinguishes historical redirect evidence from current resolution.

The audit examines Wikipedia and Wikidata as the actual source systems used here. It does not independently establish military history or decide whether historical formations require separate graph entities.

## All eight assertions

| Saved subject / QID | Saved property | Source field and original target | Verified result | Limit / disposition |
|---|---|---|---|---|
| 50th Guards Rifle Division / Q16625079 | P1365 replaces | Predecessor = **124th Rifle Division, 2nd formation** | Source revision 134503510, line 11, links the 124th title. Target revision 64687574 already redirects to the 50th article. Current target resolution gives Q16625079. | Historical direct return path established. Original import edit not traced. Retain pending representation decision. |
| 162nd Fighter Aviation Regiment / Q21634743 | P1366 replaced by | Successor = **162nd Fighter Aviation Regiment PVO** | Source revision 138985762, line 11, links the PVO title. Target revision 74659281 already redirects to the 162nd article. Current resolution gives Q21634743. | A distinct name/role is lost under the same identity. Whether this should be a separate unit is not decided. |
| 16th Guards Fighter Aviation Regiment / Q4029011 | P1365 replaces | Predecessor = **55th Fighter Aviation Regiment** | Source revision 128844657, line 12, links the 55th title. Historical target revision 44327647 redirects to the **16th Guards** title. The present target resolves to the **689th Guards** article with Q4029011. | Historical redirect to the earlier name verified; complete move/redirect history between 16th and 689th not traced. The saved English label says 16th while its saved English and Russian sitelinks say 689th. |
| 163rd Rifle Division / Q4029071 | P1365 replaces | Current predecessor text = **163rd Motorized Division**, without a wiki link | The saved reference identifies Russian Wikipedia but has no revision URL. Current revision 155396632, line 10, names a different phase in plain text. | Current context does not prove the imported field, its target resolution, or the cause of the self-link. Unresolved. |
| 39th Guards Rifle Division / Q4031132 | P1365 replaces | Predecessor field = **5th Airborne Corps (1941) → 39th Guards Rifle Division (1942–1957)** | Source revision 134502410, line 13. The rifle-division target's revision 33253658 already redirects to the source **39th Guards Motor Rifle Division** article. Current resolution gives Q4031132. The other chain target resolves to Q4031595. | One field contains multiple historical stages. Selecting any one link without retaining the stage/chain can change meaning. No automatic substitution with the corps is justified. |
| 77th Guards Rifle Division / Q4032386 | P1365 replaces | Not recovered | Referenced revision 122348199 returns `query.badrevids[122348199].missing`. | No claim about the exact original predecessor field or import cause. Unresolved. |
| 77th Guards Rifle Division / Q4032386 | P1366 replaced by | Not recovered | Same missing source revision as the preceding row; a separate saved statement. | No claim about the original successor field. This is not a duplicate of P1365. Unresolved. |
| Maxim Gorky Fortresses / Q4096918 | P1365 replaces | Predecessor = **Separate Battery No. 8, 6th Fortress Artillery Regiment, Black Sea Coastal Defence**, marked under construction | Source revision 138040864, line 10. Target revision 127080909 already redirects to **Coastal Battery No. 35**. Current resolution gives Q4096918. | Historical direct return path established. Saved English identity is broader in wording than the Russian battery title; identity scope needs separate review before correction. |

All eight output actions remain `RETAIN_NO_APPROVED_EXCLUSION` in the row-level review table. This preserves the current approval boundary; it is not a quality acceptance of these assertions.

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

For the five traced cases, the source article structure and redirect resolution supply a concrete explanation path for the self-target. The source-to-QID collapse is visible; a specific importer fault or mistaken entity merge is not established. Three other cases have incomplete historical evidence.

The next decision should be the representation of **one real example**, such as 124th Division, 2nd formation → 50th Guards. Decide whether this is a continuing unit with dated names/phases or two separate graph entities linked by a transition. Make that decision from historical identity evidence, then apply it consistently to similar cases. Keep the original source statement and source field in either design. Do not derive a new identity from relation labels alone.

No blanket deletion, new entity split, new relation mapping, reversed-endpoint correction or inferred replacement target was applied here.

## Evidence and reproduction

- [source_evidence.json](source_evidence.json): original eight assertions and complete saved Wikidata statements, among the full self-link audit.
- [succession_entities.json](succession_entities.json): saved entity labels, sitelinks, aliases, dates/types and succession claims for all seven entities.
- [succession_source_trace.json](succession_source_trace.json): five accessible pinned revisions, current-only context for the unpinned case, the missing revision response, original field strings and current redirect/QID API response. Revision-query `title` is the page title returned at retrieval; it does not by itself prove that title was used at the revision timestamp.
- [succession_historical_redirects.json](succession_historical_redirects.json): five target revisions at or before the source time. `content_start` and the response content string are capped at 600 characters; these are excerpts, not full article snapshots. The redirect statements fit inside those excerpts.
- [trace_succession_sources.py](../trace_succession_sources.py): repeatable source-field/current-resolution retrieval using `requests`, already installed in the project environment. Does not edit source data or mapping rules. An inaccessible source is saved as an error, not replaced with a guessed field.

```powershell
& 'Agent/.venv/Scripts/python.exe' 'GG_Data/mapping/test_trace_succession_sources.py'
& 'Agent/.venv/Scripts/python.exe' 'GG_Data/mapping/trace_succession_sources.py'
```

The local parser check verifies that indentation is accepted and an empty predecessor does not absorb the following successor field. The historical checks are reproducible using the exact `request_url` values in their evidence file. API responses and current redirect/QID assignments can change after the retrieval date. Saved evidence is the basis for this report.
