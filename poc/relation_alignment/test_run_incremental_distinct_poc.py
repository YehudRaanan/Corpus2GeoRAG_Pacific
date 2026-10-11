import run_incremental_distinct_poc as poc


def test_smallest_useful_split_then_stop():
    rows = [
        {
            "object_qid": f"Q{i}",
            "wikidata_observed": "P17|P710" if i < 3 else "P276",
            "features": {"role"} if i < 3 else set(),
        }
        for i in range(6)
    ]
    selected, steps = poc.choose_fields(rows)
    assert selected == ["role"]
    assert steps[0]["added_groups"] == 1
    assert steps[0]["mixed_pairs"] == 0

    # A feature found only on one object cannot define a reusable split.
    for row in rows[:3]:
        row["object_qid"] = "Q0"
    assert poc.choose_fields(rows)[0] == []


def test_features_keep_native_sources_separate():
    row = {
        "subject_p31": "Q10|Q11",
        "object_p31": "Q20",
        "eventkg_graphs": "event_kg|wikidata|yago",
    }
    assert poc.features(row) == {
        "subject_type_Q10",
        "subject_type_Q11",
        "object_type_Q20",
        "source_yago",
    }


def test_fewest_new_groups_wins_over_larger_ambiguity_reduction():
    rows = [
        {
            "object_qid": f"Q{i}",
            "wikidata_observed": "P17" if i < 3 or 6 <= i < 9 else "P710",
            "features": (
                ({"base"} if i < 6 else set())
                | ({"small"} if i < 3 else set())
                | ({"large"} if i < 3 or 6 <= i < 9 else set())
            ),
        }
        for i in range(12)
    ]
    selected, steps = poc.choose_fields(rows, initial=("base",))
    assert selected[1] == "small"
    assert steps[0]["added_groups"] == 1
