"""Focused Laya pipeline/evaluation contracts; no real model or network."""

from __future__ import annotations

import json


def test_forward_chunk_cache_streams_binds_and_rejects_drift(tmp_path, monkeypatch):
    import pytest
    from GG_Data.entity_resolution.hundred_page_pilot import run_laya
    from GG_Data.entity_resolution.laya_model import model
    from GG_Data.entity_resolution.luke_pilot.data import sha256, write_jsonl

    prepared = tmp_path / "prepared"
    prepared.mkdir()
    jobs = [dict(id=str(i), direction="forward", candidates=[]) for i in range(101)]
    write_jsonl(prepared / "forward_jobs.jsonl", jobs)
    manifest = dict(
        files={"forward_jobs.jsonl": sha256(prepared / "forward_jobs.jsonl")}
    )
    (prepared / "manifest.json").write_text(json.dumps(manifest))
    original = (prepared / "manifest.json").read_bytes()
    tokenizer = tmp_path / "tokenizer"
    tokenizer.mkdir()
    (tokenizer / "tokenizer.json").write_text("saved tokenizer")
    monkeypatch.setattr(run_laya, "load_local_tokenizer", lambda _path: object())
    monkeypatch.setattr(
        model,
        "partition_record",
        lambda record, direction, **kwargs: [
            dict(record, chunk_index=0, chunk_count=1)
        ],
    )
    cache = tmp_path / "cache"
    result = run_laya.prepare_chunk_cache(prepared, tokenizer, cache)
    assert result["jobs"] == 101 and result["chunks"] == 101
    assert json.loads((cache / "progress.json").read_text())["status"] == "complete"
    hashes = {"tokenizer/" + p.name: sha256(p) for p in tokenizer.iterdir()}
    loaded = run_laya.load_chunk_cache(
        prepared, cache, {"checkpoint_files": hashes}, {"1", "99"}
    )
    assert set(loaded) == {"1", "99"}
    assert loaded["1"][0]["id"] == "1"
    assert (prepared / "manifest.json").read_bytes() == original
    with pytest.raises(FileExistsError):
        run_laya.prepare_chunk_cache(prepared, tokenizer, cache)
    with pytest.raises(ValueError, match="binding"):
        run_laya.load_chunk_cache(
            prepared, cache, {"checkpoint_files": hashes}, {"1"}, max_options=19
        )
    with pytest.raises(ValueError, match="tokenizer"):
        run_laya.load_chunk_cache(
            prepared,
            cache,
            {"checkpoint_files": {"tokenizer/tokenizer.json": "changed"}},
            {"1"},
        )
    with (cache / "forward_chunks.jsonl").open("a") as stream:
        stream.write("{}\n")
    with pytest.raises(ValueError, match="hash"):
        run_laya.load_chunk_cache(prepared, cache, {"checkpoint_files": hashes}, {"1"})


def test_reverse_checks_assigned_groups_and_only_uncovered_qids():
    from GG_Data.entity_resolution.hundred_page_pilot.run_laya import reverse_jobs

    groups = [
        dict(
            id="g1", page_id=1, revision_id=2, name="Alpha", type="ORG", context="Alpha"
        ),
        dict(
            id="g2", page_id=1, revision_id=2, name="Beta", type="PER", context="Beta"
        ),
    ]
    entities = [
        dict(
            qid="Q1",
            page_id=1,
            revision_id=2,
            label="Alpha",
            type_categories=["ORG"],
            type_unknown=False,
        ),
        dict(
            qid="Q2",
            page_id=1,
            revision_id=2,
            label="Other",
            type_categories=["ORG"],
            type_unknown=False,
        ),
    ]
    pairs = [dict(page_id=1, revision_id=2, group_id="g1", qid="Q1")]
    jobs = reverse_jobs(groups, entities, pairs)
    assert len(jobs) == 1
    assert jobs[0]["group_id"] == "g1"  # Already assigned remains eligible.
    assert [c["id"] for c in jobs[0]["candidates"]] == ["Q2"]
    assert jobs[0]["entity"]["name"] == "Alpha"


