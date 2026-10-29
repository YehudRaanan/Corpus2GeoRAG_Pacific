"""Frozen membership must not depend on model output or discard revisions."""

import pytest

from GG_Data.pipeline.post_qid_run import freeze_scopes


def test_legacy_gate_uses_archived_model_and_restores_imports(tmp_path):
    import sys

    from GG_Data.pipeline.post_qid_run import archived_readiness

    name = "GG_Data.entity_resolution.hundred_page_pilot.model"
    previous = sys.modules.get(name)
    model = tmp_path / "model.py"
    model.write_text('STOP_SENTENCE = "archived stop text"\n')
    gate = tmp_path / "readiness.py"
    gate.write_text(f"from {name} import STOP_SENTENCE\n")
    assert archived_readiness(gate, model)["STOP_SENTENCE"] == "archived stop text"
    assert sys.modules.get(name) is previous


@pytest.fixture
def core_inputs(tmp_path):
    import json

    import pyarrow as pa
    import pyarrow.parquet as pq

    from GG_Data.entity_resolution.luke_pilot.data import sha256

    source, scope, inference, native, model = [
        tmp_path / n for n in ("input", "scope", "inference", "native", "model")
    ]
    for p in (source, scope, inference, native, model, source / "matching_k80_v2"):
        p.mkdir(exist_ok=True)

    def save(path, value):
        path.write_text(json.dumps(value), encoding="utf8")

    def lines(path, values):
        path.write_text("".join(json.dumps(v) + "\n" for v in values), encoding="utf8")

    rows = [
        dict(
            source_row_index=i,
            page_id=p,
            revision_id=r,
            word=w,
            entity_group=t,
            Source=f"P{p}",
            Text=w,
            Index=1,
            start=0,
            end=len(w),
        )
        for i, p, r, w, t in (
            (0, 1, 10, "A", "DATE"),
            (1, 1, 11, "A", "DATE"),
            (2, 2, 20, "B", "PER"),
            (3, 3, 30, "C", "LOC"),
        )
    ]
    groups = [
        dict(
            id=f"g{i}",
            page_id=r["page_id"],
            revision_id=r["revision_id"],
            name=r["word"],
            type=r["entity_group"],
            source_row_indices=[i],
        )
        for i, r in enumerate(rows)
    ]
    revisions = []
    for row in rows:
        p = source / f"{row['revision_id']}.txt"
        p.write_bytes(b"content")
        revisions.append(
            dict(
                page_id=row["page_id"],
                revision_id=row["revision_id"],
                wiki_title=row["Source"],
                wikitext_path=str(p),
                sha256=sha256(p),
            )
        )
    pq.write_table(pa.Table.from_pylist(rows), source / "selected_mentions.parquet")
    pq.write_table(pa.Table.from_pylist(revisions), source / "revisions.parquet")
    exact = [
        dict(group_id="g0", qid="Q2", method="exact"),
        dict(group_id="g2", qid="Q1", method="exact"),
    ]
    pq.write_table(
        pa.Table.from_pylist(exact), source / "matching_k80_v2/exact_pairs.parquet"
    )
    lines(source / "matching_k80_v2/groups.jsonl", groups)
    job = dict(
        id="job",
        page_id=1,
        revision_id=10,
        qid="Q1",
        excluded_count=0,
        candidates=[dict(id="g0", type="DATE")],
    )
    lines(source / "matching_k80_v2/jobs.jsonl", [job])
    lines(scope / "jobs_3.jsonl", [job])
    save(source / "selection.json", {"input_sha256": "a" * 64})
    files = [
        "selection.json",
        "selected_mentions.parquet",
        "revisions.parquet",
        "matching_k80_v2/groups.jsonl",
        "matching_k80_v2/jobs.jsonl",
        "matching_k80_v2/exact_pairs.parquet",
    ]
    save(
        scope / "scope_manifest.json",
        dict(
            original_input_sha256="a" * 64,
            scopes={
                "3": dict(
                    page_ids=[1, 2, 3],
                    used_revisions=[[1, 10], [1, 11], [2, 20], [3, 30]],
                    original_rows=4,
                )
            },
            inputs={f: sha256(source / f) for f in files},
        ),
    )
    from GG_Data.entity_resolution.hundred_page_pilot import readiness
    from GG_Data.entity_resolution.hundred_page_pilot.test_readiness import evidence

    checkpoint, gate_paths, training_inputs = evidence.__wrapped__(model)
    training_dir = source / "training_k80_v2"
    training_inputs.rename(training_dir)
    gate_paths["public_manifest"] = training_dir / "public_manifest.json"
    archive = scope / "code_archive"
    archive.mkdir()
    for role, name in {
        "training_code": "train.py",
        "inference_code": "resolve_entities.py",
        "model_code": "model.py",
        "readiness_code": "readiness.py",
    }.items():
        (archive / name).write_bytes(gate_paths[role].read_bytes())
    metrics = json.loads(gate_paths["held_out_metrics"].read_text())
    metrics.update(predicted_stops=0, correct_stops=0)
    save(gate_paths["held_out_metrics"], metrics)
    inspected = json.loads(gate_paths["checkpoint_inspection"].read_text())
    inspected["final_artifact_hashes"]["held_out_metrics"] = sha256(
        gate_paths["held_out_metrics"]
    )
    save(gate_paths["checkpoint_inspection"], inspected)
    save(
        model / "readiness.json",
        readiness.build_readiness(checkpoint, gate_paths, training_dir),
    )
    save(
        model / "experimental_three_page_approval.json",
        dict(
            approved_by="OWNER",
            scope="experimental_three_pages",
            decision="Allow the experimental three-page run with this model",
            checkpoint_sha256=sha256(model / "full_best.pt"),
            jobs_sha256=sha256(scope / "jobs_3.jsonl"),
            page_ids=[1, 2, 3],
        ),
    )
    signature = dict(
        jobs_sha256=sha256(scope / "jobs_3.jsonl"),
        checkpoint_sha256=sha256(model / "full_best.pt"),
        readiness_sha256=sha256(model / "readiness.json"),
        experimental_approval_sha256=sha256(
            model / "experimental_three_page_approval.json"
        ),
    )
    save(inference / "inference_inputs.json", signature)
    save(inference / "inference_summary.json", dict(questions=1, **signature))
    lines(
        inference / "scores.jsonl",
        [dict(id="job", options=[dict(id="g0", score=2), dict(id=None, score=1)])],
    )
    lines(
        inference / "model_pairs.jsonl",
        [
            dict(
                id="job",
                page_id=1,
                revision_id=10,
                qid="Q1",
                group_id="g0",
                entity_group="DATE",
                method="model",
            )
        ],
    )
    lines(
        inference / "decisions.jsonl",
        [
            dict(
                id="job",
                page_id=1,
                revision_id=10,
                qid="Q1",
                step=0,
                decision="select",
                group_id="g0",
                score=2,
                stop_score=1,
                remaining_count=1,
                excluded_count=0,
            ),
            dict(
                id="job",
                page_id=1,
                revision_id=10,
                qid="Q1",
                step=1,
                decision="stop",
                group_id=None,
                score=1,
                remaining_count=0,
                excluded_count=0,
            ),
        ],
    )
    import gzip

    with gzip.open(native / "full_records.json.gz", "wt", encoding="utf8") as stream:
        json.dump(
            {
                q: dict(
                    requested_qid=q,
                    entity=dict(id=q, claims={}, labels={"en": {"value": q}}),
                )
                for q in ("Q1", "Q2")
            },
            stream,
        )
    save(native / "sources.json", {q: dict(provider="FIXTURE") for q in ("Q1", "Q2")})
    return source, scope, inference, native, model, tmp_path / "output"


