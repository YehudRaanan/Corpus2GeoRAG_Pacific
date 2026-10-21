"""Independent cloud fixture for S2T 7 count, direction and rank rules."""

import argparse
import json
import sys
from pathlib import Path

from GG_Data.pipeline.event_population import STORE, discovery_query
from GG_Data.pipeline.poc import ROOT, digest


def statement(subject, prop, target, number, rank="normal"):
    return dict(
        id=f"{subject}${number}",
        rank=rank,
        mainsnak=dict(
            property=prop,
            datatype="wikibase-item",
            snaktype="value",
            datavalue=dict(
                type="wikibase-entityid", value={"id": target, "entity-type": "item"}
            ),
        ),
    )


def run(output: Path):
    output.mkdir(parents=True, exist_ok=False)
    records = []
    for qid, endpoints, cls, rank in [
        ("Q10", ["Q1", "Q2"], "Q100", "normal"),
        ("Q11", ["Q1", "Q2", "Q3"], "Q100", "normal"),
        ("Q12", [], "Q100", "preferred"),
        ("Q13", ["Q1"], "Q100", "normal"),
        ("Q14", ["Q1", "Q2", "Q3"], "Q100", "deprecated"),
        ("Q15", ["Q1", "Q2", "Q3"], "Q999", "normal"),
        ("Q16", ["Q1", "Q2", "Q2"], "Q100", "normal"),
    ]:
        claims = {
            "P31": [statement(qid, "P31", cls, 0, rank)],
            "P17": [
                statement(qid, "P17", d, i + 1, "deprecated")
                for i, d in enumerate(endpoints)
            ],
        }
        records.append(dict(id=qid, item=json.dumps(dict(id=qid, claims=claims))))
    source = (
        "(SELECT * FROM UNNEST(["
        + ",".join(
            "STRUCT("
            + json.dumps(r["id"])
            + " AS id,"
            + json.dumps(r["item"])
            + " AS item)"
            for r in records
        )
        + "])) AS w"
    )
    sys.path.insert(0, str(ROOT / "GG_Data/entity_resolution"))
    from bigquery_direct_wikidata import BigQueryData

    client = BigQueryData("geo-hagai-ndvi", STORE)
    types = client.upload_values(["Q100"], "event_type")
    pairs = client.upload_values(
        [
            json.dumps(dict(event_qid=e, daniel_qid=d), sort_keys=True)
            for e, ds in [("Q12", ["Q1", "Q2", "Q3"]), ("Q13", ["Q2", "Q3"])]
            for d in ds
        ],
        "pair",
    )
    sql = discovery_query(source, {"Q1", "Q2", "Q3"}, types, pairs)
    (output / "query.sql").write_text(sql, encoding="utf-8")
    rows = client.query(sql)
    (output / "result.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    assert {r["qid"]: r["daniel_qids"] for r in rows} == {
        q: ["Q1", "Q2", "Q3"] for q in ["Q11", "Q12", "Q13"]
    }
    report = dict(
        status="VERIFIED_CLOUD_DIRECTION_COUNT_RECOGNITION_FIXTURE",
        requests=client.requests,
        checks=[
            "three incoming",
            "three outgoing",
            "mixed directions",
            "duplicate endpoint rejected",
            "deprecated-only classification rejected",
            "unknown class rejected",
            "deprecated relation evidence retained",
        ],
        code_sha256=digest(ROOT / "GG_Data/pipeline/event_population.py"),
    )
    (output / "verification.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(report["status"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
