from build_country_reference_dataset import minimal_spans, split_paragraphs


def test_minimal_spans_prefers_one_sentence() -> None:
    text = "U-1 was registered in Germany. U-1 was launched in 1940."
    spans = minimal_spans(text, ["U-1"], ["Germany"])
    assert [row["evidence_text"] for row in spans] == [
        "U-1 was registered in Germany."
    ]
    assert spans[0]["span_level"] == "sentence"


def test_minimal_spans_uses_shortest_sentence_window() -> None:
    text = (
        "U-1 entered service. It had a short career. Germany operated the vessel. "
        "Another unrelated sentence follows."
    )
    spans = minimal_spans(text, ["U-1"], ["Germany"])
    assert [row["evidence_text"] for row in spans] == [
        "U-1 entered service. It had a short career. Germany operated the vessel."
    ]
    assert spans[0]["span_level"] == "multi_sentence"


def test_minimal_spans_does_not_cross_paragraphs() -> None:
    text = "U-1 entered service.\n\nGermany operated several vessels."
    assert minimal_spans(text, ["U-1"], ["Germany"]) == []


def test_heading_is_not_joined_to_sentence() -> None:
    assert split_paragraphs("Lineage\nU-1 was registered in Germany.") == [
        "U-1 was registered in Germany."
    ]
