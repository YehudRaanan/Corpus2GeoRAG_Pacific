"""A fixed review cohort follows original mentions, never stale QIDs."""

import pytest

from GG_Data.pipeline.geography_review_rerun import cohort


def test_corrected_ids_and_non_locations_remain_in_the_review_denominator():
    old = [
        dict(
            index=i,
            place_id=f"Q{i}",
            mention_id=str(i),
            daniel_name=f"Name {i}",
            daniel_text=f"Text {i}",
        )
        for i in range(3)
    ]
    mentions = [
        dict(
            mention_id=str(i),
            entity_id=f"Q{i+10}",
            entity_type="LOC" if i < 2 else "PER",
            word=f"Name {i}",
            Text=f"Text {i}",
        )
        for i in range(3)
    ]
    result = cohort(old, mentions, [dict(place_id="Q10"), dict(place_id="Q11")])
    assert [r["entity_id"] for r in result] == ["Q10", "Q11", "Q12"]
    assert [r["status"] for r in result] == ["LOC", "LOC", "NON_LOC_AFTER_MATCHING"]
    assert len(result) == len(old)
    # The baseline sampled LOC entity rows. A QID can also have an ORG row;
    # its representative mention's type must not remove the existing LOC row.
    mentions[1]["entity_type"] = "ORG"
    assert cohort(old, mentions, [dict(place_id="Q11")])[1]["status"] == "LOC"
    mentions[0]["Text"] = "Different original text"
    with pytest.raises(ValueError, match="input changed"):
        cohort(old, mentions, [])
