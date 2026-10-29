"""The revised workflow keeps page scopes and experimental evidence explicit."""

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from GG_Data.entity_resolution.luke_pilot.data import sha256
from GG_Data.pipeline.post_qid_run import freeze_scopes, prepare
from GG_Data.pipeline.test_post_qid_run import core_inputs as _core_inputs


@pytest.fixture(name="core_inputs")
def revised_core_inputs(tmp_path):
    return _core_inputs.__wrapped__(tmp_path)


def test_scopes_use_readable_title_when_raw_source_is_qid():
    rows = [
        dict(page_id=i, revision_id=i * 10, Source=f"Q{i}", source_title=f"P{i}")
        for i in range(1, 101)
    ]
    result = freeze_scopes(rows, ["P1", "P2", "P3"], [f"P{i}" for i in range(1, 101)])
    assert len(result["3"]["page_ids"]) == 3
    assert len(result["10"]["page_ids"]) == 10
    assert result["100"]["original_rows"] == 100


def test_prepare_binds_explicit_cleaned_and_matching_stages(tmp_path):
    source = tmp_path / "input"
    source.mkdir()
    matching = source / "matching"
    matching.mkdir()
    rows = [
        dict(page_id=i, revision_id=i * 10, Source=f"Q{i}", source_title=f"P{i}")
        for i in range(1, 101)
    ]
    for name in (
        "selected_mentions.parquet",
        "cleaned_mentions.parquet",
        "revisions.parquet",
    ):
        pq.write_table(pa.Table.from_pylist(rows), source / name)
    (source / "selection.json").write_text(
        json.dumps(
            dict(
                input_sha256="a" * 64,
                old_ten_titles=["P1", "P2", "P3"],
                source_titles=[f"P{i}" for i in range(1, 101)],
            )
        )
    )
    (matching / "groups.jsonl").write_text("")
    (matching / "jobs.jsonl").write_text(
        "".join(
            json.dumps(dict(id=str(i), page_id=i, revision_id=i * 10)) + "\n"
            for i in range(1, 101)
        )
    )
    pq.write_table(
        pa.table({"group_id": pa.array([], type=pa.string())}),
        matching / "exact_pairs.parquet",
    )
    result = prepare(
        source,
        tmp_path / "scopes",
        matching_subdir="matching",
        mentions_name="cleaned_mentions.parquet",
    )
    assert result["matching_subdir"] == "matching"
    assert result["mentions_name"] == "cleaned_mentions.parquet"
    assert result["inputs"]["cleaned_mentions.parquet"] == sha256(
        source / "cleaned_mentions.parquet"
    )
    assert result["inputs"]["matching/jobs.jsonl"] == sha256(matching / "jobs.jsonl")


def test_portable_approval_uses_identical_local_manifest_bytes(tmp_path):
    from GG_Data.entity_resolution.hundred_page_pilot.readiness import (
        validate_experimental_scope,
    )

    checkpoint = tmp_path / "checkpoint"
    checkpoint.write_bytes(b"same trained checkpoint")
    jobs = tmp_path / "jobs.jsonl"
    jobs.write_text(
        "".join(
            json.dumps(dict(page_id=p, revision_id=p * 10)) + "\n" for p in (1, 2, 3)
        )
    )
    manifest = tmp_path / "local_manifest.json"
    manifest.write_text(
        json.dumps(
            dict(
                page_ids=list(range(1, 101)),
                page_revisions=[
                    dict(page_id=p, revision_id=p * 10) for p in range(1, 101)
                ],
                original_mentions_sha256="a" * 64,
                source_reference_sha256="b" * 64,
            )
        )
    )
    approval = dict(
        approved_by="OWNER",
        scope="experimental_source_name_pilot",
        decision="Allow the exploratory source-name pilot with this model",
        checkpoint_sha256=sha256(checkpoint),
        jobs_sha256=sha256(jobs),
        page_ids=[1, 2, 3],
        manifest=dict(path="/remote/manifest.json", sha256=sha256(manifest)),
        approval_evidence="OWNER approved revised pipeline run",
    )
    validate_experimental_scope(approval, checkpoint, jobs, manifest_path=manifest)
    manifest.write_text("{}")
    with pytest.raises(ValueError, match="manifest-bound"):
        validate_experimental_scope(approval, checkpoint, jobs, manifest_path=manifest)


def test_core_uses_manifest_stage_paths_instead_of_old_run_names(
    core_inputs,
):  # noqa: F811
    from GG_Data.pipeline.post_qid_run import build_core

    source, scope, inference, native, model, output = core_inputs
    (source / "matching_k80_v2").rename(source / "matching")
    (source / "selected_mentions.parquet").rename(source / "cleaned_mentions.parquet")
    manifest_path = scope / "scope_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest.update(
        matching_subdir="matching", mentions_name="cleaned_mentions.parquet"
    )
    manifest["inputs"] = {
        name.replace("matching_k80_v2/", "matching/").replace(
            "selected_mentions.parquet", "cleaned_mentions.parquet"
        ): value
        for name, value in manifest["inputs"].items()
    }
    manifest_path.write_text(json.dumps(manifest))
    result = build_core(
        source, scope, inference, native, output, model_dir=model, stage="legacy"
    )
    assert result["counts"]["mentions"] == 4


