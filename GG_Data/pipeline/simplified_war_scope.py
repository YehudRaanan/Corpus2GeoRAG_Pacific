"""Source-backed part-of paths to World War II, independent of page scope."""

from __future__ import annotations

import re
from collections import defaultdict, deque


def wiki_partof(raw: str) -> list[dict]:
    """Only explicit own-page infobox partof fields, not incidental prose links."""
    import mwparserfromhell

    from GG_Data.pipeline.simplified_page_events import raw_links

    result = []
    for template in mwparserfromhell.parse(raw).filter_templates(recursive=False):
        name = re.sub(r"[ _-]", "", str(template.name)).strip().lower()
        if not (name.startswith("infobox") or name == "operationalplan"):
            continue
        for param in template.params:
            field = re.sub(r"[ _-]", "", str(param.name)).strip().lower()
            if field not in {"partof", "partof2"}:
                continue
            value = str(param.value)
            for link in raw_links(value):
                result.append(
                    dict(
                        target_title=link["target_title"],
                        template=str(template.name).strip(),
                        field=str(param.name).strip(),
                        raw_value=value,
                    )
                )
    return result


def war_paths(
    native: dict, own: dict, title_mapping: dict[str, str], context: dict | None = None
) -> dict[str, list[dict]]:
    """Shortest proof paths to Q362 through native or explicit Wiki part-of edges.

    Native P527 is read in reverse. Statements that were deprecated have already
    been removed by acquisition. The caller must pin those source statements.
    Cycles and unrelated roots cannot establish a connection to the war.
    """
    reverse = defaultdict(list)
    for qid, row in sorted(native.items()):
        for parent in row.get("parents", []):
            if parent["property"] != "P361":
                continue
            reverse[parent["qid"]].append(
                dict(parent, **{"from": qid, "to": parent["qid"], "source_qid": qid})
            )
        for child in row.get("children", []):
            reverse[qid].append(
                dict(
                    child,
                    **{
                        "from": child["qid"],
                        "to": qid,
                        "property": "P527_INVERSE",
                        "source_qid": qid,
                    },
                )
            )
    for qid, row in sorted(own.items()):
        for part in row.get("partof", []):
            target = title_mapping.get(part["target_title"])
            if target:
                reverse[target].append(
                    dict(
                        part,
                        **{
                            "from": qid,
                            "to": target,
                            "property": "WIKI_INFOBOX_PARTOF",
                            "source": row.get("source"),
                        },
                    )
                )
    for qid, evidence in sorted((context or {}).items()):
        if evidence.get("status") == "ACCEPT":
            target = evidence.get("target_qid", "Q362")
            reverse[target].append(
                dict(
                    **{
                        "from": qid,
                        "to": target,
                        "property": "WIKI_EXPLICIT_WWII_CONTEXT",
                    },
                    evidence=evidence,
                )
            )
    paths = {"Q362": []}
    queue = deque(["Q362"])
    while queue:
        parent = queue.popleft()
        for edge in sorted(reverse[parent], key=lambda e: (e["from"], e["property"])):
            child = edge["from"]
            if child not in paths:
                paths[child] = [edge] + paths[parent]
                queue.append(child)
    return paths
