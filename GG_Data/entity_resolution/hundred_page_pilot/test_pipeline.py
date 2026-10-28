"""Small regression checks for source identity and local many-to-many decisions."""

import pytest

from GG_Data.entity_resolution.hundred_page_pilot.match import (
    exact_pairs, group_mentions, rank_candidates, select_loop)


def mention(name="Japan", kind="LOC", revision=11, row=0):
    return {
        "page_id": 1,
        "revision_id": revision,
        "word": name,
        "entity_group": kind,
        "Text": name,
        "start": 0,
        "end": len(name),
        "source_row_index": row,
    }


def entity(qid="Q17", label="Japan", revision=11):
    return {
        "page_id": 1,
        "revision_id": revision,
        "qid": qid,
        "label": label,
        "aliases": [],
        "description": "",
    }


def test_exact_requires_unique_type_and_qid_on_same_revision():
    groups = group_mentions([mention(), mention(row=1), mention(revision=12, row=2)])
    assert len(groups) == 2
    assert len(exact_pairs(groups, [entity()])) == 1
    assert not exact_pairs(groups, [entity(), entity("Q999")])
    ambiguous = group_mentions([mention(), mention(kind="MISC", row=1)])
    assert not exact_pairs(ambiguous, [entity()])
    assert not exact_pairs(groups, [entity(label="japan")])


def test_group_preserves_all_occurrences_and_literal_identity():
    groups = group_mentions([mention(), mention(row=1), mention(name="JAPAN", row=2)])
    assert sorted(len(g["source_row_indices"]) for g in groups) == [1, 2]
    assert len({g["id"] for g in groups}) == 2


def test_loop_stops_on_tie_and_removal_is_local():
    scores = {"a": 3.0, "b": 2.0, "c": 1.0}
    selected, trace = select_loop(scores, 1.0)
    assert selected == ["a", "b"]
    assert trace[-1]["decision"] == "stop"
    assert select_loop(scores, 1.0)[0] == selected
    assert len(scores) == 3
    assert select_loop({}, 0.0)[0] == []
    with pytest.raises(ValueError, match="finite"):
        select_loop({"a": float("nan")}, 0.0)


def test_candidates_are_page_and_revision_local_and_keep_many_to_many():
    groups = group_mentions(
        [mention(), mention(name="Japanese", row=1), mention(revision=12, row=2)]
    )
    ranked = rank_candidates(entity(), groups, count=0)
    assert len(ranked) == 2
    assert ranked[0]["name"] == "Japan"
    assert all(g["revision_id"] == 11 for g in ranked)
    assert rank_candidates(entity("Q999"), groups, count=0) == ranked


def test_raw_markup_and_damage_are_not_silently_repaired():
    from GG_Data.entity_resolution.hundred_page_pilot.prepare_pages import (
        match_method, passage_id)

    assert match_method("[[A]]", "x [[A]] y") == "EXACT_RAW_CONTAINMENT"
    assert match_method("[[A]]", "x A y") is None
    assert match_method("1938\ufffd1942", "1938–1942") is None
    assert passage_id("A", 1, "text") != passage_id("A", 2, "text")


def test_reverse_pairs_and_set_loss_keep_multiple_correct_answers():
    import torch

    from GG_Data.entity_resolution.hundred_page_pilot.model import (
        STOP_SENTENCE, marginal_set_loss, pair_texts)

    row = {
        "entity": {"name": "Japan", "qid": "Q17"},
        "candidates": [
            {"id": "a", "name": "Japan", "context": "Japan sailed"},
            {"id": "b", "name": "Japanese", "context": "Japanese ships"},
        ],
        "positive_ids": ["a", "b"],
    }
    first, second, targets = pair_texts(row)
    assert targets == [0, 1]
    assert second[-1] == STOP_SENTENCE
    assert all("Q17" not in text for text in first + second)
    logits = torch.tensor([2.0, 2.0, 0.0], requires_grad=True)
    loss = marginal_set_loss(logits, [3], [targets])
    expected = torch.logsumexp(logits, 0) - torch.logsumexp(logits[:2], 0)
    assert torch.allclose(loss, expected)
    loss.backward()
    assert torch.isfinite(logits.grad).all()
    assert (logits.grad[:2] < 0).all()
    row["positive_ids"] = []
    assert pair_texts(row)[2] == [2]


