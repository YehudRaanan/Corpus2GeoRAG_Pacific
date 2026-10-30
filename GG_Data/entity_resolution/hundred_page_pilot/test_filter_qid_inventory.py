"""The shared inventory keeps uncertain evidence and rejects proved exclusions."""

import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from GG_Data.entity_resolution.hundred_page_pilot import filter_qid_inventory as qids
from GG_Data.entity_resolution.luke_pilot.data import sha256


def entity(qid="Q1", **kwargs):
    return dict(page_id=1, revision_id=2, qid=qid, label="Example", **kwargs)


def support(tmp_path, raw, text, *, occurrence=0, **kwargs):
    path = tmp_path / "1_2.txt"
    path.write_text(raw, encoding="utf-8")
    start = [i for i in range(len(raw)) if raw.startswith(text, i)][occurrence]
    return dict(
        page_id=1,
        revision_id=2,
        qid="Q1",
        link_origin="RAW_DIRECT_LINK",
        raw_evidence_path=str(path),
        raw_sha256=sha256(path),
        anchor_start=start,
        anchor_end=start + len(text),
        anchor_text=text,
        **kwargs,
    )


def test_mixed_body_reference_and_excluded_only(tmp_path):
    raw = "[[Japan]]<ref>{{cite book|title=[[Japan]]}}</ref>"
    body = support(tmp_path, raw, "Japan")
    reference = support(tmp_path, raw, "Japan", occurrence=1)
    retained, audit = qids.filter_inventory(
        [entity(raw_link_occurrences=2)], [body, reference], tmp_path, {}
    )
    assert retained[0]["qid_source_status"] == "KEEP"
    assert audit[0]["source_support_counts"] == {"KEEP": 1, "EXCLUDE": 1}
    retained, audit = qids.filter_inventory([entity()], [reference], tmp_path, {})
    assert retained == []
    assert audit[0]["qid_source_status"] == "EXCLUDE"


def test_template_uses_name_offset_instead_of_whole_template(tmp_path):
    raw = "The {{ship|Japanese battleship|Nagato|up=yes}} sailed."
    row = support(tmp_path, raw, "Nagato")
    row.update(
        link_origin="RAW_SHIP_TEMPLATE",
        name="Nagato",
        name_start=row.pop("anchor_start"),
        name_end=row.pop("anchor_end"),
        raw_start=4,
        raw_end=raw.index("}}") + 2,
        raw_text=raw[4 : raw.index("}}") + 2],
    )
    retained, audit = qids.filter_inventory([entity()], [row], tmp_path, {})
    assert retained[0]["qid_source_status"] == "KEEP"
    assert audit[0]["source_support"][0]["reason"] == "display_value"


def test_unknown_support_and_missing_occurrences_are_retained(tmp_path):
    retained, _ = qids.filter_inventory([entity()], [], tmp_path, {})
    assert retained[0]["qid_source_status"] == "UNKNOWN_KEEP"
    row = support(tmp_path, "{{cite book|title=Japan}}", "Japan")
    retained, _ = qids.filter_inventory(
        [entity(raw_link_occurrences=2)], [row], tmp_path, {}
    )
    assert retained[0]["qid_source_status"] == "UNKNOWN_KEEP"


def test_verified_page_own_support_and_review_are_kept(tmp_path):
    own = support(tmp_path, "Japan", "Japan")
    own.update(link_origin="PAGE_OWN_QID", page_own_qid_page_id_verified=True)
    retained, audit = qids.filter_inventory([entity()], [own], tmp_path, {})
    assert retained[0]["qid_source_status"] == "KEEP"
    assert audit[0]["page_own_verified"] == 1
    own["page_own_qid_page_id_verified"] = None
    retained, _ = qids.filter_inventory([entity()], [own], tmp_path, {})
    assert retained[0]["qid_source_status"] == "UNKNOWN_KEEP"
    review = support(tmp_path, "{{unknown|Japan}}", "Japan")
    retained, _ = qids.filter_inventory([entity()], [review], tmp_path, {})
    assert retained[0]["qid_source_status"] == "REVIEW_KEEP"


@pytest.mark.parametrize("bad", ["hash", "offset", "text"])
def test_invalid_raw_evidence_raises(tmp_path, bad):
    row = support(tmp_path, "Japan", "Japan")
    if bad == "hash":
        row["raw_sha256"] = "0" * 64
    elif bad == "offset":
        row["anchor_end"] = 99
    else:
        row["anchor_text"] = "Other"
    with pytest.raises(ValueError):
        qids.filter_inventory([entity()], [row], tmp_path, {})