def test_metrics_accept_multi_positive_and_report_unrun_and_ci():
    from GG_Data.entity_resolution.laya_model.evaluate import evaluate_records

    records = [
        dict(
            id="a",
            direction="forward",
            candidates=[dict(id="a"), dict(id="b")],
            positive_ids=["a", "b"],
            full_positive_ids=["a", "b"],
        ),
        dict(id="b", direction="forward", candidates=[dict(id="z")], positive_ids=[]),
        dict(
            id="c", direction="forward", candidates=[dict(id="x")], positive_ids=["x"]
        ),
        dict(id="d", direction="reverse", candidates=[], positive_ids=[]),
    ]
    metrics = evaluate_records(
        records,
        [
            dict(id="a", candidate_id="b"),
            dict(id="b", candidate_id=None),
            dict(id="d", candidate_id=None),
        ],
    )
    forward = metrics["directions"]["forward"]
    assert forward["valid_set_accuracy"]["numerator"] == 2
    assert forward["valid_set_accuracy"]["denominator"] == 2
    assert forward["not_run"] == 1
    assert forward["stop_precision"]["value"] == 1.0
    assert forward["stop_recall"]["value"] == 1.0
    assert forward["valid_set_accuracy"]["ci95"][0] < 1.0
    assert metrics["directions"]["reverse"]["records"] == 1


def test_metrics_distinguish_retrieval_misses_and_reject_stale_ids():
    import pytest
    from GG_Data.entity_resolution.laya_model.evaluate import evaluate_records

    record = dict(
        id="a",
        direction="forward",
        candidates=[dict(id="x")],
        positive_ids=[],
        full_positive_ids=["missing"],
    )
    metric = evaluate_records([record], [dict(id="a", candidate_id=None)])[
        "directions"
    ]["forward"]
    assert metric["candidate_coverage"]["numerator"] == 0
    assert metric["candidate_coverage"]["denominator"] == 1
    assert metric["stop_precision"]["numerator"] == 0
    with pytest.raises(ValueError, match="candidate"):
        evaluate_records([record], [dict(id="a", candidate_id="stale")])


def test_compare_pairs_retains_many_to_many_identity():
    from GG_Data.entity_resolution.laya_model.evaluate import compare_pairs

    old = [dict(page_id=1, revision_id=2, group_id="g", qid="Q1")]
    new = old + [dict(page_id=1, revision_id=2, group_id="g", qid="Q2")]
    result = compare_pairs(new, old)
    assert result["added_pairs"] == 1
    assert result["lost_pairs"] == 0
    assert result["changed_groups"] == 1
    assert result["added_examples"][0]["qid"] == "Q2"


def test_evaluation_removal_states_use_remaining_full_gold():
    from GG_Data.entity_resolution.laya_model.evaluate import evaluate_records

    record = dict(
        id="a",
        direction="reverse",
        candidates=[dict(id="x")],
        positive_ids=[],
        full_positive_ids=["removed"],
        removed_ids=["removed"],
    )
    metric = evaluate_records([record], [dict(id="a", candidate_id=None)])[
        "directions"
    ]["reverse"]
    assert metric["stop_precision"]["value"] == 1.0
    assert metric["candidate_coverage"]["denominator"] == 0


def test_trace_rejects_missing_stop_and_unpresented_candidates():
    import pytest
    from GG_Data.entity_resolution.hundred_page_pilot.run_laya import validate_trace

    job = dict(id="a", candidates=[dict(id="x"), dict(id="y")])
    with pytest.raises(ValueError, match="complete|STOP|coverage"):
        validate_trace(
            job,
            dict(
                id="a",
                trace=[
                    dict(
                        candidate_id="x",
                        chunk_index=0,
                        chunk_count=1,
                        remaining_ids=["x", "y"],
                    )
                ],
            ),
        )
    with pytest.raises(ValueError, match="complete|STOP|coverage"):
        validate_trace(
            job,
            dict(
                id="a",
                trace=[
                    dict(
                        candidate_id=None,
                        chunk_index=0,
                        chunk_count=1,
                        remaining_ids=["x"],
                    )
                ],
            ),
        )


