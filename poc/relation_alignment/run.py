"""Count WarSampo/Wikidata conflict-relation overlap without changing either source."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import requests

WARSA = "https://ldf.fi/warsa/sparql"
WIKIDATA = "https://www.wikidata.org/w/api.php"
CONFLICT_QIDS = {
    "WinterWar": "Q134949",
    "ContinuationWar": "Q122100",
    "SecondWorldWar": "Q362",
}
QUERY = """SELECT ?actor ?wd ?conflict WHERE {
  ?actor <http://www.w3.org/2002/07/owl#sameAs> ?wd ;
         <http://ldf.fi/schema/warsa/actors/hasConflict> ?conflict .
  FILTER(CONTAINS(STR(?wd), "wikidata.org"))
}"""


def main() -> None:
    session = requests.Session()
    session.headers.update({"User-Agent": "GeoAI-relation-alignment-POC/0.1 (research)"})
    response = session.get(
        WARSA,
        params={"query": QUERY},
        headers={"Accept": "application/sparql-results+json"},
        timeout=60,
    )
    response.raise_for_status()
    rows = []
    for binding in response.json()["results"]["bindings"]:
        uri = binding["wd"]["value"]
        match = re.search(r"(?:/entity/|/wiki/)(Q\d+)$", uri)
        conflict = binding["conflict"]["value"].rsplit("/", 1)[-1]
        if match and conflict in CONFLICT_QIDS:
            rows.append(
                {
                    "warsampo_actor": binding["actor"]["value"],
                    "wikidata_actor": match.group(1),
                    "warsampo_conflict": binding["conflict"]["value"],
                    "wikidata_conflict": CONFLICT_QIDS[conflict],
                }
            )

    qids = sorted({row["wikidata_actor"] for row in rows})
    entities = {}
    for start in range(0, len(qids), 50):
        response = session.get(
            WIKIDATA,
            params={
                "action": "wbgetentities",
                "ids": "|".join(qids[start : start + 50]),
                "props": "claims|labels|descriptions",
                "format": "json",
            },
            timeout=60,
        )
        response.raise_for_status()
        entities.update(response.json()["entities"])

    for row in rows:
        entity = entities[row["wikidata_actor"]]
        row["wikidata_label_en"] = entity.get("labels", {}).get("en", {}).get("value")
        row["wikidata_description_en"] = entity.get("descriptions", {}).get("en", {}).get("value")
        row["p607_statements"] = [
            {
                "id": claim["id"],
                "qualifier_properties": sorted(claim.get("qualifiers", {})),
            }
            for claim in entity.get("claims", {}).get("P607", [])
            if claim.get("mainsnak", {})
            .get("datavalue", {})
            .get("value", {})
            .get("id")
            == row["wikidata_conflict"]
        ]

    rows.sort(
        key=lambda row: (
            row["wikidata_actor"], row["wikidata_conflict"], row["warsampo_actor"]
        )
    )
    summary = {
        "scope": "WarSampo owl:sameAs-linked actors with hasConflict; Wikidata P607",
        "warsampo_relation_rows": len(rows),
        "linked_actor_qids_with_hasConflict": len(qids),
        "candidate_shared_relation_pairs": sum(bool(row["p607_statements"]) for row in rows),
        "actor_qids_with_candidate_shared_pair": len(
            {row["wikidata_actor"] for row in rows if row["p607_statements"]}
        ),
        "qualifier_properties_on_matching_p607": dict(
            Counter(
                prop
                for row in rows
                for statement in row["p607_statements"]
                for prop in statement["qualifier_properties"]
            )
        ),
        "rows": rows,
    }
    output = Path(__file__).with_name("overlap.json")
    output.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key != "rows"}, indent=2))


if __name__ == "__main__":
    main()