def test_native_p31_overlapping_categories_and_incomplete_closure(tmp_path):
    metadata = {
        "Q1": {"direct_types": ["Q5"], "parents": []},
        "Q10": {"parents": ["Q43229", "Q618123"]},
        "Q43229": {"parents": []},
        "Q618123": {"parents": []},
    }
    retained, _ = qids.filter_inventory(
        [entity(native_types=["Q10"])], [], tmp_path, metadata
    )
    result = retained[0]
    assert result["type_categories"] == ["LOC", "ORG"]
    assert result["type_unknown"] is False
    assert qids.compatible(result, "ORG") and qids.compatible(result, "LOC")
    assert not qids.compatible(result, "PER")
    metadata["Q10"]["parents"].append("Q99")
    retained, audit = qids.filter_inventory(
        [entity(native_types=["Q10"])], [], tmp_path, metadata
    )
    assert retained[0]["type_unknown"] is True
    assert audit[0]["type_missing_classes"] == ["Q99"]
    assert qids.compatible(retained[0], "PER")


def test_compatible_preserves_legacy_and_applies_source_and_date_guards():
    assert qids.compatible(entity(), "DATE")
    enriched = entity(
        qid_source_status="REVIEW_KEEP",
        type_categories=["ORG"],
        type_unknown=False,
        qid_filter_policy_version=qids.POLICY_VERSION,
    )
    assert qids.compatible(enriched, "MISC")
    assert not qids.compatible(enriched, "DATE")
    assert not qids.compatible(enriched, "PER")
    enriched["qid_source_status"] = "EXCLUDE"
    assert not qids.source_allowed(enriched)
    assert not qids.compatible(enriched, "MISC")


def test_missing_entity_marker_is_unknown_even_with_empty_parents(tmp_path):
    retained, _ = qids.filter_inventory(
        [entity(native_types=["Q10"])],
        [],
        tmp_path,
        {
            "Q10": {"parents": ["Q43229", "Q99"]},
            "Q43229": {"parents": []},
            "Q99": {"parents": [], "missing": True},
        },
    )
    assert retained[0]["type_categories"] == ["ORG"]
    assert retained[0]["type_unknown"] is True
    assert qids.compatible(retained[0], "PER")


def test_cli_preserves_original_columns_snapshots_and_refuses_overwrite(tmp_path):
    row = support(tmp_path, "Japan", "Japan")
    entities_path, evidence_path = (
        tmp_path / "input.parquet",
        tmp_path / "evidence.parquet",
    )
    original = entity(native_types=["Q5"], aliases=["Japan"], custom="preserved")
    pq.write_table(pa.Table.from_pylist([original]), entities_path)
    pq.write_table(pa.Table.from_pylist([row]), evidence_path)
    metadata = tmp_path / "metadata.json"
    metadata.write_text(json.dumps({"Q5": {"parents": []}}), encoding="utf-8")
    output = tmp_path / "out"
    args = [
        "--entities",
        str(entities_path),
        "--evidence",
        str(evidence_path),
        "--raw-root",
        str(tmp_path),
        "--type-metadata",
        str(metadata),
        "--out",
        str(output),
    ]
    qids.main(args)
    saved = pq.read_table(output / "entities.parquet").to_pylist()[0]
    assert all(saved[k] == value for k, value in original.items())
    assert saved["type_categories"] == ["PER"]
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["input_rows"] == summary["retained_rows"] == 1
    assert summary["type_hierarchy_sha256"] == sha256(metadata)
    assert summary["raw_revision_sha256"][row["raw_evidence_path"]] == row["raw_sha256"]
    assert (output / "type_metadata_snapshot.json.gz").exists()
    assert (output / "native_metadata_snapshot.parquet").exists()
    assert (output / "hashes.json").exists()
    with pytest.raises(FileExistsError):
        qids.main(args)


def test_cli_can_write_all_unknown_source_support(tmp_path):
    pq.write_table(pa.Table.from_pylist([entity()]), tmp_path / "entities.parquet")
    pq.write_table(
        pa.Table.from_pylist(
            [
                dict(
                    page_id=1,
                    revision_id=2,
                    qid="Q1",
                    raw_evidence_path=str(tmp_path / "missing.txt"),
                    raw_sha256="0" * 64,
                )
            ]
        ),
        tmp_path / "evidence.parquet",
    )
    (tmp_path / "metadata.json").write_text("{}", encoding="utf-8")
    qids.main(
        [
            "--entities",
            str(tmp_path / "entities.parquet"),
            "--evidence",
            str(tmp_path / "evidence.parquet"),
            "--raw-root",
            str(tmp_path),
            "--type-metadata",
            str(tmp_path / "metadata.json"),
            "--out",
            str(tmp_path / "out"),
        ]
    )
    assert (
        pq.read_table(tmp_path / "out/entities.parquet").to_pylist()[0][
            "qid_source_status"
        ]
        == "UNKNOWN_KEEP"
    )
    summary = json.loads((tmp_path / "out/summary.json").read_text(encoding="utf-8"))
    assert summary["raw_revision_sha256"] == {}