def test_full_pipeline_keeps_all_rows_and_adds_reverse_to_assigned_group(
    tmp_path, monkeypatch
):
    import pyarrow as pa
    import pyarrow.parquet as pq
    from GG_Data.entity_resolution.hundred_page_pilot.run_laya import (
        prepare_chunk_cache,
        prepare_run,
        run_scope,
    )
    from GG_Data.entity_resolution.laya_model import model
    from GG_Data.entity_resolution.luke_pilot.data import read_jsonl

    monkeypatch.setattr(
        model, "token_diagnostics", lambda *_args, **_kwargs: {"fits": True}
    )

    class FakeAgent:
        tok = object()

        def __init__(self):
            self.questions = []

        def system_one(self, state, questions, **_kwargs):
            self.questions.append((state, questions))
            keys = list(questions["match"]["criteria"])
            choice = (
                keys[0]
                if state.startswith("Query mention: Alpha") and len(keys) > 1
                else model.STOP_KEY
            )
            return dict(
                answers=dict(
                    match=dict(
                        choice=choice,
                        probabilities={k: float(k == choice) for k in keys},
                    )
                )
            )

    rows, entities = [], []
    for page in range(1, 101):
        for name, kind in (
            ("Alpha", "ORG"),
            ("Beta", "ORG"),
            ("Date", "DATE"),
            ("Excluded", "ORG"),
        ):
            rows.append(
                dict(
                    page_id=page,
                    revision_id=page + 100,
                    entity_group=kind,
                    word=name,
                    Text=name,
                    start=0,
                    end=len(name),
                    source_row_index=len(rows),
                    occurrence_id=f"occ-{len(rows)}",
                    source_scope_policy_version="article-source-v3",
                    source_scope_context=name,
                    source_scope_status=(
                        "EXCLUDE"
                        if name == "Excluded"
                        else "REVIEW" if name == "Beta" else "KEEP"
                    ),
                    clean_status="excluded" if name == "Excluded" else "mapped",
                    Text_clean=name,
                    clean_start=0,
                    clean_end=len(name),
                    clean_source_status="unique_raw_placement",
                    clean_revision_sha256="saved",
                )
            )
        entities.extend(
            [
                dict(
                    page_id=page,
                    revision_id=page + 100,
                    qid=qid,
                    label=name,
                    aliases=[],
                    linked_titles=[],
                    qid_source_status="KEEP",
                    type_categories=["ORG"],
                    type_unknown=False,
                    qid_filter_policy_version="qid-source-native-types-v1",
                )
                for qid, name in (("Q1", "Alpha"), ("Q2", "Other"))
            ]
        )
    mentions, inventory, scopes = (
        tmp_path / "mentions.parquet",
        tmp_path / "entities.parquet",
        tmp_path / "scopes.json",
    )
    pq.write_table(pa.Table.from_pylist(rows), mentions)
    pq.write_table(pa.Table.from_pylist(entities), inventory)
    scopes.write_text(
        json.dumps(
            {
                "scopes": {
                    str(n): dict(
                        page_ids=list(range(1, n + 1)),
                        used_revisions=[[p, p + 100] for p in range(1, n + 1)],
                    )
                    for n in (3, 10, 100)
                }
            }
        )
    )
    original = mentions.read_bytes()
    prepared = tmp_path / "prepared"
    manifest = prepare_run(mentions, inventory, scopes, prepared)
    assert manifest["input_rows"] == 400
    assert manifest["forward_preparation"]["matching_eligible_rows"] == 200
    uncached_agent = FakeAgent()
    result = run_scope(
        prepared,
        tmp_path / "results",
        uncached_agent,
        3,
        max_seconds=60,
        checkpoint_binding={"fake": "test"},
    )
    assert result["input_rows"] == 12
    assert result["eligible_occurrences"] == 6
    assert result["excluded_rows"] == 3
    assert result["date_deferred_rows"] == 3
    assert result["groups_with_multiple_qids"] == 3
    assert result["proposal_pairs"] == 6
    assert result["assigned_mentions"] == 3
    assert result["unresolved_mentions"] == 3
    reverse = read_jsonl(tmp_path / "results/reverse_jobs.jsonl")
    assert len(reverse) == 6  # Includes exact-assigned Alpha and REVIEW Beta.
    assert all([c["id"] for c in j["candidates"]] == ["Q2"] for j in reverse)
    before = (tmp_path / "results/forward_traces.jsonl").read_bytes()
    assert (
        run_scope(
            prepared,
            tmp_path / "results",
            FakeAgent(),
            3,
            max_seconds=60,
            checkpoint_binding={"fake": "test"},
        )
        == result
    )
    assert (tmp_path / "results/forward_traces.jsonl").read_bytes() == before
    assert mentions.read_bytes() == original

    from GG_Data.entity_resolution.hundred_page_pilot import run_laya
    from GG_Data.entity_resolution.luke_pilot.data import sha256

    tokenizer_path = tmp_path / "tokenizer"
    tokenizer_path.mkdir()
    (tokenizer_path / "tokenizer.json").write_text("saved tokenizer")
    monkeypatch.setattr(run_laya, "load_local_tokenizer", lambda _path: object())
    prepare_chunk_cache(prepared, tokenizer_path, tmp_path / "chunks")
    cached_agent = FakeAgent()
    cached = run_scope(
        prepared,
        tmp_path / "cached-results",
        cached_agent,
        3,
        max_seconds=60,
        checkpoint_binding={
            "checkpoint_files": {
                "tokenizer/tokenizer.json": sha256(tokenizer_path / "tokenizer.json")
            }
        },
        chunk_cache=tmp_path / "chunks",
    )
    assert cached_agent.questions == uncached_agent.questions
    assert {k: v for k, v in cached.items() if k != "elapsed_seconds"} == {
        k: v for k, v in result.items() if k != "elapsed_seconds"
    }
    for name in ("forward_traces.jsonl", "reverse_traces.jsonl", "proposals.jsonl"):
        assert read_jsonl(tmp_path / "cached-results" / name) == read_jsonl(
            tmp_path / "results" / name
        )