def test_pending_and_exact_snapshots_do_not_invent_unresolved_nodes(
    core_inputs,
):  # noqa: F811
    import gzip

    from GG_Data.pipeline.post_qid_run import write_stage
    from GG_Data.pipeline.test_post_qid_stages import row

    source, scope, _, native, _, output = core_inputs
    rows = pq.read_table(source / "selected_mentions.parquet").to_pylist()
    rows = [
        row(
            r["source_row_index"],
            **{k: v for k, v in r.items() if k != "source_row_index"},
            raw_original_word=r["word"],
            word_original=r["word"],
            Text_clean=r["Text"],
            clean_start=0,
            clean_end=len(r["word"]),
        )
        for r in rows
    ]
    for r in rows:
        r["matching_eligible"] = r["entity_group"] != "DATE"
        r["matching_eligibility_reason"] = (
            "eligible" if r["matching_eligible"] else "deferred_date"
        )
    pq.write_table(pa.Table.from_pylist(rows), source / "selected_mentions.parquet")
    groups = [
        json.loads(line)
        for line in (source / "matching_k80_v2/groups.jsonl").read_text().splitlines()
    ]
    groups = [g for g in groups if g["type"] != "DATE"]
    (source / "matching_k80_v2/groups.jsonl").write_text(
        "".join(json.dumps(g) + "\n" for g in groups)
    )
    pq.write_table(
        pa.Table.from_pylist([dict(group_id="g2", qid="Q1", method="exact")]),
        source / "matching_k80_v2/exact_pairs.parquet",
    )
    manifest_path = scope / "scope_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["inputs"] = {name: sha256(source / name) for name in manifest["inputs"]}
    manifest_path.write_text(json.dumps(manifest))
    pending = write_stage(source, scope, output / "pending", "3", "pending")
    exact = write_stage(
        source, scope, output / "exact", "3", "exact", native_dir=native
    )
    assert pending["counts"]["mentions"] == 4 and pending["counts"]["entities"] == 0
    assert exact["counts"]["entities"] == exact["counts"]["mention_entity_links"] == 1
    with gzip.open(output / "exact/mentions.json.gz", "rt") as stream:
        states = [r["processing_status"] for r in json.load(stream)]
    assert states == [
        "DEFERRED_DATE",
        "DEFERRED_DATE",
        "ACCEPTED_EXACT",
        "PENDING_MATCHING",
    ]
    from GG_Data.pipeline.post_qid_eda import run as eda

    eda(output / "exact", output / "exact_eda")


def test_revised_core_final_keeps_dates_out_of_entity_table(core_inputs):  # noqa: F811
    import gzip

    from GG_Data.entity_resolution.hundred_page_pilot import readiness
    from GG_Data.pipeline.post_qid_run import build_core
    from GG_Data.pipeline.test_post_qid_stages import row

    source, scope, inference, native, model, output = core_inputs
    rows = pq.read_table(source / "selected_mentions.parquet").to_pylist()
    rows = [
        row(
            r["source_row_index"],
            **{k: v for k, v in r.items() if k != "source_row_index"},
            raw_original_word=r["word"],
            word_original=r["word"],
            Text_clean=r["Text"],
            clean_start=0,
            clean_end=len(r["word"]),
            matching_eligible=r["entity_group"] != "DATE",
        )
        for r in rows
    ]
    pq.write_table(pa.Table.from_pylist(rows), source / "selected_mentions.parquet")

    def save(path, value):
        path.write_text(json.dumps(value))

    def lines(path, values):
        path.write_text("".join(json.dumps(v) + "\n" for v in values))

    groups = [
        json.loads(line)
        for line in (source / "matching_k80_v2/groups.jsonl").read_text().splitlines()
    ]
    lines(
        source / "matching_k80_v2/groups.jsonl",
        [g for g in groups if g["type"] != "DATE"],
    )
    pq.write_table(
        pa.Table.from_pylist([dict(group_id="g2", qid="Q1", method="exact")]),
        source / "matching_k80_v2/exact_pairs.parquet",
    )
    job = dict(
        id="job",
        page_id=3,
        revision_id=30,
        qid="Q1",
        excluded_count=0,
        candidates=[dict(id="g3", type="LOC")],
    )
    lines(source / "matching_k80_v2/jobs.jsonl", [job])
    lines(scope / "jobs_3.jsonl", [job])
    lines(
        inference / "scores.jsonl",
        [dict(id="job", options=[dict(id="g3", score=2), dict(id=None, score=1)])],
    )
    lines(
        inference / "model_pairs.jsonl",
        [
            dict(
                id="job",
                page_id=3,
                revision_id=30,
                qid="Q1",
                group_id="g3",
                entity_group="LOC",
                method="model",
            )
        ],
    )
    decisions = [
        json.loads(line)
        for line in (inference / "decisions.jsonl").read_text().splitlines()
    ]
    for d in decisions:
        d.update(page_id=3, revision_id=30)
        if d["group_id"] is not None:
            d["group_id"] = "g3"
    lines(inference / "decisions.jsonl", decisions)
    gate_path = model / "readiness.json"
    gate = json.loads(gate_path.read_text())
    paths = {
        k: Path(v["path"])
        for k, v in gate["files"].items()
        if not k.startswith("input:")
    }
    metrics = json.loads(paths["held_out_metrics"].read_text())
    metrics.update(predicted_stops=10, correct_stops=9)
    save(paths["held_out_metrics"], metrics)
    inspection = json.loads(paths["checkpoint_inspection"].read_text())
    inspection["final_artifact_hashes"]["held_out_metrics"] = sha256(
        paths["held_out_metrics"]
    )
    save(paths["checkpoint_inspection"], inspection)
    save(
        gate_path,
        readiness.build_readiness(
            model / "full_best.pt", paths, source / "training_k80_v2"
        ),
    )
    signature = json.loads((inference / "inference_inputs.json").read_text())
    signature.pop("experimental_approval_sha256")
    signature.update(
        jobs_sha256=sha256(scope / "jobs_3.jsonl"), readiness_sha256=sha256(gate_path)
    )
    save(inference / "inference_inputs.json", signature)
    save(inference / "inference_summary.json", dict(questions=1, **signature))
    manifest_path = scope / "scope_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["inputs"] = {name: sha256(source / name) for name in manifest["inputs"]}
    save(manifest_path, manifest)
    result = build_core(
        source, scope, inference, native, output, model_dir=model, stage="final"
    )
    assert result["counts"]["mentions"] == 4
    assert result["counts"]["entities"] == 2
    with gzip.open(output / "mentions.json.gz", "rt") as stream:
        assert [r["processing_status"] for r in json.load(stream)] == [
            "DEFERRED_DATE",
            "DEFERRED_DATE",
            "ACCEPTED_EXACT",
            "ACCEPTED_MODEL",
        ]


