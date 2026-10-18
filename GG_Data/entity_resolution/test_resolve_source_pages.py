"""Exercise server-directed aliases and unresolved cases without network calls."""

from resolve_source_pages import resolve_batch


def test_alias_chain_and_explicit_unresolved_cases() -> None:
    titles = ["franklin_Roosevelt", "Missing", "Ambiguous", "No QID", "Loop"]
    response = {
        "query": {
            "normalized": [{"from": "franklin_Roosevelt", "to": "Franklin Roosevelt"}],
            "redirects": [
                {"from": "Franklin Roosevelt", "to": "Franklin D. Roosevelt"},
                {"from": "Loop", "to": "Other"},
                {"from": "Other", "to": "Loop"},
            ],
            "pages": [
                {
                    "title": "Franklin D. Roosevelt",
                    "pageid": 10979,
                    "ns": 0,
                    "pageprops": {"wikibase_item": "Q8007"},
                },
                {"title": "Missing", "missing": True},
                {
                    "title": "Ambiguous",
                    "pageid": 2,
                    "ns": 0,
                    "pageprops": {"disambiguation": "", "wikibase_item": "Q2"},
                },
                {"title": "No QID", "pageid": 3, "ns": 0},
            ],
        }
    }
    rows = resolve_batch(titles, response)
    assert [r["Source"] for r in rows] == titles
    assert rows[0]["page_qid"] == "Q8007"
    assert rows[0]["wikipedia_page_id"] == 10979
    assert len(rows[0]["normalization_and_redirects"]) == 2
    assert [r["status"] for r in rows[1:]] == [
        "MISSING_OR_INVALID_PAGE",
        "DISAMBIGUATION",
        "NO_WIKIDATA_ID",
        "REDIRECT_CYCLE",
    ]
    assert all(r["page_qid"] is None for r in rows[1:])
