"""Small integrity check for EventKG range boundaries and QID selection."""

from __future__ import annotations

import gzip
import json

import filter_eventkg_v3_2 as job


def test_range_resume_keeps_complete_matched_resource(tmp_path, monkeypatch) -> None:
    source = (
        b"<event_1> <rdf:type> <Event> <graph> .\n"
        b"<event_1> <owl#sameAs> <http://www.wikidata.org/entity/Q362> <graph> .\n"
        b"<event_1> <rdfs:label> \"World War II\" <graph> .\n"
        b"<event_2> <rdf:type> <Event> <graph> .\n"
        b"<event_2> <owl#sameAs> <http://www.wikidata.org/entity/Q999> <graph> .\n"
    )

    class Response:
        def __init__(self, body: bytes, headers: dict[str, str], status: int = 200) -> None:
            self.content = body
            self.headers = headers
            self.status_code = status

        def raise_for_status(self) -> None:
            return None

    class Session:
        def request(self, method: str, url: str, **kwargs: object) -> Response:
            if method == "HEAD":
                return self.head(url, kwargs["timeout"])
            return self.get(url, kwargs["headers"], kwargs["timeout"])

        def head(self, url: str, timeout: int) -> Response:
            return Response(b"", {"Content-Length": str(len(source))})

        def get(self, url: str, headers: dict[str, str], timeout: int) -> Response:
            range_text = headers["Range"].removeprefix("bytes=")
            start, end = map(int, range_text.split("-"))
            return Response(
                source[start : end + 1],
                {"Content-Range": f"bytes {start}-{end}/{len(source)}"},
                206,
            )

    monkeypatch.setattr(job, "BASE", tmp_path)
    monkeypatch.setattr(job, "CHUNK_SIZE", 224)
    monkeypatch.setattr(job, "session", Session())
    (tmp_path / "wikidata_qids.txt").write_text("Q362\n", encoding="ascii")
    job.download("events.nq")
    output = tmp_path / "eventkg_v3_2" / "events"
    combined = b"".join(gzip.decompress(path.read_bytes()) for path in sorted(output.glob("*.nq.gz")))
    assert combined == source.split(b"<event_2>", 1)[0]
    assert sum(1 for path in output.glob("*.qid_map.tsv") for _ in path.open()) == 1
    assert json.loads((output / "manifest.json").read_text())["matched"] == 1