def test_core_preserves_rows_revision_fks_and_typed_qid_importance(core_inputs):
    import gzip
    import json

    from GG_Data.pipeline.post_qid_run import build_core

    source, scope, inference, native, model, output = core_inputs
    original_readiness = (model / "readiness.json").read_bytes()
    manifest = build_core(source, scope, inference, native, output, model_dir=model)
    assert (model / "readiness.json").read_bytes() == original_readiness
    assert manifest["locally_observed_readiness"]["technical_status"] == "PASS"
    assert manifest["status"] == "CORE_COMPLETE_GEOGRAPHY_PENDING"
    tables = {
        n: json.load(gzip.open(output / f"{n}.json.gz", "rt", encoding="utf8"))
        for n in ("wiki_pages", "entities", "mentions", "mention_entity_links")
    }
    assert (
        len(tables["mentions"]) == 4
        and len(tables["wiki_pages"]) == 4
        and len(tables["mention_entity_links"]) == 5
    )
    q1 = [r for r in tables["entities"] if r["entity_id"] == "Q1"]
    assert {r["type"] for r in q1} == {"DATE", "PER"}
    assert all(
        r["importance"] == 4
        and r["unique_original_mention_count"] == 2
        and r["attributes"]["normalized_mention_frequency"] == 0.5
        for r in q1
    )
    model_link = next(
        r for r in tables["mention_entity_links"] if r["method"] == "model"
    )
    assert model_link["evidence"][0]["decision_reference"]["step"] == 0
    assert model_link["evidence"][0]["run_id"]


