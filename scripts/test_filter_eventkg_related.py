from filter_eventkg_related import filter_content


def test_reified_relation_keeps_full_group_when_endpoint_matches() -> None:
    ids = {b"<https://eventkg.l3s.uni-hannover.de/resource/event_1>"}
    data = (
        b"<relation_1> <rdf:type> <Relation> .\n"
        b"<relation_1> <http://www.w3.org/1999/02/22-rdf-syntax-ns#subject> <https://eventkg.l3s.uni-hannover.de/resource/event_1> .\n"
        b"<relation_1> <roleType> <P710> .\n"
        b"<relation_2> <http://www.w3.org/1999/02/22-rdf-syntax-ns#object> <other> .\n"
    )
    kept, consumed, count = filter_content(data, final=True, ids=ids, reified=True)
    assert kept == data.split(b"<relation_2>")[0]
    assert consumed == len(data)
    assert count == 1


def test_incomplete_reified_group_is_retried() -> None:
    ids = {b"<target>"}
    data = b"<r1> <rdf:type> <Relation> .\n<r2> <http://www.w3.org/1999/02/22-rdf-syntax-ns#object> <target> .\n"
    kept, consumed, count = filter_content(data, final=False, ids=ids, reified=True)
    assert kept == b""
    assert consumed == data.index(b"<r2>")
    assert count == 0
