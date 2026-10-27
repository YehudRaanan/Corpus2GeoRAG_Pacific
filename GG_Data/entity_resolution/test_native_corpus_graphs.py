"""Pin graph identity, page-count weights, and source version boundaries."""

import native_corpus_graphs as subject
import native_eventkg_archive as archive
import native_graph_reference as reference
import numpy as np
import pandas as pd
import pytest


def test_exact_identity_page_deduplication_and_unresolved_nodes(tmp_path):
    rows = pd.DataFrame(
        [
            ("A", "PER", 1, 11),
            ("A", "PER", 1, 12),
            ("B", "LOC", 1, 11),
            ("B", "LOC", 1, 12),
            ("A", "PER", 2, 21),
            ("B", "LOC", 2, 21),
            ("A", "ORG", 1, 12),
            ("a", "PER", 1, 12),
            ("orphan", "MISC", None, None),
        ],
        columns=["name", "type", "wiki_page_id", "wiki_revision_id"],
    )
    nodes, pages, revisions = subject.memberships(rows)
    assert len(nodes) == 5
    assert len(pages) == 6
    assert len(revisions) == 8
    orphan = nodes.loc[nodes.name.eq("orphan")].iloc[0]
    assert orphan.page_count == 0
    stats = subject.write_edges(nodes, pages, tmp_path, block_size=2)
    edges = pd.read_parquet(tmp_path)
    ids = {(x.name, x.type): x.node_id for x in nodes.itertuples()}
    pair = sorted([ids[("A", "PER")], ids[("B", "LOC")]])
    assert edges.loc[
        edges.source.eq(pair[0]) & edges.target.eq(pair[1]), "weight"
    ].tolist() == [2]
    assert stats["weight_sum"] == 7
    assert (edges.source < edges.target).all()
    assert np.isin(edges.weight, [1, 2]).all()


def test_link_targets_keep_article_colons_and_reject_namespaces_and_edits():
    html = """<div class="mw-parser-output"><p>
    <a href="/wiki/Alpha#History">A</a><a href="/wiki/Alpha">Alpha</a>
    <a href="/wiki/Star_Trek:_Discovery">Ship</a>
    <a href="/wiki/File:X.jpg">file</a><a href="/wiki/Category:War">category</a>
    <a href="#Section">local</a><a href="https://example.com/x">external</a>
    <a href="/w/index.php?title=Missing&amp;action=edit&amp;redlink=1">red</a>
    </p><script><a href="/wiki/Script">bad</a></script></div>"""
    links = subject.article_links(html)
    assert set(links) == {
        ("Alpha", "A"),
        ("Alpha", "Alpha"),
        ("Star Trek: Discovery", "Ship"),
    }


def test_wrong_page_or_revision_is_rejected():
    with pytest.raises(ValueError, match="identity"):
        subject.validate_parse({"pageid": 4, "revid": 10, "text": "ok"}, 4, 11)
    with pytest.raises(ValueError, match="identity"):
        subject.validate_parse({"pageid": 5, "revid": 11, "text": "ok"}, 4, 11)


def test_native_types_are_not_mapped_and_deprecated_claims_are_excluded():
    entity = {
        "id": "Q1",
        "labels": {"en": {"value": "Name"}},
        "claims": {
            "P31": [
                {"rank": "normal", "mainsnak": {"datavalue": {"value": {"id": "Q5"}}}},
                {
                    "rank": "preferred",
                    "mainsnak": {"datavalue": {"value": {"id": "Q9"}}},
                },
                {
                    "rank": "deprecated",
                    "mainsnak": {"datavalue": {"value": {"id": "Q8"}}},
                },
            ]
        },
    }
    item = subject.project_entity(entity)
    assert item["direct_types"] == ["Q5", "Q9"]
    assert item["label"] == "Name"


def test_revision_union_counts_one_page_even_without_simultaneous_presence(tmp_path):
    rows = pd.DataFrame(
        [("A", "Q5", 1, 11), ("B", "Q9", 1, 12)],
        columns=["name", "type", "wiki_page_id", "wiki_revision_id"],
    )
    nodes, pages, _ = subject.memberships(rows)
    assert subject.write_edges(nodes, pages, tmp_path)["weight_sum"] == 1


