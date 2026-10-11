from run_country_data_availability_audit import (
    article_body_wikitext,
    balanced_template,
    infobox_field_matches,
    linked_anchors,
    object_spans,
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


def test_nested_ship_infobox_fields_are_extracted() -> None:
    text = """{{Infobox ship begin}}
{{Infobox ship career
| country = [[Norway]]
}}
{{Infobox ship career
| country = [[Nazi Germany]]
}}
"""
    assert infobox_field_matches(text, "Nazi Germany", ["Nazi Germany"]) == {
        "country": "Nazi Germany"
    }


def test_plain_wikitext_keeps_link_anchor_and_removes_infobox() -> None:
    text = "{{Infobox ship|country=Germany}}\nU-1 served [[Nazi Germany|Germany]]."
    assert plain_wikitext(text).strip() == "U-1 served Germany."


def test_page_subject_allows_object_only_sentence() -> None:
    spans = object_spans(
        "It served under Nazi Germany. It later surrendered.", ["Nazi Germany"]
    )
    assert spans == [
        {
            "paragraph_index": 0,
            "sentence_start": 0,
            "sentence_end": 0,
            "span_level": "sentence",
            "object_match": "Nazi Germany",
            "evidence_text": "It served under Nazi Germany.",
        }
    ]


def test_article_body_excludes_reference_tail() -> None:
    text = "{{Infobox x\n| country = Germany\n}}\nBody text.\n== References ==\nGermany"
    infobox = balanced_template(text)
    assert article_body_wikitext(text, infobox).strip() == "Body text."