def test_assembly_validates_event_endpoints_before_publish(tmp_path):
    import gzip

    from GG_Data.pipeline.post_qid_run import assemble
    from GG_Data.pipeline.test_post_qid_eda import tables as example_tables

    core, events = tmp_path / "core", tmp_path / "events"
    core.mkdir()
    events.mkdir()

    def save(directory, name, value):
        with gzip.open(directory / f"{name}.json.gz", "wt") as stream:
            json.dump(value, stream)

    tables = example_tables.__wrapped__()
    for name, value in tables.items():
        save(core, name, value)
    (core / "manifest.json").write_text(
        json.dumps(
            dict(
                scope="3",
                counts={n: len(v) for n, v in tables.items()},
                outputs={p.name: sha256(p) for p in core.glob("*.json.gz")},
            )
        )
    )
    save(events, "event_entities", [dict(entity_id="Q99", type="event")])
    save(events, "events", [dict(event_id="Q99")])
    save(events, "relations", [])
    receipt = dict(
        status="NATIVE_EVENT_RELATIONS_READY",
        scope="3",
        inputs={
            str((core / "manifest.json").resolve()): sha256(core / "manifest.json")
        },
        outputs={p.name: sha256(p) for p in events.glob("*.json.gz")},
    )
    (events / "receipt.json").write_text(json.dumps(receipt))
    result = assemble(core, events, tmp_path / "complete")
    assert result["counts"]["entities"] == len(tables["entities"]) + 1
    assert result["counts"]["events"] == 1 and result["pending"] == ["Geography"]
    save(events, "events", [dict(event_id="Q98")])
    receipt["outputs"]["events.json.gz"] = sha256(events / "events.json.gz")
    (events / "receipt.json").write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="Event"):
        assemble(core, events, tmp_path / "bad")
    assert not (tmp_path / "bad").exists()

    # A valid receipt for another run must not be accepted because pages overlap.
    receipt["inputs"] = {}
    (events / "receipt.json").write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="exact core"):
        assemble(core, events, tmp_path / "stale")
    manifest = json.loads((core / "manifest.json").read_text())
    manifest["processing_stage"] = "model"
    (core / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="must be final"):
        assemble(core, events, tmp_path / "pending")


@pytest.mark.parametrize(
    "changed",
    [
        None,
        "scope_manifest_sha256",
        "original_input_sha256",
        "original_mentions_sha256",
    ],
)
def test_approval_binds_input_and_scope(tmp_path, changed):
    from GG_Data.pipeline.post_qid_run import validate_approval_input

    scope = tmp_path / "scope.json"
    scope.write_text(
        json.dumps(
            dict(
                original_input_sha256="input",
                inputs={"selected_mentions.parquet": "rows"},
            )
        )
    )
    approved = dict(
        scope_manifest_sha256=sha256(scope),
        original_input_sha256="input",
        original_mentions_sha256="rows",
    )
    if changed:
        approved[changed] = "different"
    manifest = tmp_path / "approved.json"
    manifest.write_text(json.dumps(approved))
    if changed:
        with pytest.raises(ValueError, match="input or frozen scope differs"):
            validate_approval_input(manifest, scope)
    else:
        validate_approval_input(manifest, scope)