def test_evaluate_agent_reports_local_stop_and_source_recovery_with_unknowns(
    tmp_path, monkeypatch
):
    from GG_Data.entity_resolution.laya_model import model
    from GG_Data.entity_resolution.laya_model.evaluate import evaluate_agent

    def chunks(records, **_kwargs):
        result = []
        for record in records:
            for index, candidate in enumerate(record["candidates"]):
                positives = (
                    [candidate["id"]]
                    if candidate["id"] in record["positive_ids"]
                    else []
                )
                result.append(
                    dict(
                        record,
                        candidates=[candidate],
                        positive_ids=positives,
                        chunk_index=index,
                        chunk_count=len(record["candidates"]),
                    )
                )
        return result

    monkeypatch.setattr(model, "partition_removal_states", chunks)

    class FakeAgent:
        tok = object()
        calls = 0

        def system_one(self, state, questions, **_kwargs):
            assert set(questions) == {"match"}  # No gold is passed.
            keys = list(questions["match"]["criteria"])
            choice = keys[0] if self.calls < 2 else model.STOP_KEY
            self.calls += 1
            return dict(
                answers=dict(
                    match=dict(
                        choice=choice,
                        probabilities={k: float(k == choice) for k in keys},
                    )
                )
            )

    records = [
        dict(
            id="a",
            direction="forward",
            entity=dict(name="Alpha"),
            candidates=[dict(id="yes", name="Alpha"), dict(id="unknown", name="Other")],
            positive_ids=["yes"],
            full_positive_ids=["yes"],
        ),
        dict(
            id="b",
            direction="reverse",
            entity=dict(name="Beta"),
            candidates=[dict(id="no", name="Other")],
            positive_ids=[],
        ),
    ]
    agent = FakeAgent()
    result = evaluate_agent(
        agent,
        records,
        tmp_path / "evaluation",
        max_seconds=30,
        checkpoint_binding={"fake": True},
    )
    assert result["status"] == "complete"
    assert (
        result["chunk_metrics"]["directions"]["forward"]["valid_set_accuracy"][
            "numerator"
        ]
        == 1
    )
    assert (
        result["source_state_metrics"]["forward"]["positive_state_recovery"]["value"]
        == 1.0
    )
    assert (
        result["source_state_metrics"]["forward"]["selected_unannotated_candidates"]
        == 1
    )
    assert (
        result["source_state_metrics"]["forward"][
            "success_without_unannotated_selection"
        ]["value"]
        == 0.0
    )
    assert (
        result["source_state_metrics"]["reverse"]["terminal_all_chunks_stop"]["value"]
        == 1.0
    )
    assert result["source_not_run_ids"] == []
    assert agent.calls == 3
    assert (
        evaluate_agent(
            agent,
            records,
            tmp_path / "evaluation",
            max_seconds=30,
            checkpoint_binding={"fake": True},
        )
        == result
    )
    assert agent.calls == 3

    import pytest
    from GG_Data.entity_resolution.luke_pilot.data import read_jsonl

    saved_chunks = read_jsonl(tmp_path / "evaluation/chunk_records.jsonl")
    saved_chunks[0]["positive_ids"] = []
    (tmp_path / "evaluation/chunk_records.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in saved_chunks)
    )
    with pytest.raises(ValueError, match="chunk|gold|positive"):
        evaluate_agent(
            agent,
            records,
            tmp_path / "evaluation",
            max_seconds=30,
            checkpoint_binding={"fake": True},
        )
    saved_chunks[0]["positive_ids"] = ["yes"]
    (tmp_path / "evaluation/chunk_records.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in saved_chunks)
    )
    saved_predictions = read_jsonl(tmp_path / "evaluation/predictions.jsonl")
    saved_predictions[0]["candidate_id"] = None
    (tmp_path / "evaluation/predictions.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in saved_predictions)
    )
    with pytest.raises(ValueError, match="prediction|probabilit"):
        evaluate_agent(
            agent,
            records,
            tmp_path / "evaluation",
            max_seconds=30,
            checkpoint_binding={"fake": True},
        )


