# WWII Agent draft graph: independent data audit

**Date:** 2026-10-13
**Graph:** `wwii-agent-draft-v0.1.0`
**Graph SHA-256:** `11568ad9618f612e7c33b8f074171709a26b7a261d29f50634a5bda188e4af97`
**Status:** Data and code review of a draft for Agent mechanism QA. This is not an acceptance decision for the Pacific graph.

## Executive conclusion

The draft loads correctly, but its successful structural checks do not establish that its facts can support grounded answers. The largest observed problem is a handoff error in relation-family mapping: a **ranked, unapproved candidate** is copied into the active family field, and the export omits the assignment status that would tell the Agent it is provisional. This can turn ordinary relations such as *significant event* or *participant in* into apparently spatial edges.

The next broad problem is endpoint identity. About two thirds of all edges touch at least one node whose name is only a QID. Event-place queries are therefore weak even before geometry is considered. The graph also lacks article passages and paragraph-level evidence, has many unresolved entity types, and often has only a broad participant or country relation where a question needs a specific actor, side, or place. Date parsing admits invalid or reversed intervals.

Geometry is **not an acceptance requirement at this stage**. The draft's Wikidata points were used for Agent mechanism QA. They are not the approved GG geometry source. A missing geometry value in this draft is not, by itself, a GG data fault. A country-scale place relation, an unresolved place identity, and an unsupported *who attacked?* answer are data and answer-support issues that remain relevant without geometry.

## Scope, sources, and method

The audit used a full scan of the local draft JSON, its data-quality report, the mapped relation rows and mapping/export notebooks, the available corpus text file, and the Agent developer's published documentation and code at the fixed commit. It did not run a model, fetch new metadata, geocode places, or change source data. Counts below refer to this one graph snapshot unless stated otherwise.