def test_freezing_encoder_controls_gradients_and_dropout():
    from types import SimpleNamespace

    import torch

    from GG_Data.entity_resolution.hundred_page_pilot.model import \
        CandidateScorer

    class Encoder(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.config = SimpleNamespace(hidden_size=4)
            self.embedding = torch.nn.Embedding(6, 4)
            self.dropout = torch.nn.Dropout(0.5)

        def forward(self, input_ids):
            return SimpleNamespace(
                last_hidden_state=self.dropout(self.embedding(input_ids))
            )

    model = CandidateScorer(Encoder())
    model.freeze_encoder(True)
    model.train()
    assert not model.encoder.training
    model(input_ids=torch.tensor([[1, 2]])).sum().backward()
    assert model.encoder.embedding.weight.grad is None
    model.freeze_encoder(False)
    model.train()
    assert model.encoder.training
    model(input_ids=torch.tensor([[1, 2]])).sum().backward()
    assert model.encoder.embedding.weight.grad is not None


def test_reference_uses_whole_anchor_and_unique_passage_placement(tmp_path):
    from GG_Data.entity_resolution.hundred_page_pilot.report import (
        freeze_reference, source_positive_metrics)

    raw = "A [[Japan]] sailed."
    path = tmp_path / "raw.txt"
    path.write_text(raw, encoding="utf-8")
    row = {**mention(), "Text": raw, "start": 4, "end": 9}
    revision = {"page_id": 1, "revision_id": 11, "wikitext_path": str(path)}
    link = {
        "page_id": 1,
        "revision_id": 11,
        "qid": "Q17",
        "anchor_text": "Japan",
        "anchor_start": 4,
        "anchor_end": 9,
        "link_origin": "RAW_DIRECT_LINK",
    }
    ref = freeze_reference([row], [revision], [link])
    assert len(ref) == 1
    metrics = source_positive_metrics(ref, ref)
    assert metrics["source_positive_recall"] == 1.0
    assert metrics["precision"] is None
    assert metrics["stop_precision"] is None
    path.write_text(raw + raw, encoding="utf-8")
    assert not freeze_reference([row], [revision], [link])


def test_export_preserves_rows_and_many_to_many_lists(tmp_path):
    import json

    import pyarrow as pa
    import pyarrow.parquet as pq

    from GG_Data.entity_resolution.hundred_page_pilot.match import identity
    from GG_Data.entity_resolution.hundred_page_pilot.report import export
    from GG_Data.entity_resolution.luke_pilot.data import sha256

    rows = [mention(), mention(row=1)]
    groups = group_mentions(rows)
    group = groups[0]["id"]
    matching, inference = tmp_path / "matching", tmp_path / "inference"
    matching.mkdir()
    inference.mkdir()
    (matching / "groups.jsonl").write_text(
        json.dumps(groups[0]) + "\n", encoding="utf-8"
    )
    pair = {
        "page_id": 1,
        "revision_id": 11,
        "group_id": group,
        "qid": "Q17",
        "entity_group": "LOC",
        "method": "exact",
    }
    pq.write_table(pa.Table.from_pylist([pair]), matching / "exact_pairs.parquet")
    job_id = identity([1, 11, "Q999"])
    other = {**pair, "id": job_id, "qid": "Q999", "method": "model"}
    (inference / "model_pairs.jsonl").write_text(
        json.dumps(other) + "\n", encoding="utf-8"
    )
    mentions_path = tmp_path / "mentions.parquet"
    pq.write_table(pa.Table.from_pylist(rows), mentions_path)
    jobs = [
        {
            "id": identity([1, 11, "Q17"]),
            "page_id": 1,
            "revision_id": 11,
            "qid": "Q17",
            "candidates": [],
        },
        {
            "id": job_id,
            "page_id": 1,
            "revision_id": 11,
            "qid": "Q999",
            "candidates": [{"id": group, "type": "LOC"}],
        },
    ]
    jobs_path = matching / "jobs.jsonl"
    jobs_path.write_text("".join(json.dumps(j) + "\n" for j in jobs))
    (matching / "matching_summary.json").write_text(
        json.dumps({"input_hashes": {str(mentions_path): sha256(mentions_path)}})
    )
    (inference / "inference_inputs.json").write_text(
        json.dumps({"jobs_sha256": sha256(jobs_path)})
    )
    ref = tmp_path / "reference.jsonl"
    ref.write_text("", encoding="utf-8")
    summary = export(mentions_path, matching, inference, ref, tmp_path / "final")
    result = pq.read_table(tmp_path / "final/matched_mentions.parquet")
    assert summary["exported_rows"] == 2
    assert result["matched_qids"].to_pylist() == [["Q17", "Q999"], ["Q17", "Q999"]]
    assert result.select(list(rows[0])).equals(pq.read_table(mentions_path))
    # A new hash alone must not permit stale groups to join a new revision.
    changed = [{**r, "revision_id": 12} for r in rows]
    pq.write_table(pa.Table.from_pylist(changed), mentions_path)
    (matching / "matching_summary.json").write_text(
        json.dumps({"input_hashes": {str(mentions_path): sha256(mentions_path)}})
    )
    with pytest.raises(ValueError):
        export(mentions_path, matching, inference, ref, tmp_path / "stale_final")


def test_every_positive_gets_a_singleton_state_to_prevent_early_stop():
    import torch

    from GG_Data.entity_resolution.hundred_page_pilot.model import (
        marginal_set_loss, pair_texts)
    from GG_Data.entity_resolution.hundred_page_pilot.prepare_training import \
        removal_states

    base = {
        "id": "q",
        "entity": {"name": "E"},
        "candidates": [{"id": k, "name": k, "context": ""} for k in ("a", "b", "n")],
        "positive_ids": ["a", "b"],
    }
    states = removal_states(base)
    assert {s["positive_ids"][0] for s in states if len(s["positive_ids"]) == 1} == {
        "a",
        "b",
    }
    signatures = [tuple(c["id"] for c in s["candidates"]) for s in states]
    assert len(signatures) == len(set(signatures))
    sequential = [s for s in states if s["state_kind"] == "sequential_removal"]
    last = sequential[-2]["positive_ids"][0]

    def loss(row):
        values = [20.0 if c["id"] == last else -20.0 for c in row["candidates"]] + [0.0]
        return marginal_set_loss(
            torch.tensor(values), [len(values)], [pair_texts(row)[2]]
        )

    assert torch.stack([loss(s) for s in sequential]).mean() < 1e-6
    assert torch.stack([loss(s) for s in states]).mean() > 4.0


def test_failed_cache_save_keeps_previous_complete_file(tmp_path, monkeypatch):
    import torch

    from GG_Data.entity_resolution.hundred_page_pilot.train import \
        atomic_torch_save

    path = tmp_path / "cache.pt"
    torch.save({"old": 1}, path)
    original = path.read_bytes()

    def failed_save(value, destination):
        from pathlib import Path

        Path(destination).write_bytes(b"partial")
        raise OSError("interrupted")

    with monkeypatch.context() as patch:
        patch.setattr(torch, "save", failed_save)
        with pytest.raises(OSError, match="interrupted"):
            atomic_torch_save({"new": 2}, path)
    assert path.read_bytes() == original
    atomic_torch_save({"new": 2}, path)
    assert torch.load(path, weights_only=True) == {"new": 2}


def test_score_tail_recovery_preserves_evidence_and_rejects_interior(tmp_path):
    import json

    from GG_Data.entity_resolution.hundred_page_pilot.match import \
        read_score_records

    path = tmp_path / "scores.jsonl"
    valid = json.dumps({"id": "one", "options": []}) + "\n"
    original = (valid + '{"id":').encode()
    path.write_bytes(original)
    assert read_score_records(path) == [{"id": "one", "options": []}]
    assert path.read_text() == valid
    assert any(p.read_bytes() == original for p in tmp_path.iterdir() if p != path)
    path.write_text(valid + "broken\n" + valid)
    with pytest.raises(ValueError):
        read_score_records(path)


def test_export_rejects_missing_input_lineage(tmp_path):
    import json

    import pyarrow as pa
    import pyarrow.parquet as pq

    from GG_Data.entity_resolution.hundred_page_pilot.report import export

    matching, inference = tmp_path / "matching", tmp_path / "inference"
    matching.mkdir()
    inference.mkdir()
    rows = [mention()]
    groups = group_mentions(rows)
    (matching / "groups.jsonl").write_text(json.dumps(groups[0]) + "\n")
    pair = {
        "page_id": 1,
        "revision_id": 11,
        "group_id": groups[0]["id"],
        "qid": "Q17",
        "entity_group": "LOC",
        "method": "exact",
    }
    pq.write_table(pa.Table.from_pylist([pair]), matching / "exact_pairs.parquet")
    (inference / "model_pairs.jsonl").write_text("")
    source = tmp_path / "mentions.parquet"
    pq.write_table(pa.Table.from_pylist(rows), source)
    ref = tmp_path / "ref.jsonl"
    ref.write_text("")
    with pytest.raises((ValueError, FileNotFoundError)):
        export(source, matching, inference, ref, tmp_path / "final")


def test_resumed_inference_counts_new_and_cached_pairs(tmp_path, monkeypatch):
    import json

    from GG_Data.entity_resolution.hundred_page_pilot import model
    from GG_Data.entity_resolution.hundred_page_pilot.match import infer

    jobs = [
        {
            "id": k,
            "page_id": 1,
            "revision_id": 11,
            "qid": "Q" + k,
            "candidates": [{"id": "g", "type": "LOC"}],
            "excluded_count": 0,
        }
        for k in ("1", "2")
    ]
    source = tmp_path / "jobs.jsonl"
    source.write_text("".join(json.dumps(j) + "\n" for j in jobs))
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(b"mock model")
    monkeypatch.setattr(model, "load_scorer", lambda *a: (None, None, {}))
    calls = []

    def score(*args, **kwargs):
        calls.append(args[2]["id"])
        if len(calls) == 2:
            raise RuntimeError("interrupted scoring")
        return {"g": 1.0, None: 0.0}

    monkeypatch.setattr(model, "score_record", score)
    output = tmp_path / "inference"
    with pytest.raises(RuntimeError, match="interrupted scoring"):
        infer(source, checkpoint, output, 1, 8, "cpu")
    result = infer(source, checkpoint, output, 1, 8, "cpu")
    assert calls == ["1", "2", "2"]
    assert result["pair_evaluations"] == 2
    assert result["cached_pair_evaluations"] == 2
    assert result["total_pair_evaluations"] == 4
    assert result["cumulative_elapsed_seconds"] >= result["elapsed_seconds"]
    assert result["selected_pairs"] == 2