def test_evaluate_agent_budget_reports_all_unrun_source_ids(tmp_path, monkeypatch):
    from GG_Data.entity_resolution.laya_model import evaluate
    from GG_Data.entity_resolution.laya_model.evaluate import evaluate_agent

    ticks = iter([0.0, 1.0])
    monkeypatch.setattr(evaluate.time, "monotonic", lambda: next(ticks, 1.0))

    record = dict(
        id="a",
        direction="forward",
        entity=dict(name="Alpha"),
        candidates=[],
        positive_ids=[],
    )
    result = evaluate_agent(
        object(),
        [record],
        tmp_path / "evaluation",
        max_seconds=1e-12,
        checkpoint_binding={"fake": True},
    )
    assert result["status"] == "resource_limit"
    assert result["source_not_run_ids"] == ["a"]
    assert result["source_state_metrics"]["forward"]["fully_run"] == 0


def test_scope_rejects_unbound_saved_traces(tmp_path):
    import pytest
    from GG_Data.entity_resolution.hundred_page_pilot.run_laya import run_scope

    prepared = tmp_path / "prepared"
    prepared.mkdir()
    (prepared / "manifest.json").write_text(json.dumps(dict(files={})))
    output = tmp_path / "output"
    output.mkdir()
    (output / "forward_traces.jsonl").write_text('{"id":"stale","trace":[]}\n')
    with pytest.raises(ValueError, match="binding|receipt"):
        run_scope(
            prepared,
            output,
            object(),
            3,
            max_seconds=10,
            checkpoint_binding={"different": "weights"},
        )


def test_evaluation_resume_binds_canonical_model_code(tmp_path, monkeypatch):
    import pytest
    from GG_Data.entity_resolution.laya_model import evaluate

    output = tmp_path / "evaluation"
    evaluate.evaluate_agent(
        object(), [], output, max_seconds=30, checkpoint_binding={"fake": True}
    )
    real_hash = evaluate.sha256
    monkeypatch.setattr(
        evaluate,
        "sha256",
        lambda p: "changed-model" if p.name == "model.py" else real_hash(p),
    )
    with pytest.raises(ValueError, match="binding"):
        evaluate.evaluate_agent(
            object(), [], output, max_seconds=30, checkpoint_binding={"fake": True}
        )


def test_trace_rejects_corrupt_saved_probabilities():
    import pytest
    from GG_Data.entity_resolution.hundred_page_pilot.run_laya import validate_trace

    trace = dict(
        candidate_id=None,
        chunk_index=0,
        chunk_count=1,
        remaining_ids=["x"],
        option_ids={"candidate": "x", "STOP": None},
        choice="STOP",
        stop=True,
        probabilities={"candidate": float("nan"), "STOP": 1.0},
    )
    with pytest.raises(ValueError, match="probabilit|option"):
        validate_trace(
            dict(id="a", candidates=[dict(id="x")]), dict(id="a", trace=[trace])
        )


def test_evaluation_uses_fixed_initial_chunks_for_later_removal_states(
    tmp_path, monkeypatch
):
    from GG_Data.entity_resolution.laya_model import model
    from GG_Data.entity_resolution.laya_model.evaluate import evaluate_agent
    from GG_Data.entity_resolution.luke_pilot.data import read_jsonl

    monkeypatch.setattr(model, "token_diagnostics", lambda *_a, **_k: {"fits": True})
    candidates = [dict(id=x, name=x) for x in ("a", "b", "c")]
    records = [
        dict(
            id="initial",
            base_id="base",
            removal_index=0,
            direction="forward",
            entity=dict(name="Query"),
            candidates=candidates,
            positive_ids=["a", "b"],
        ),
        dict(
            id="removed",
            base_id="base",
            removal_index=1,
            direction="forward",
            entity=dict(name="Query"),
            candidates=candidates[1:],
            positive_ids=["b"],
            removed_ids=["a"],
        ),
    ]

    class FakeAgent:
        tok = object()

        def system_one(self, _state, questions, **_kw):
            keys = questions["match"]["criteria"]
            return dict(
                answers=dict(
                    match=dict(
                        choice="STOP",
                        probabilities={k: float(k == "STOP") for k in keys},
                    )
                )
            )

    evaluate_agent(
        FakeAgent(),
        records,
        tmp_path / "evaluation",
        max_seconds=30,
        checkpoint_binding={"fake": True},
        max_options=2,
    )
    chunks = [
        c
        for c in read_jsonl(tmp_path / "evaluation/chunk_records.jsonl")
        if c["source_record_id"] == "removed"
    ]
    assert [[c["id"] for c in chunk["candidates"]] for chunk in chunks] == [
        ["b"],
        ["c"],
    ]
