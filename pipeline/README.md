# GeoAI pipeline

The project entry point selects the organized implementation:

```powershell
.\run_pipeline.ps1 -Status
.\run_pipeline.ps1 -Help
.\run_pipeline.ps1 -Plan path\to\explicit-plan.json
```

`current.json` pins the code entry point and verified local runtime. Code and
generated processing output remain in the authorized C: workspace because D:
has little free space. Dataset/cache assets remain at their existing locations.
The launcher changes process-local environment variables only and restores them.
The pipeline's stage/CPU free-space guards remain active. No process or schedule
starts just by installing this entry point.

`data_versions.json` preserves both input versions independently. No default data
version is inferred from selecting new code. Read the actual public tables with:

```powershell
python -B pipeline\read_data.py legacy_full_47141678ff0f
python -B pipeline\read_data.py daniel_partof_20261103
```

The previous full version has 5,747 processing units / 5,693 physical pages and
existing approved CPU state and four-table consumer artifacts. Its formal
six-table SQLite model was **not populated**. The new 521-unit version has a
committed six-table model and export, with 63,655 source-pending records retained.
These statuses are separate from schema version and data version identity.

The legacy code archive is a byte-preserving copy with an exact source manifest.
Original code paths stay in place because frozen provenance receipts still
reference them. Active retained algorithms under the organized implementation's
`support/legacy` directory remain runtime dependencies of the new pipeline.

Rollback: this installation adds a project launcher/selector; it does not replace
legacy entry scripts or alter existing data. Preserve this directory, the archive
and source manifest. To return to a known legacy invocation, use its archived
original locator explicitly after reviewing its dataset and output ownership.
Changing this selector requires an explicit new reviewed entry-point hash.
No permissions, scheduled tasks, application data selection or external
publication are changed by this installation.


## Measured comparison of the two preserved data versions

| Measure | Previous full version | New PART_OF version |
|---|---:|---:|
| Declared physical pages | 5,693 | 521 |
| Admitted mentions | 1,301,119 | 106,853 |
| Exported typed entities | 3,529 | 1,194 |
| Distinct exported QIDs | 1,985 | 841 |
| Unique events | 4 | 4 |
| Active geolocated QIDs | 883 | 542 |
| Native relation observations | 731 | 450 |

On the same **518 pages with admitted mentions in both versions**, the previous
version has 80,585/166,773 QID-linked mentions
(48.32%), versus 54,773/106,853
(51.26%) in the new version. Explicit NONE rates are
4.06% and 5.40%; pending
rates are 47.62% and 43.34%.
Three additional declared new pages have all their input held before admission;
they remain in Wiki Pages and the held ledger. The two mention populations still
differ, so these coverage rates do not establish an accuracy improvement.

There are 18 newly exported QIDs. Fifteen were already linked in the prior CPU
state; three were not: USS Paddle (Q6141277), Battle of Toungoo (Q691273), and
USS Ommaney Bay (Q930940). Across the entire CPU result there are 59 newly linked
QIDs; most are outside the approved final export. `new_exported_QIDs.csv` lists
the 18 exported additions and whether the prior CPU had already linked them.

For the same 2,043 LOC QIDs identified in the shared-page cohorts, both versions
have approved geometry for 534 (26.14%).
The higher overall geometry ratio in the new smaller corpus reflects a changed
entity/scope mix; no geometry gain is measured for this common LOC population.

Both outputs contain the same four event QIDs and the same supplied type claims.
The current candidate bridge has four explicitly supplied Event-QID routes;
these counts do not establish that no other events occur in either corpus.
Native Event assertions fall from 127 to 94; these are observations, not unique events.

The previous six-table model remains **not populated**. Its full approved CPU
state and existing public model are preserved and linked under a named registry
version. Backfill was not started: the current writer's minimum space preflight,
using only the twice-stored Text values, already requires at least
25.73GiB free versus
16.79GiB observed. Other fields increase that lower bound.
No CPU matching needs to be rerun for that future conversion, but its full
source-to-six-table mapping and readback remain to be validated.

The new model is populated but has 63,655 source-pending input records and
preserves unknown fields. Its 46,310 CPU-pending admitted mentions are a separate
population; later route evidence does not justify calling every fact resolved.

`DATA_VERSION_COMPARISON.json` records numerators, denominators, QID lists,
event type IDs and pinned evidence. The controlled comparison of old/new code
on the same frozen 100 new inputs passed; this cross-data-version comparison
does not isolate pipeline effects from input/scope changes. No expensive CPU
scoring, new dataset processing, permission change or external publication was
performed by this comparison.
