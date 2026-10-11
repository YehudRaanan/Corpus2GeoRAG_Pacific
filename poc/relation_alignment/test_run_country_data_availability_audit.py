from run_country_data_availability_audit import (
    balanced_template,
    linked_anchors,
    plain_wikitext,
    relation_paths,
    template_fields,
)


def test_relation_paths_separates_direct_and_qualifier() -> None:
    entity = {
        "claims": {
            "P17": [
                {
                    "rank": "normal",
                    "mainsnak": {"datavalue": {"value": {"id": "Q1"}}},
                    "qualifiers": {
                        "P642": [{"datavalue": {"value": {"id": "Q2"}}}]
                    },
                }
            ]
        }
    }
    direct, qualifiers = relation_paths(entity, "Q2")
    assert direct == set()
    assert qualifiers == {"P17/P642"}


def test_infobox_and_link_extraction() -> None:
    text = "{{Infobox ship\n| operator = [[Nazi Germany|German]] navy\n}}\nU-1 sailed."
    infobox = balanced_template(text)
    assert template_fields(infobox)["operator"].startswith("[[Nazi Germany")
    assert linked_anchors(text, "Nazi Germany") == ["German"]


def test_plain_wikitext_keeps_link_anchor_and_removes_infobox() -> None:
    text = "{{Infobox ship|country=Germany}}\nU-1 served [[Nazi Germany|Germany]]."
    assert plain_wikitext(text).strip() == "U-1 served Germany."