def test_cached_disambiguation_is_not_accepted_as_an_entity():
    assert reference.cached_title_status(
        {"id": "Q1", "direct_types": ["Q4167410"]}
    ) == ("DISAMBIGUATION_TARGET", None)
    assert reference.cached_title_status({"id": "Q2", "direct_types": ["Q5"]}) == (
        "BQ_EXACT_ENWIKI_SITELINK",
        "Q2",
    )


def test_incomplete_eventkg_scan_cannot_claim_absence(tmp_path):
    folder = tmp_path / "events"
    folder.mkdir()
    (folder / "manifest.json").write_text(
        '{"next_offset": 9, "source_bytes": 10, "part": 0}'
    )
    with pytest.raises(ValueError, match="Incomplete saved EventKG"):
        reference.validate_saved_scan(tmp_path)


def test_archive_rejects_wrong_range_and_keeps_only_requested_qids():
    with pytest.raises(ValueError, match="Unexpected archive range"):
        archive.check_range(200, None, 0, 9, 10)
    archive.check_range(206, "bytes 0-9/10", 0, 9, 10)
    data = b'<r1> <label> "A" <g> .\n<r1> <http://www.w3.org/2002/07/owl#sameAs> <http://www.wikidata.org/entity/Q1> <g> .\n<r2> <http://www.w3.org/2002/07/owl#sameAs> <http://www.wikidata.org/entity/Q2> <g> .\n'
    lines = data.splitlines()
    assert archive.matching_qids(lines[:2], {b"Q1"}) == {b"Q1"}
    assert not archive.matching_qids(lines[2:], {b"Q1"})


def test_archive_two_pass_filter_keeps_types_before_entity_mapping(
    tmp_path, monkeypatch
):
    import gzip
    import io
    import json
    import tarfile

    folder = tmp_path / "eventkg_archive"
    folder.mkdir()
    pd.DataFrame({"qid": ["Q1"]}).to_parquet(tmp_path / "title_qid_mapping.parquet")
    with tarfile.open(folder / "eventkg_v3_2_output.tar.gz", "w:gz") as tar:
        for name in sorted(archive.SOURCES, reverse=True):
            data = b"<r1> <type> <T> <g> .\n<r2> <type> <T> <g> .\n"
            if name == "entities.nq":
                data = b'<r1> <label> "A" <g> .\n<r1> <http://www.w3.org/2002/07/owl#sameAs> <http://www.wikidata.org/entity/Q1> <g> .\n<r2> <http://www.w3.org/2002/07/owl#sameAs> <http://www.wikidata.org/entity/Q2> <g> .\n'
            if name == "events.nq":
                data = b""
            if name == "entities.nq":
                data += b'<r1> <label> "Later noncontiguous label" <g> .\n'
            member = tarfile.TarInfo("output/" + name)
            member.size = len(data)
            tar.addfile(member, io.BytesIO(data))
    monkeypatch.setattr(
        archive, "SIZE", (folder / "eventkg_v3_2_output.tar.gz").stat().st_size
    )
    (folder / "download_manifest.json").write_text(
        json.dumps(
            {
                "verified_md5": archive.MD5,
                "sha256": archive.sha256(folder / "eventkg_v3_2_output.tar.gz"),
            }
        )
    )
    archive.filter_archive(tmp_path)
    result = json.loads((folder / "filter_manifest.json").read_text())
    assert result["completed"] and result["found_qids"] == 1
    with gzip.open(folder / "corpus/types.nq.gz", "rb") as stream:
        assert stream.read() == b"<r1> <type> <T> <g> .\n"
    with gzip.open(folder / "corpus/entities.nq.gz", "rb") as stream:
        content = stream.read()
        assert b'"A"' in content
        assert b'"Later noncontiguous label"' in content
    path = folder / "eventkg_v3_2_output.tar.gz"
    original = path.read_bytes()
    path.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
    with pytest.raises(ValueError, match="Missing verified official archive"):
        archive.filter_archive(tmp_path)