@pytest.mark.parametrize(
    "corruption",
    [
        "missing_score",
        "changed_scope_input",
        "outside_pair",
        "changed_decision",
        "missing_native",
        "changed_approval",
        "changed_checkpoint",
    ],
)
def test_core_rejects_corrupt_evidence_before_output(core_inputs, corruption):
    import gzip
    import json

    from GG_Data.pipeline.post_qid_run import build_core

    source, scope, inference, native, model, output = core_inputs
    if corruption == "missing_score":
        (inference / "scores.jsonl").write_text("")
    elif corruption == "changed_scope_input":
        (source / "selection.json").write_text("{}")
    elif corruption == "outside_pair":
        p = inference / "model_pairs.jsonl"
        d = json.loads(p.read_text())
        d["group_id"] = "g1"
        p.write_text(json.dumps(d) + "\n")
    elif corruption == "changed_decision":
        p = inference / "decisions.jsonl"
        p.write_text(p.read_text().replace('"step": 0', '"step": 9'))
    elif corruption == "missing_native":
        with gzip.open(native / "full_records.json.gz", "wt") as stream:
            json.dump({}, stream)
    elif corruption == "changed_approval":
        (model / "experimental_three_page_approval.json").write_text("{}")
    elif corruption == "changed_checkpoint":
        (model / "full_best.pt").write_bytes(b"wrong")
    with pytest.raises(ValueError):
        build_core(source, scope, inference, native, output, model_dir=model)
    assert not output.exists()


@pytest.mark.parametrize(
    "corruption",
    [
        "missing_input_binding",
        "changed_code_archive",
        "failed_technical",
        "incomplete_options",
        "duplicate_score",
        "missing_readiness_role",
        "tampered_metric",
    ],
)
def test_core_rejects_missing_bindings_and_partial_questions(core_inputs, corruption):
    import json

    from GG_Data.entity_resolution.luke_pilot.data import sha256
    from GG_Data.pipeline.post_qid_run import build_core

    source, scope, inference, native, model, output = core_inputs
    if corruption == "missing_input_binding":
        p = scope / "scope_manifest.json"
        d = json.loads(p.read_text())
        del d["inputs"]["selected_mentions.parquet"]
        p.write_text(json.dumps(d))
    elif corruption == "changed_code_archive":
        (scope / "code_archive/resolve_entities.py").write_text("changed")
    elif corruption == "failed_technical":
        p = model / "readiness.json"
        d = json.loads(p.read_text())
        d["technical_status"] = "FAIL"
        p.write_text(json.dumps(d))
        p = inference / "inference_inputs.json"
        d = json.loads(p.read_text())
        d["readiness_sha256"] = sha256(model / "readiness.json")
        p.write_text(json.dumps(d))
    elif corruption == "incomplete_options":
        p = inference / "scores.jsonl"
        d = json.loads(p.read_text())
        d["options"].pop()
        p.write_text(json.dumps(d) + "\n")
    elif corruption == "missing_readiness_role":
        p = model / "readiness.json"
        d = json.loads(p.read_text())
        del d["files"]["restore_check"]
        p.write_text(json.dumps(d))
        p = inference / "inference_inputs.json"
        d = json.loads(p.read_text())
        d["readiness_sha256"] = sha256(model / "readiness.json")
        p.write_text(json.dumps(d))
        p = inference / "inference_summary.json"
        d = json.loads(p.read_text())
        d["readiness_sha256"] = sha256(model / "readiness.json")
        p.write_text(json.dumps(d))
    elif corruption == "tampered_metric":
        p = model / "held_out_metrics.json"
        p.write_text("{}")
    else:
        p = inference / "scores.jsonl"
        p.write_text(p.read_text() * 2)
    with pytest.raises(ValueError):
        build_core(source, scope, inference, native, output, model_dir=model)
    assert not output.exists()


def test_nested_pages_preserve_every_used_revision():
    rows = [dict(Source=f"p{i}", page_id=i, revision_id=100 + i) for i in range(1, 13)]
    rows.append(dict(Source="p1", page_id=1, revision_id=999))
    result = freeze_scopes(rows, [f"p{i}" for i in range(1, 11)])
    assert set(result["3"]["page_ids"]) <= set(result["10"]["page_ids"])
    assert len(result["3"]["page_ids"]) == 3
    assert result["10"]["page_ids"] == list(range(1, 11))
    assert (1, 999) in result["10"]["used_revisions"]
    assert len(result["100"]["page_ids"]) == 12


def test_missing_or_ambiguous_prior_title_fails():
    with pytest.raises(ValueError, match="one page"):
        freeze_scopes([dict(Source="p", page_id=1, revision_id=2)], ["missing"])


def test_missing_old_titles_fill_only_from_saved_sample_order():
    rows = [dict(Source=f"p{i}", page_id=i, revision_id=100 + i) for i in range(1, 13)]
    result = freeze_scopes(
        rows, ["p1", "p2", "p3", "absent"], [f"p{i}" for i in range(1, 13)]
    )
    assert result["3"]["page_ids"] == [1, 2, 3]
    assert result["10"]["page_ids"] == list(range(1, 11))