| Source | Use |
|---|---|
| [Draft graph](../GG_Data/agent_export/outputs/wwii_agent_graph_draft_v0.1.0.json) and [build QA](../GG_Data/agent_export/outputs/wwii_agent_graph_draft_v0.1.0_dq.json) | Full node and edge scan; version, scope, and loader checks. The graph is a local ignored output and may not exist in a fresh clone. |
| [Graph builder](../GG_Data/agent_export/BUILD_WWII_AGENT_GRAPH_DRAFT.ipynb) | Endpoint metadata, type, text, source, date, and edge export logic. |
| [Mapping notebook](../GG_Data/mapping/RELATION_MAPPING_ALL_ITEMS_v1.0.0.ipynb) and [mapping method](../GG_Data/mapping/RELATION_MAPPING_LOGIC_AND_RESULTS_2026-10-12.md) | Relation-family assignment and review semantics. |
| [Corpus text](../Data/DATA.json) | Exact article-title overlap and available passage text. |
| [Agent handoff](https://github.com/EtzionR/Corpus2GeoRAG_Pacific/blob/1e1acd4384ad78cc741cb42812792cb5c65ec152/Agent/docs/GRAPH_TEAM.md), [Agent graph store](https://github.com/EtzionR/Corpus2GeoRAG_Pacific/blob/1e1acd4384ad78cc741cb42812792cb5c65ec152/Agent/geo_agent/graph_store.py), and [Agent logic](https://github.com/EtzionR/Corpus2GeoRAG_Pacific/blob/1e1acd4384ad78cc741cb42812792cb5c65ec152/Agent/geo_agent/agent.py) | Contract claims and the way the Agent reads roles, dates, geometry, and sources. |

The QA report identifies 53,857 core QIDs from an English Wikipedia World War II task force, 146,318 nodes, 700,890 edges, 810 relation types, and no Pacific corpus in this draft. All edge endpoints exist, IDs are unique, and the Agent loader read the whole file. These are important *format and loading* results. They are not semantic or citation checks. All draft edges touch at least one core node; 464,095 join a core node to an external endpoint.

## Findings, ordered by effect on answers

### 1. Unreviewed relation-family candidates become active graph facts

**Confirmed code fault.** The mapping notebook reads `level1_family`, then replaces `UNRESOLVED` with `level1_candidate` in `map_relation`. The mapping method says Level 1 may remain unresolved when only a ranked candidate exists. The mapped rows retain `level1_assignment_status`, but the graph builder exports `level1_relation` as `attributes.relation_family` and omits the assignment status. The Agent cannot tell which active families were only suggestions.

- 142,891 mapped assertions have `level1_assignment_status=RANKED_REVIEW_REQUIRED`. Of those, 142,849 have `final_review_status=ACCEPTED`; that status applies to the Level 2 relation, not to the broad family.
- 143,130 graph edges have an active family different from the graph catalog's listed family. The catalog lacks 61 used relation types on 101,176 edges; eight used types have more than one family.
- Examples: `wd:P793` (*significant event*, 30,455 edges) is active as `SPATIAL` although its catalog family is `UNRESOLVED`; `wd:P735` (*given name*, 18,310) is `AFFILIATION_STATUS`; `wd:P734` (*family name*, 12,516) is `PART_WHOLE_HIERARCHY`; `wd:P1344` (*participant in*, 2,604) and YAGO `participatedIn` (1,744) are `SPATIAL`.
- The catalog also lacks heavily used types such as `wd:P31` (56,106 edges), `wd:P21` (17,476), and `wd:P279` (5,312). An edge type missing from the catalog is a coverage fault, not proof that every individual assertion is false.

**Effect.** A family filter, graph index, or generated explanation can treat a nonspatial relation as spatial. Agent code that uses an explicit relation-ID allowlist may avoid some of this damage, but it does not repair the exported semantics. The correction is to preserve the *accepted family*, the *ranked candidate*, and the *family review status* as distinct fields, then reconcile the catalog against actual used types. Do not promote a candidate by filling a null or `UNRESOLVED` active field.

### 2. Endpoint names and entity types do not support reliable place lookup

**Confirmed data limitation with a separate classifier issue.** Metadata fetching for missing endpoints is disabled in this first draft (`FETCH_MISSING_METADATA=False`). The builder falls back to the QID as name, an empty alias list, and an empty description. It sets `metadata_status=QID_FALLBACK` for 91,880 nodes; 92,307 node primary names are QIDs. Some other node paths also produce a QID name, so these two counts are not identical. Of all 700,890 edges, 462,289 (65.96%) touch at least one fallback endpoint. A named source node does not make its target searchable by name.

This is not only missing metadata. Of the locally populated nodes, 18,545 are still classified `other`; 16,828 of those have `P31` type data. The five-class rules also misclassify known entities. Examples in this snapshot include USS Yorktown as `location` or `other`, the Imperial Japanese Navy and US Navy as `other`, Soviet Union as `location`, and Independent State of Croatia as `event`. `other` is an acceptable unresolved state for genuinely uncertain nodes; automatic conversion of all `other` nodes would introduce new errors.

**Place examples.** Midway Atoll (`Q47863`), Tokyo (`Q1490`), and Guadalcanal (`Q192767`) occur as fallback-QID `other` nodes. Their missing geometry is expected at this stage; their missing names and unresolved place types make name-based discovery and role checks fail now. The same general problem applies to Kiska and other endpoint-only places.

There are also 741 exact duplicate-name groups covering 1,699 nodes. Shared names can be legitimate. Search must return candidate identities with QIDs and context instead of silently taking the first string match.

### 3. Event-place links often have the wrong granularity or an unusable target

The graph contains 6,224 nodes typed `event`. Using the Agent's broad occurrence relation set (`OCCURRED_AT`, `wd:P276`, `P276+OBJECT_TYPE_CITY`, `wd:P131`, `wd:P706`), 2,545 events have an outgoing occurrence-like edge. Only 589 have at least one target with a readable primary name, and only 191 have a named target typed `location`. Only 162 meet that last condition *and* have a usable node date. This is a deliberately narrow structural measure, not a measured answer rate: another route or text source could still support an answer.

For event-source `wd:P276` alone, there are 3,765 edges: 2,349 target QID-named `other` nodes; 777 target named `other`; 379 named `location`; 227 named `event`; and 33 named `org`. This mixes missing metadata, type faults, and possible source meaning differences. The predicate `P276` cannot alone certify that the target is a precise battle site.

There are 723 event `P276` edges to four state-scale nodes: Nazi Germany (230), Soviet Union (218), Empire of Japan (198), and Kingdom of Italy (77). For the Battle of Midway, one Wikidata `P276` assertion points to Midway Atoll, while two EventKG `sem:hasPlace` assertions mapped to `P276` point to Empire of Japan. The country assertions may be valid broad context. They should remain as source assertions with their predicate and scale. A *where did it happen?* answer needs the most specific **supported** place for the question; it must not convert a country to a battle site or discard the broad assertion without review.

This responds to the possible missing-geo explanation: **the location error starts before geometry**. A country-scale edge and an unlabeled atoll node are different failures. Geometry cannot choose the intended semantic scale or repair an unresolved identity. :codex-annotation{index="1"}

### 4. Participation is not an attack role

The draft has broad war, participant, and commander links, but no `ATTACKED` or `BOMBED` edge type and no populated `attributes.side` on edges. Among the 6,224 event nodes, 1,926 have a link in a broad actor/participant/commander set; 1,559 have both such a link and an occurrence-like place link; 1,467 also have a usable event date. These figures **overstate** support for questions such as *who attacked whom?* A participant could be an attacker, defender, commander, victim, or merely related to a wider conflict.

The graph has 80,429 `wd:P607` (*conflict*) edges. Of these, 46,227 point to the World War II hub and only 426 point to Pacific War. Traversing a hub can return plausible but unrelated entities. The Agent has a cap on broad subevent expansion; that limits query size, but cannot establish an attacker side. A role answer needs a source assertion or cited passage that states the action and direction. If that is absent, the Agent should abstain.

### 5. The draft cannot supply article-level evidence claimed by answer text

`Data/DATA.json` contains 428 article-title to full-text entries. Exactly 239 titles match a graph node Wikipedia source title; 189 have no exact-title match. A different title or alias may explain some unmatched entries, so this is a join diagnostic, not a count of absent topics. None of the 428 article texts is attached to a matching graph node in this draft. The longest graph `text` among matched titles is 195 characters.

Across the whole graph, 94,444 nodes have empty `text`; 51,800 have 1–160 characters; 74 have 161–500; none exceed 500. The builder uses a Wikidata description for `text`, not a Wikipedia passage. All 146,318 node `sources` have `paragraph=null`. A Wikipedia sitelink gives a page identity, but it does not show which sentence supports a claim. Some source page fields are labels rather than QIDs, which further weakens automatic citation.

The Agent asks for source search and Wikipedia citations. This draft can help locate a page but cannot, by itself, provide retrieved article passages and paragraph-level evidence for a grounded answer. The corpus and raw extraction are upstream inputs; this audit does not assume they must be rebuilt. The needed handoff is a verified entity-to-passage join that keeps page, paragraph, source assertion, and text together.

### 6. Dates mix missing, broad, and invalid values

The Agent's node-date rule yields a usable date for 2,360 event nodes; 3,864 have none. A simpler check of direct start/end/point fields finds 4,979 events with none, but 1,115 of these have point-date candidates, so it would exaggerate missing dates under Agent logic. Some undated events touch dated edges, but an adjacent date is not automatically the event date.

At edge level, 618,963 of 700,890 edges have no start, end, or point date. Many are timeless types, so this is not a blanket quality-failure count. The confirmed validation problems are 130 edges with `start_date > end_date` and six edge date fields that are not valid calendar dates (examples include `1927-02-29` and `1934-02-31`). Observed years extend from 0044 to 6194; early years can be valid in a broad historical graph, while the 15 fields after 2100 and 25 before 1000 warrant source review. The exporter normalizes date strings but does not check calendar validity or interval order. A time filter cannot repair those values.

### 7. Review state, duplicate evidence, and ranking need explicit semantics

The graph has 127,929 edges with `final_review_status=PROVISIONAL` and 572,961 accepted edges. Within the provisional set, 102,154 are runtime-unresolved relations and 22,405 are `wd:P607`; 21,714 of those `P607` mappings came from EventKG `http://dbpedia.org/ontology/battle`. The Agent includes provisional edges in its graph and does not show review status in the ordinary edge summary. These edges are not automatically false, but their uncertainty can disappear before generation.

Grouping by source, target, relation, and dates found 74,111 assertions beyond the first row in 61,543 repeated-key groups. The checked repeats had distinct source record IDs. They may be independent evidence rather than duplicate mistakes. The Agent combines them at query time, so this is not a reason to delete them. However, groups with different broad families or review states need a rule for which attributes are exposed, and summed counts must not be mistaken for independent corroboration without checking source dependence. In this snapshot, 115 repeated-key groups have mixed families.

The graph also has 1,328 isolated core nodes and 45 self-loop edges. These are lower-priority diagnostics. Isolation affects coverage; a self-loop may be an extraction or source artifact. Neither count alone proves a false fact.

## Geometry boundary

The draft includes 7,605 points derived from Wikidata `P625`, including 2,033 event nodes. They helped test Agent loading and spatial tools. The [GG geocoding process](GEOCODING_HIGH_LEVEL_PROCESS.md) specifies one selected, user-owned Shapely object per confirmed place, with source and decision evidence; Wikidata can support identity but is not the geometry source. The Agent's current file contract consumes GeoJSON geometry. A conversion and acceptance interface from the GG geometry store to that contract has not been demonstrated here.

Therefore, do not use draft point coverage as GG geometry progress, and do not fail the present GG handoff solely because an endpoint has `geometry=null`. Fix place identity, type, relation meaning, and provenance first. Geometry acceptance is a later gate under the stated source policy.

## What the Agent examples do and do not establish

The Agent developer's fixed-commit documentation reports 10/10 contract checks and 9/56 question-evaluation success. The available examples show questions, final answers, and tool-call names/arguments. They do **not** provide a complete per-question package of the full prompts, returned tool payloads or retrieved passages, generated answer, and gold judgment for all 56 questions. Thus the 9/56 result identifies a serious system gap, but these documents do not let us attribute each failed question to one graph defect. The counts in this audit are independent data measurements, not a reconstruction of those 56 outcomes.

One complete trace per selected question should retain: the exact question and system/developer prompts; graph version and hash; tool calls with parameters and returned payloads; passage retrieval results; final generated text and citations; expected answer; and the reason for a pass or fail. Include cases that test place identity, country versus site scale, attacker versus participant, time, and abstention. Freeze that small trace set before changing mapping or graph data, then compare it with a new export. No model run is required to record the current data faults.

## Conclusions and action order

| Priority | Owner at handoff | Action and acceptance evidence |
|---:|---|---|
| 1 | GG relation mapping/export | Keep unresolved Level 1 families unresolved; export candidate and assignment status separately; reconcile every used relation ID with the catalog. Recount family conflicts and inspect the listed high-volume counterexamples. |
| 2 | GG entity identity/type | Resolve endpoint QIDs with source-backed names, aliases, and type evidence. Preserve unresolved cases. Check named event-place targets and known misclassified ships, navies, states, and places. Do not infer a place merely from a matching name. |
| 3 | GG assertion model with Agent | Preserve original predicate, source record, scale, review state, and direction. Define which relation or passage supports `occurred at`, `participated`, `attacked`, and `defended`. Make unsupported roles abstain. |
| 4 | Corpus-to-graph handoff | Join verified article passages and paragraph references to claims or entities. A page sitelink alone is not a claim citation. Retain raw upstream evidence without changing the corpus collection scope. |
| 5 | GG date export | Check calendar dates and interval order; distinguish unknown dates from timeless relations and from source-level conflict dates. Review extreme values with original assertions. |
| 6 | Agent evaluation | Publish a small complete, frozen trace set and score place, actor, time, citation, and abstention separately. Use it to attribute observed answer failures after the data correction. |
| Later | GG geocoding and Agent integration | Supply approved source geometry and verify the Shapely-to-Agent representation when the geometry gate opens. |

The near-term acceptance question is whether an answer can follow a **reviewed relation and identifiable entities back to evidence at the right semantic scale**. Loader success, a non-null point, or a broad war link does not answer that question.

## Limits of this audit

- The graph is a World War II mechanism draft without the Pacific corpus. These rates should not be projected to a future Pacific release.
- Type and role coverage counts use the current five-class labels and the Agent's current relation lists. They are structural diagnostics, not a manually judged gold set.
- A QID label, `other` type, missing date, repeated assertion, broad country relation, or absent geometry is not automatically an incorrect source claim. The finding states the precise downstream risk for each case.
- Exact-title corpus matching does not account for redirects or aliases. Passage joins need identity checks before their count can be treated as coverage.
- No full 56-question prompt/tool/retrieval/answer traces were available for causal evaluation. No new model evaluation or geometry build was run for this report.
