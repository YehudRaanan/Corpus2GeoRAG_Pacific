# Simplified core correction implementation plan

> For agentic workers: use superpowers:executing-plans inline, with failing regression checks before implementation.

**Goal:** Correct source-page Event relevance, completeness, dates, Event identity and clear invalid Entity keys; publish a new complete no-geography JSON without overwriting the first release.

**Architecture:** Reuse saved Wikipedia revisions, title mappings, native metadata, article-source-v3 classification and existing compact export/verification. New source observations have their own evidence cache. Original Daniel rows and old releases remain immutable. No mention-to-Wikidata resolution.

**Tech stack:** Existing Python, pytest, pyarrow, ijson, mwparserfromhell, SQLite and saved public-source evidence.

**Spec:** OWNER messages in current thread on 30 October 2026: inspect and filter Events against their source pages, complete source dates, fix date queries, separate same-name Events with different dates, remove junk Entities. Existing approved full-task 24-240 elapsed-hour envelope; geography extension is NOT approved and geography remains paused.

## Constraints and review focus

- Sole owner /root, existing isolated worktree; no geography, training, cloud, installs, paid calls, push, deletions or changes in other worktrees.
- Original input/raw mentions retained byte-for-byte. Every removal must have a recorded reason and evidence; uncertain semantic names are not silently deleted.
- Occurrence hierarchy alone does not establish a concrete Event; distinguish generic concepts/classes and source support.
- Event source identities must not collapse distinct dated battles. Native dates retain precision, calendar, rank and source; unknown dates stay explicitly unknown.
- Date filtering selects dated Events associated with co-occurrence, never invents a date for an undated entity-to-entity relation. Filter before result limits; cover both directions, date boundaries, unknown dates, multiple points and invalid ranges.
- Full source and population denominators, unknowns, redirects and missing records must remain auditable.

## Tasks and interfaces

1. **Evidence spike /root (13:30-13:50 Asia/Jerusalem UTC+02, max20 minutes).** Trace actual raw-page supports, all Event/native type/date groups, unresolved title outcomes and missing native data. Outcome: bounded census and evidence-supported correction rules, or an exact blocker. Reuse existing source classifier; do not guess from English names. Read-only source inputs; write only task-local audit files.
2. **Event/model correction /root, depends1 (0.5/1.5/3 elapsed hours).** Add tested source filtering and recognition/date normalization to the existing adapter or a small correction module; refresh only genuinely missing native data using saved receipts. Expose corrected Entities, Events, membership tables and explicit exclusions/unknowns. Use separate native Event identities for separate source Events. Preserve raw mentions. Test false concept, reference-only link, undated real instance, duplicate name/different date, missing metadata and punctuation-only Entity.
3. **Agent dates /root, depends1 (0.25/0.5/1 elapsed hours).** Carry normalized Event dates to node attributes; reuse calendar/precision comparisons. Remove unconditional empty date guard, filter appropriate Event endpoints before limit, expose temporal semantics. Tests must fail first for in-range result and out-of-range exclusion, both directions, mixed/unknown endpoints, multiple point dates and tools.
4. **Rebuild, independent acceptance and new delivery /root, depends2+3 (1/1.5/3 elapsed hours).** Recompute all distinct-page pairs and both weights for the corrected population, complete model/raw/provenance/date/exclusion checks, load actual Agent, compare same-name separated Events and date queries, package to new immutable version. Run relevant suites and one final fresh review only for this corrective scope, then one correction pass if needed. Check disk reserve before each large materialization. No old outputs replaced.

Task dependencies2->4 (corrected population),3->4 (Agent date interface); shared files/export formats remain root-owned sequentially. Tasks2 and3 are independently testable but no parallel agents are assigned.

## Estimate and state

Model-derived total2/4/8 elapsed hours, start30Oct2026 13:30 Asia/Jerusalem UTC+02, completion range15:30-21:30. Epoch8f43a0bb-2962-434d-9f0e-b2d19c415449: raw PERT4.33h; no empirical probability claim. Superpowers breakdown and Epoch use the same no-geography scope, root ownership, source waits included, elapsed hours; agreement after one exchange. Active_work unknown; approval_wait zero for this already-authorized correction; source environment_wait measured when applicable. Next checkpoint13:40, then13:50.

- [x] Evidence census and correction rules.
- [x] Event/source/quality correction, RED->GREEN.
- [x] Agent date filters, RED->GREEN.
- [x] Full new population, graph, checks and release.

Ruling: Native Event source identity takes precedence over the old exact-name Event collision rule when names identify distinct Events; OWNER explicitly requested separation. Ordinary NER entity identity remains exact name/type. Clear invalid keys are excluded from the new graph with an audit, while original raw rows remain present.
Ruling: Missing P31 is an unresolved classification, not proof that a linked item is an Event or that it is irrelevant. Refresh metadata and preserve remaining uncertainty visibly.

## OWNER scope correction, 30 October 2026 14:40 Asia/Jerusalem UTC+02

Only Events related to World War II are now requested. This supersedes the
earlier all-dates Event population, not the Daniel NER population or page scope.
Date overlap alone and appearing on a WWII ship/person page do not establish
war relevance. Apollo is therefore excluded without an Event-to-war connection.

Ponytail full: reuse pinned native full records, saved own-page infobox fields,
the existing recognition audit and compact exporter. No new graph platform.
Superpowers changed tasks: (2a) bounded15-minute evidence spike for native P361
and inverse P527 paths to Q362, plus explicit own-infobox partof evidence;
(2b) independently test scope decisions and unknowns, then finish source dates;
(4) rebuild and verify the resulting population. Task3 date filtering is already
implemented and remains unchanged. Root is sole writer; no geography, training,
paid calls, installations, deletions, external messages or push.

