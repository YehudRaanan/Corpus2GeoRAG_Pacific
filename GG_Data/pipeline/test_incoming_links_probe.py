"""Count retrieval must not confuse missing values, page views or other QIDs."""

import pytest

from GG_Data.pipeline.incoming_links_probe import indexed_counts
from GG_Data.pipeline.misc_relevance_probe import relevance_rows


def payload(count=0, qid="Q5287"):
    return {
        "query": {
            "pages": [
                {
                    "ns": 0,
                    "pageid": 15606,
                    "title": "Japanese language",
                    "cirrusdoc": [
                        {
                            "index": "enwiki_content",
                            "source": {
                                "wikibase_item": qid,
                                "incoming_links": count,
                                "popularity_score": 999,
                            },
                        }
                    ],
                }
            ]
        }
    }


def test_validate_existing_counts_and_stop_on_missing_or_wrong_identity():
    assert indexed_counts(payload(), {"Q5287"})["Q5287"]["incoming_links"] == 0
    for invalid in (None, -1, True, "10"):
        with pytest.raises(ValueError):
            indexed_counts(payload(invalid), {"Q5287"})
    with pytest.raises(ValueError):
        indexed_counts(payload(qid="Q1"), {"Q5287"})
    missing = payload()
    del missing["query"]["pages"][0]["cirrusdoc"][0]["source"]["incoming_links"]
    with pytest.raises(KeyError):
        indexed_counts(missing, {"Q5287"})


def test_relevance_counts_distinct_english_pages_and_keeps_unknown_counts():
    def mention(page, site="enwiki"):
        return {
            "entity_id": "Q5287",
            "wiki_site": site,
            "wiki_page_id": page,
            "raw": {"word": "Japanese"},
        }

    mentions = [mention(1), mention(1), mention(2), mention(3, "jawiki")]
    for denominator, expected in [(100, 0.02), (None, None), (0, None)]:
        row = relevance_rows(
            mentions,
            [
                {
                    "qid": "Q5287",
                    "title": "Japanese language",
                    "incoming_links": denominator,
                }
            ],
        )[0]
        assert row["daniel_english_pages_in_10k"] == 2
        assert row["daniel_english_mentions_in_10k"] == 3
        assert row["relevance"] == expected
