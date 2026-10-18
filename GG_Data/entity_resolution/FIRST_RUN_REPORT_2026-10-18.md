# First candidate run — 18 October 2026

Completed on all **309,864 mentions** across **428 source pages**.
Every raw row and all nine original fields were preserved and verified after writing.

**44,547 mentions have name candidates**, producing **194,298 mention/entity pairs**.
This is 16.4% of the 271,432 non-date mentions.
No final identities were selected. Candidate recall and linking accuracy have not been measured.

## Counts

| Extracted type | All input mentions | With name candidates | No name candidate in resolved page pool | Page not in snapshot | Dates deferred |
|---|---:|---:|---:|---:|---:|
| DATE | 38,432 | 0 | 0 | 0 | 38,432 |
| LOC | 89,846 | 11,774 | 41,445 | 36,627 | 0 |
| MISC | 85,676 | 18,522 | 35,471 | 31,683 | 0 |
| ORG | 47,680 | 7,787 | 22,689 | 17,204 | 0 |
| PER | 48,230 | 6,464 | 24,409 | 17,357 | 0 |
| **Total** | **309,864** | **44,547** | **124,014** | **102,871** | **38,432** |

The page lookup resolved **239/428 pages (55.8%)**. The other **189 pages** account
for **117,644 raw mentions**, including dates. Exact saved Wikipedia sitelinks did
not add more page identities. Six resolved pages offer only their own page identity in the pool.
The page pools contain 8,554 distinct entity IDs; 1,169 lack metadata in the saved
Wikidata file and therefore cannot supply names or aliases in this run.

## What this run shows

- `Isoroku Yamamoto`, Attack on Pearl Harbor, paragraph 1: Q152325 at 1.0 and
  Q5986314 (alias `Ichirou Yamamoto`) at 0.5714. Both remain candidates.
- `Noel Irwin`, 14th Indian Infantry Division, paragraph 6: Q7047013 at 1.0.
- `Franklin D. Roosevelt`, Attack on Pearl Harbor, paragraph 3: the strict page
  pool does not offer Roosevelt. It returns Q1445298 (`Franklin Van Valkenburgh`)
  at 0.3684. This exposes the risk of weak name overlap and missing correct
  candidates. This result is **not an accepted identity link**.

Names with candidates are not necessarily correct matches. A count of one
candidate also does not establish correctness. Unresolved rows do not establish
that an entity is unknown.

## Fixed scope and evidence

- Daniel upload commit: `43e35453421b032fc67d426d7d16fe436574b0fa`.
- Runtime code checkpoint: `cddfc01`; exact input and code hashes are in the manifest.
- Method: `page-trigram-candidates-v0.1.0`; threshold 0.35; no candidate cap.
- Candidate scope: page identity and direct graph neighbours, using English labels/aliases.
- `PER`: explicit saved `P31=Q5`. Other entity type checks remain **PENDING**.
  All `DATE` rows remain **DEFERRED_DATE**.
- Relation-map-v2.1.0 replayed over 700,890 legacy assertions after restoring
  original endpoints. All 14 approved assertion exclusions were applied.
- Page context keeps original and mapped endpoints, source predicates, source
  record IDs, and observation IDs. No HITS ranking, model calls, new entities,
  final links, relation extraction, or event extraction were run.

## Verification

Two focused tests passed, including indexed-versus-exhaustive name scoring,
alias evidence, type rules, stable mention IDs, and overlapping spans. All nine
notebook code cells also ran with the shared name functions.

The full run reread all output rows and verified raw-field equality, unique
stable IDs, row counts, candidate counts, page-pool membership, source names,
exact similarity scores, and the person type rule. Input/code hashes were
unchanged from start to finish. Output hashes are recorded in the completion manifest.

## Files

- [Candidate rows](runs/first_candidates_v0.1.0_20261018/mention_candidates.jsonl.gz)
- [Page and assertion evidence](runs/first_candidates_v0.1.0_20261018/page_context.jsonl.gz)
- [Entity names and types](runs/first_candidates_v0.1.0_20261018/entity_metadata.jsonl.gz)
- [Full counts and page details](runs/first_candidates_v0.1.0_20261018/summary.json)
- [Completed run manifest](runs/first_candidates_v0.1.0_20261018/run_manifest.json)
- [Run instructions and schema](README.md)

## Next improvement

Improve page identity and candidate coverage first. Resolve the missing page
mappings and inspect known entities excluded by the direct-neighbour rule before
using graph ranking to select identities. Keep this run unchanged as the baseline.
Unknown-entity handling remains a separate open issue.

Backup status: **Local checkpoint only**. The run outputs and code are committed
locally. Large source snapshots remain outside Git; their exact hashes are
recorded in the manifest. No off-device backup was verified for these changes.
