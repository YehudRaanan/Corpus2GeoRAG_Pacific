"""Check indented fields and an empty predecessor followed by a successor."""

from trace_succession_sources import FIELD_PATTERN


def check_fields() -> None:
    text = "{{Unit\n  | предшественник = \n  | преемник = [[Next]]\n | other = x\n}}"
    fields = [(m.group(1), m.group(2).strip()) for m in FIELD_PATTERN.finditer(text)]
    assert fields == [("предшественник", ""), ("преемник", "[[Next]]")], fields
    print("Succession field parser check passed.")


if __name__ == "__main__":
    check_fields()
