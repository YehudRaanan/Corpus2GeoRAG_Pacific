from run_relation_catalog_eda import exclusion, family_for, mapping


def test_easy_scoped_mapping() -> None:
    assert mapping("http://ldf.fi/schema/warsa/actors/hasConflict") == (
        "wd:P607",
        "EXACT",
        "same",
        "military unit or person -> conflict",
    )
    assert mapping("http://semanticweb.cs.vu.nl/2009/11/sem/hasSubEvent")[:3] == (
        "wd:P527",
        "EXACT",
        "same",
    )


def test_family_and_exclusion_rules() -> None:
    assert family_for("wd:P276", "location", "") == "SPATIAL"
    assert family_for("wd:P710", "participant", "") == "PARTICIPATION_ROLE"
    assert exclusion("wd:P31", "wd:P31", "instance of", "") == "TYPE_OR_SCHEMA"
    assert exclusion("wd:P607", "wd:P607", "conflict", "") == ""