Remaining model-derived elapsed estimate2/4/8 hours from14:40, completion range
16:40-22:40 on30October2026, central18:40. Source waits included; active_work
unknown. Epoch6e134d2e-352a-4d6e-ba42-c4a2ea8450da, session
simplified-core-v2-wwii-20261030, raw PERT4.33elapsed hours. One exchange agrees
on the changed sequential scope, dependencies, root ownership and elapsed-hour
basis. No empirical confidence claim. Existing OWNER24-240hour approval covers
this narrower Event scope. Next checkpoint14:45, evidence exit14:55.

## OWNER simplification, 30 October 2026 15:20 Asia/Jerusalem UTC+02

Resume under existing approval. Skip further Event completeness/identity review
and source-date conflict/range review. Retain fixes and pinned structured WWII
scope already implemented; do not add the unfinished optional own-prose context
population expansion. Original sources and previous release remain immutable.
For the new export normalize all selected dates: no date -> 1939-09-01 through
1945-09-02; one date -> identical start/end; year/month precision -> first day
of that year/month. Preserve source precision and planned/actual role separately;
mark defaults as OWNER policy, never source observations. Multiple explicit
periods/points remain distinct. Existing native IDs remain separate; no extra
identity audit is commissioned. No geography.

Ponytail full reuses event_date_payload, verifier and existing exporter. Inline
Superpowers changed chain root-owned: D1 tested date normalization (10/20/40min)
-> D2 frozen population/full graph/actual Agent checks (25/50/100min)
-> D3 portable release/review/checkpoint (10/20/40min). Source input/code freeze
precedes large runs. Epoch48ac7867-f254-42f3-8d7f-a7ac506db2de agrees one exchange:
0.75/1.5/3 elapsed hours including local process waits, raw PERT1.63h. Same scope,
dependencies, sole ownership and elapsed-hour basis; model-derived, no empirical
confidence claim; active_work unknown. Completion16:05-18:20 today from15:20,
central16:50. Checkpoint15:30 then every10minutes. Existing approval valid.

## Required integrity corrections, 30 October 2026 15:33 Asia/Jerusalem UTC+02

The fresh final corrective review found one Important provenance defect: current
rule text could be packaged with its older pinned hash. A changed-rule regression
failed first; population verification now rejects any changed event_rule bytes.
No second review or added Event business audit is required.

Full population calendar validation found one source value, 31 June 1943 for
Q125759090, invalid in both native and own-page evidence. Root confirmed the
required integrity rule: preserve the original value and INVALID_SOURCE_DATE
reason, retain any other already-selected usable date, and otherwise apply the
approved OWNER WWII default. Month precision is normalized before validity is
checked. No date repair is guessed. This correction also passed RED -> GREEN.
The first failed population remains immutable; the new accepted candidate path
is core_correction_v2/population_date_integrity_v1. Actual invalid-key exclusion
count is 64 (48 punctuation and 16 fragment keys), superseding provisional 65.

## Completed delivery, 30 October 2026 17:34 Asia/Jerusalem UTC+02

The corrected immutable core release is
`Data/external/simplified_agent_20261030/core_correction_v2/core_release`.
Its manifest SHA256 is
`f2277a370964af79b6b21e434798b8f49b3a25a88f6ff23f27e424faa7e9f8c4`.
The accepted population contains 268,703 nodes, including 788 Events, and
131,034,512 unordered page-co-occurrence pairs (262,069,024 directional views).
Full population/source/node checks, every Relations row, the fresh actual Agent
pair scan, and 11 date queries passed. Focused suites passed: 53 source tests
and 90 Agent tests, with 3 existing expected R6 failures. Original raw input,
the first release, and the failed intermediate population remain unchanged.

The separately authorized offline arbitrary-point extension is complete at
`core_correction_v2/xy_release_v1`, manifest SHA256
`7923e8439fec32d6fc3b921b7bca8a1e29873830d1a385fc5a2796810976ccd4`.
It binds 26,228 files and retains the accepted core model unchanged. All nodes
and non-XY fields, exact edge-tail bytes, a new full Agent scan/index, 11 date
queries, and 4 actual LOC/Event near/bbox checks passed. The graph contains
13,723 LOC points and 427 Event points; 27,683 LOC and 361 Events have explicit
missing-point records. These are partial arbitrary source points, without
identity verification. R6 `what_happened_at` spatial date filtering remains OPEN.
The selector and attachment focused suites passed 9 and 8 tests respectively.

XY elapsed execution was 46.223 minutes from 16:48:20 through 17:34:34, including
local process waits; active work and separate contention waits are unknown.
Epoch actual was recorded once against replan
`5c9db7ef-fdaf-4a7e-a147-33ca8e46207e`. New XY physical allocation is
4,665,558,429 bytes, below the 8 GiB cap; free space remained above 15 GiB.

The corrected core WITHOUT XY is separately Protected on GitHub as a lossless
588,030,417-byte Parquet delivery in draft PR31:
<https://github.com/EtzionR/Corpus2GeoRAG_Pacific/pull/31>.
Final shared commit is `ce0243f03a08a93c0a1d0332b51245a2d9e2d209`.
A fresh independent-cache clone recovered the LFS payload and verified all
14 delivery-file hashes. The source task branch has a local checkpoint only;
the full core and XY package trees remain local. No task-branch push, merge,
source deletion, or worktree removal is authorized for this checkpoint.
