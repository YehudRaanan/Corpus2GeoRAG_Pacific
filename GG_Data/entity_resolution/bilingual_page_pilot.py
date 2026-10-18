"""Separate, replayable pilot of the user-approved three-pass matching rules.

Run from the repository root. Network/model caches are on C:; compact evidence
and outputs are written to a new directory on D:. Earlier runs are unchanged.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import html
import json
import logging
import math
import random
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

import pandas as pd
import requests
from bs4 import BeautifulSoup

from generate_candidates import NameIndex, normalize, similarity

ROOT = Path(__file__).resolve().parents[2]
PAGES = [
    "1st Mobile Fleet (Imperial Japanese Navy)",
    "14th Indian Infantry Division",
    "1943 Cairo Declaration",
]
EXTRACTORS = {
    "en": "capitalized noun phrases",
    "ja": "fugashi 1.5.2 + unidic-lite 1.0.8 noun phrases",
}
# Broad, explicit Wikidata classes; inheritance follows P279, never name guesses.
TYPE_ROOTS = {
    "PER": {"Q5"},
    "ORG": {"Q43229", "Q176799"},
    "LOC": {"Q618123", "Q2221906", "Q56061"},
    "DATE": {"Q577", "Q205892", "Q3186692", "Q47018901"},
}
EXCLUDE_CLASSES = {"Q4167410", "Q13406463"}  # disambiguation and Wikimedia lists
POPULATION = (
    "{ ?item wdt:P607/wdt:P361* wd:Q362 } UNION "
    "{ ?item wdt:P1344/wdt:P361* wd:Q362 } UNION "
    "{ ?item wdt:P361+ wd:Q362 } UNION { ?item wdt:P921 wd:Q362 }"
)
LOG = logging.getLogger(__name__)


def dump(path: Path, value: object) -> None:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "wt", encoding="utf-8") as stream:
        json.dump(
            value, stream, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        )


def read(path: Path) -> object:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


class LiveData:
    """Single-client public requests, bounded retries, persistent response cache."""

    def __init__(self, cache: Path) -> None:
        self.cache = cache
        cache.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers["User-Agent"] = (
            "GeoAI-Bilingual-Entity-Pilot/0.1 (research; single client)"
        )
        self.last_request = 0.0
        self.entities: dict[str, dict] = {}
        self.requests: list[dict] = []

    def get(self, url: str, params: dict, post: bool = False) -> dict:
        key = hashlib.sha256(
            json.dumps(
                [url, params] + (["POST"] if post else []), sort_keys=True
            ).encode()
        ).hexdigest()
        path = self.cache / (key + ".json.gz")
        if path.exists():
            saved = read(path)
        else:
            for attempt in range(6):
                time.sleep(max(0.0, 1.1 - (time.monotonic() - self.last_request)))
                self.last_request = time.monotonic()
                try:
                    response = (
                        self.session.post(url, data=params, timeout=180)
                        if post
                        else self.session.get(url, params=params, timeout=180)
                    )
                    if response.status_code in {429, 500, 502, 503, 504}:
                        LOG.warning(
                            "HTTP %s, wait and retry %d: %s %s",
                            response.status_code,
                            attempt + 1,
                            params.get("action", "SPARQL"),
                            params.get("search", ""),
                        )
                        time.sleep(
                            max(
                                float(response.headers.get("Retry-After", 0)),
                                3 * 2**attempt,
                            )
                        )
                        continue
                    response.raise_for_status()
                    payload = response.json()
                    if "error" in payload:
                        if payload["error"].get("code") in {
                            "maxlag",
                            "cirrussearch-too-busy-error",
                            "ratelimited",
                        }:
                            LOG.warning(
                                "API busy, wait and retry %d: %s",
                                attempt + 1,
                                payload["error"].get("code"),
                            )
                            time.sleep(5 * (attempt + 1))
                            continue
                        raise RuntimeError(payload["error"])
                    saved = {
                        "url": url,
                        "params": params,
                        "retrieved_at": datetime.now(timezone.utc).isoformat(),
                        "data": payload,
                    }
                    dump(path, saved)
                    break
                except (requests.RequestException, ValueError):
                    if attempt == 5:
                        raise
                    time.sleep(3 * 2**attempt)
            else:
                raise RuntimeError(f"Request failed after retries: {url} {params}")
        self.requests.append(
            {k: saved[k] for k in saved if k != "data"} | {"cache_key": key}
        )
        return saved["data"]

    def wiki(self, language: str, **params: object) -> dict:
        return self.get(
            f"https://{language}.wikipedia.org/w/api.php",
            {"format": "json", "formatversion": 2, **params},
        )

    def entities_for(self, qids: set[str]) -> None:
        todo = sorted(
            q
            for q in qids
            if q not in self.entities
            or self.entities[q].get("projection") == "CLASS_EDGES_ONLY"
        )
        for offset in range(0, len(todo), 50):
            batch = todo[offset : offset + 50]
            data = self.get(
                "https://www.wikidata.org/w/api.php",
                {
                    "action": "wbgetentities",
                    "format": "json",
                    "ids": "|".join(batch),
                    "props": "labels|aliases|claims|sitelinks",
                    "languages": "en|ja",
                    "sitefilter": "enwiki|jawiki",
                    "maxlag": 10,
                },
            )
            for qid, raw in data["entities"].items():
                properties = {}
                for prop in ("P31", "P279"):
                    properties[prop] = sorted(
                        {
                            claim["mainsnak"]["datavalue"]["value"]["id"]
                            for claim in raw.get("claims", {}).get(prop, [])
                            if claim.get("rank") != "deprecated"
                            and isinstance(
                                claim.get("mainsnak", {})
                                .get("datavalue", {})
                                .get("value"),
                                dict,
                            )
                            and "id" in claim["mainsnak"]["datavalue"]["value"]
                        }
                    )
                names = sorted(
                    {v["value"] for v in raw.get("labels", {}).values()}
                    | {
                        v["value"]
                        for values in raw.get("aliases", {}).values()
                        for v in values
                    }
                    | {v["title"] for v in raw.get("sitelinks", {}).values()}
                )
                self.entities[qid] = {
                    "id": qid,
                    "labels": {
                        lang: v["value"] for lang, v in raw.get("labels", {}).items()
                    },
                    "label": raw.get("labels", {}).get("en", {}).get("value", ""),
                    "aliases": names,
                    "direct_types": properties["P31"],
                    "parents": properties["P279"],
                    "sitelinks": raw.get("sitelinks", {}),
                    "revision": raw.get("lastrevid"),
                    "missing": "missing" in raw,
                }

    def hierarchy(self, ids: set[str]) -> None:
        """Fetch the complete reachable P279 graph, with cycle-safe traversal."""
        self.entities_for(ids)
        frontier = {t for q in ids for t in self.entities[q]["direct_types"]}
        visited = set()
        while frontier:
            # Fetch only the class edges needed for types, instead of downloading
            # every unrelated claim of every ancestor class through the item API.
            missing = sorted(frontier - self.entities.keys())
            for offset in range(0, len(missing), 500):
                batch = missing[offset : offset + 500]
                query = (
                    "SELECT DISTINCT ?item ?parent WHERE { VALUES ?item { "
                    + " ".join("wd:" + q for q in batch)
                    + " } OPTIONAL { ?item p:P279 ?statement . ?statement ps:P279 ?parent . "
                    "FILTER NOT EXISTS { ?statement wikibase:rank wikibase:DeprecatedRank } } }"
                )
                result = self.get(
                    "https://query.wikidata.org/sparql",
                    {"query": query, "format": "json"},
                    post=True,
                )
                for qid in batch:
                    self.entities[qid] = {
                        "id": qid,
                        "label": "",
                        "labels": {},
                        "aliases": [],
                        "parents": [],
                        "direct_types": [],
                        "revision": None,
                        "projection": "CLASS_EDGES_ONLY",
                    }
                for row in result["results"]["bindings"]:
                    if "parent" in row:
                        qid = row["item"]["value"].rsplit("/", 1)[-1]
                        self.entities[qid]["parents"].append(
                            row["parent"]["value"].rsplit("/", 1)[-1]
                        )
            visited.update(frontier)
            frontier = {
                p for q in frontier for p in self.entities[q]["parents"]
            } - visited
        LOG.info(
            "Type closure: %d classes, %d total records",
            len(visited),
            len(self.entities),
        )


def ancestry(types: list[str], metadata: dict[str, dict]) -> set[str]:
    found, todo = set(), list(types)
    while todo:
        qid = todo.pop()
        if qid not in found:
            found.add(qid)
            todo.extend(metadata.get(qid, {}).get("parents", []))
    return found


def categories(entity: dict, metadata: dict[str, dict]) -> set[str]:
    parents = ancestry(entity.get("direct_types", []), metadata)
    if parents & EXCLUDE_CLASSES or not parents:
        return set()
    found = {group for group, roots in TYPE_ROOTS.items() if parents & roots}
    # MISC is the residual known type class, not a wildcard for unknown types.
    return found or {"MISC"}


def choose(
    candidates: list[dict], group: str, metadata: dict[str, dict], rng: random.Random
) -> dict:
    eligible = [
        c
        for c in candidates
        if group == "ANY" or group in categories(metadata[c["entity_id"]], metadata)
    ]
    if eligible:
        highest = max(c["name_similarity"] for c in eligible)
        tied = sorted(
            [
                c
                for c in eligible
                if math.isclose(c["name_similarity"], highest, abs_tol=1e-12)
            ],
            key=lambda c: c["entity_id"],
        )
        return {
            "status": "MATCHED",
            **rng.choice(tied),
            "type_check": "NOT_APPLIED_TO_ARTICLE_PHRASE"
            if group == "ANY"
            else "COMPATIBLE_P31_P279",
            "tied_ids": [c["entity_id"] for c in tied],
        }
    if candidates:
        known = [
            c for c in candidates if categories(metadata[c["entity_id"]], metadata)
        ]
        return {
            "status": "TYPE_MISMATCH" if known else "TYPE_UNKNOWN",
            "rejected": candidates,
        }
    return {"status": "NO_NAME_ABOVE_THRESHOLD"}


def synthetic_id(row: dict, reason: str) -> str:
    prefix = (
        "SYN_TYPE_"
        if reason == "TYPE_MISMATCH"
        else "SYN_TYPE_UNKNOWN_"
        if reason == "TYPE_UNKNOWN"
        else "SYN_"
    )
    return prefix + row["mention_id"].removeprefix("mention-")[:24]


def article(api: LiveData, language: str, title: str) -> dict:
    info = api.wiki(
        language,
        action="query",
        titles=title,
        redirects=1,
        prop="pageprops|info|revisions",
        rvprop="ids|timestamp",
    )
    page = info["query"]["pages"][0]
    if "missing" in page:
        raise ValueError(f"Missing article: {language}:{title}")
    revision = page["revisions"][0]
    parsed = api.wiki(
        language, action="parse", oldid=revision["revid"], prop="text|links"
    )["parse"]
    soup = BeautifulSoup(parsed["text"], "html.parser")
    for node in soup.select(
        ".navbox,.vertical-navbox,.metadata,.mw-editsection,script,style,.catlinks,.noprint"
    ):
        node.decompose()
    targets = set()
    anchors = set()
    for node in soup.select("a[href]"):
        href = node["href"]
        if href.startswith("/wiki/"):
            target = unquote(href[6:].split("#")[0]).replace("_", " ")
        elif href.startswith("./"):
            target = unquote(href[2:].split("#")[0]).replace("_", " ")
        else:
            continue
        if target and ":" not in target:
            targets.add(target)
            anchors.add(node.get_text(" ", strip=True))
    links, mapping = [], {}
    titles = sorted(targets)
    for offset in range(0, len(titles), 50):
        result = api.wiki(
            language,
            action="query",
            titles="|".join(titles[offset : offset + 50]),
            redirects=1,
            prop="pageprops",
            ppprop="wikibase_item",
        )
        query = result["query"]
        mapping.update({x["from"]: x["to"] for x in query.get("normalized", [])})
        mapping.update({x["from"]: x["to"] for x in query.get("redirects", [])})
        for linked in query["pages"]:
            qid = linked.get("pageprops", {}).get("wikibase_item")
            if qid:
                links.append(
                    {"qid": qid, "title": linked["title"], "pageid": linked["pageid"]}
                )
    return {
        "language": language,
        "title": page["title"],
        "pageid": page["pageid"],
        "qid": page.get("pageprops", {}).get("wikibase_item"),
        "revision": revision,
        "url": f"https://{language}.wikipedia.org/w/index.php?oldid={revision['revid']}",
        "html": str(soup),
        "text": soup.get_text("\n", strip=True),
        "links": links,
        "anchor_names": sorted(anchors),
        "redirects": mapping,
    }


def extract_unlinked(articles: list[dict], cache: Path) -> None:
    """Automatic phrase extraction independent of Daniel; no trained NER model.

    All article blocks are traversed. This lexical pilot can miss names; linked
    entities are collected separately even if the phrase extractor misses them.
    """
    sys.path.insert(0, str(Path.home() / ".cache/geoai_bilingual_dependencies"))
    import fugashi
    import unidic_lite

    tagger = fugashi.Tagger('-d "' + unidic_lite.DICDIR + '"')
    english = re.compile(
        r"\b[A-Z][A-Za-z0-9’'–-]*(?:[ \t]+(?:(?:of|the|and|in|for|on|de|van)[ \t]+)?[A-Z][A-Za-z0-9’'–-]*){0,7}"
    )
    for source in articles:
        soup = BeautifulSoup(source["html"], "html.parser")
        blocks = [
            n.get_text(" ", strip=True)
            for n in soup.select(
                "p,li,td,th,dd,dt,h1,h2,h3,h4,figcaption,.thumbcaption"
            )
        ]
        found = set()
        for text in blocks:
            found.update(re.findall(r"(?<!\d)(?:1\d{3}|20\d{2})(?!\d)", text))
            if source["language"] == "en":
                found.update(
                    m.group()
                    for m in english.finditer(text)
                    if " " in m.group()
                    or (m.start() > 1 and text[: m.start()].rstrip()[-1:].islower())
                )
            else:
                nouns = []
                proper = False
                for word in tagger(text):
                    if word.feature.pos1 in {"名詞", "接頭辞"}:
                        nouns.append(word.surface)
                        proper |= word.feature.pos2 == "固有名詞"
                    else:
                        if nouns and proper:
                            found.add("".join(nouns))
                        nouns = []
                        proper = False
                if nouns and proper:
                    found.add("".join(nouns))
        source["extracted_names"] = [
            {"name": name, "type": "ANY", "extractor": EXTRACTORS[source["language"]]}
            for name in sorted(found)
            if len(name) >= 2 and len(name) <= 100
        ]
        LOG.info(
            "Phrase extraction %s: %d phrases",
            source["title"],
            len(source["extracted_names"]),
        )


def page_inventory(
    api: LiveData, articles: list[dict], rng: random.Random
) -> dict[str, set[str]]:
    """Direct article links plus batched, exact bilingual label/alias lookups.

    Keep all exact-name QID candidates. Their identity remains provisional until
    Daniel's compatible-type and trigram rule selects one; no manual choices.
    """
    ids = {link["qid"] for source in articles for link in source["links"]} | {
        a["qid"] for a in articles
    }
    api.entities_for(ids)
    phrases = {}
    for source in articles:
        linked = {x["qid"] for x in source["links"]} | {source["qid"]}
        linked_names = {
            normalize(n) for q in linked for n in api.entities[q]["aliases"]
        }
        source["pool"] = sorted(linked)
        source["searches"] = []
        for item in source["extracted_names"]:
            if normalize(item["name"]) in linked_names:
                continue
            name = item["name"]
            variants = {
                name,
                name.casefold(),
                name[:1].upper() + name[1:].lower(),
                name.title(),
            }
            record = {**item, "variants": sorted(variants), "hits": []}
            source["searches"].append(record)
            for variant in variants:
                phrases.setdefault(variant, []).append(record)
    names = sorted(phrases)
    for offset in range(0, len(names), 80):
        literals = " ".join(
            json.dumps(name, ensure_ascii=False) + "@" + lang
            for name in names[offset : offset + 80]
            for lang in ("en", "ja")
        )
        query = (
            "SELECT DISTINCT ?term ?item WHERE { VALUES ?term { "
            + literals
            + " } { { ?item rdfs:label ?term } UNION { ?item skos:altLabel ?term } } }"
        )
        result = api.get(
            "https://query.wikidata.org/sparql",
            {"query": query, "format": "json"},
            post=True,
        )
        for hit in result["results"]["bindings"]:
            term, qid = hit["term"]["value"], hit["item"]["value"].rsplit("/", 1)[-1]
            if not re.fullmatch(r"Q[1-9]\d*", qid):
                continue  # Properties and lexemes are not entity items.
            for record in phrases[term]:
                record["hits"].append(
                    {"id": qid, "name": term, "language": hit["term"].get("xml:lang")}
                )
        LOG.info(
            "Independent phrase lookups: %d/%d variants",
            min(offset + 80, len(names)),
            len(names),
        )
    candidates = {h["id"] for a in articles for r in a["searches"] for h in r["hits"]}
    api.hierarchy(
        ids | candidates | set().union(*TYPE_ROOTS.values()) | EXCLUDE_CLASSES
    )
    pools = {}
    for source in articles:
        pool = set(source["pool"])
        for record in source["searches"]:
            found = sorted({h["id"] for h in record["hits"]})
            eligible = NameIndex(found, api.entities).find(record["name"], "MISC", 0.8)
            record["candidate_ids"] = [c["entity_id"] for c in eligible]
            record["status"] = (
                "EXACT_NAME_CANDIDATES" if eligible else "NO_EXACT_LABEL_OR_ALIAS"
            )
            pool.update(record["candidate_ids"])
        pool = {
            q
            for q in pool
            if not ancestry(api.entities[q]["direct_types"], api.entities)
            & EXCLUDE_CLASSES
        }
        source["pool"] = sorted(pool)
        pools.setdefault(source["daniel_source"], set()).update(pool)
        LOG.info(
            "%s: %d linked QIDs, %d total provisional QIDs",
            source["title"],
            len(source["links"]),
            len(pool),
        )
    return pools


def fresh_wwii(cache: Path) -> tuple[dict[str, dict], list[dict]]:
    """Freeze fresh query IDs, then collect all EN/JA names in bounded batches."""
    api = LiveData(cache)
    query = "SELECT DISTINCT ?item WHERE { " + POPULATION + " }"
    path = cache / "wwii_ids.json.gz"
    if not path.exists():
        data = api.get(
            "https://query.wikidata.org/sparql", {"query": query, "format": "json"}
        )
        dump(
            path,
            {
                "query": query,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "data": data,
            },
        )
    saved = read(path)
    if saved["query"] != query:
        raise ValueError("WWII cache query differs from this method")
    evidence = [
        {
            "query": query,
            "retrieved_at": saved["retrieved_at"],
            "response_sha256": digest(path),
        }
    ]
    metadata = {
        row["item"]["value"].rsplit("/", 1)[-1]: {
            "label": "",
            "aliases": [],
            "direct_types": [],
        }
        for row in saved["data"]["results"]["bindings"]
    }
    ids = sorted(metadata)
    for offset in range(0, len(ids), 5000):
        batch = ids[offset : offset + 5000]
        names_query = (
            "SELECT DISTINCT ?item ?name WHERE { VALUES ?item { "
            + " ".join("wd:" + q for q in batch)
            + ' } { { ?item rdfs:label ?name } UNION { ?item skos:altLabel ?name } } FILTER(LANG(?name) IN ("en","ja")) }'
        )
        data = api.get(
            "https://query.wikidata.org/sparql",
            {"query": names_query, "format": "json"},
            post=True,
        )
        evidence.append(api.requests[-1])
        for row in data["results"]["bindings"]:
            qid = row["item"]["value"].rsplit("/", 1)[-1]
            if qid not in batch:
                raise ValueError("WWII names outside frozen population")
            name = row["name"]["value"]
            metadata[qid]["aliases"].append(name)
            if row["name"].get("xml:lang") == "en" and not metadata[qid]["label"]:
                metadata[qid]["label"] = name
        LOG.info(
            "WWII bilingual names collected: %d/%d IDs",
            min(offset + 5000, len(ids)),
            len(ids),
        )
    for entity in metadata.values():
        entity["aliases"] = sorted(set(entity["aliases"]))
    return metadata, evidence


def execute(
    output: Path, cache: Path, seed: int, metadata_snapshot: Path | None = None
) -> None:
    execution_code_sha256 = digest(Path(__file__))
    if output.exists():
        previous = read(output / "run_manifest.json")
        if (
            previous.get("status") != "IN_PROGRESS"
            or previous.get("pages") != PAGES
            or previous.get("seed") != seed
        ):
            raise FileExistsError(
                "Completed or unrelated outputs cannot be overwritten"
            )
    else:
        output.mkdir(parents=True)
    dump(
        output / "run_manifest.json",
        {"status": "IN_PROGRESS", "seed": seed, "pages": PAGES},
    )
    api = LiveData(cache)
    if metadata_snapshot is not None:
        prior = read(metadata_snapshot.parent / "run_manifest.json")
        if prior["status"] != "COMPLETED" or digest(metadata_snapshot) != prior[
            "outputs"
        ].get(metadata_snapshot.name):
            raise ValueError(
                "Metadata snapshot must belong to a verified completed run"
            )
        api.entities = {
            q: e
            for q, e in read(metadata_snapshot).items()
            if re.fullmatch(r"Q[1-9]\d*", q)
        }
        api.requests.append(
            {
                "metadata_snapshot": str(metadata_snapshot),
                "sha256": digest(metadata_snapshot),
                "source_manifest_sha256": digest(
                    metadata_snapshot.parent / "run_manifest.json"
                ),
            }
        )
    rng = random.Random(seed)
    raw_path = ROOT / "Data/external/daniel_20261017.parquet"
    if (
        digest(raw_path)
        != "dcd51dfa237b63378279ced4f9739a45d8cf8ce3991579f20848295448f83f16"
    ):
        raise ValueError("Daniel input differs from the pinned upload")
    raw = pd.read_parquet(raw_path)
    selected = raw[raw.Source.isin(PAGES)]
    rows = []
    for number, row in selected.iterrows():
        data = json.loads(row.to_json(force_ascii=False))
        # Original input position makes even duplicate spans distinct mentions.
        mid = (
            "mention-"
            + hashlib.sha256(
                json.dumps(
                    [
                        int(number),
                        data["Source"],
                        data["Index"],
                        data["start"],
                        data["end"],
                        data["entity_group"],
                    ],
                    ensure_ascii=False,
                ).encode()
            ).hexdigest()
        )
        rows.append(
            {
                "input_row_number": int(number),
                "mention_id": mid,
                "raw": data,
                "attempts": [],
            }
        )
    if set(selected.Source) != set(PAGES):
        raise ValueError("One selected source is absent")
    articles = []
    for title in PAGES:
        LOG.info("Read source article: %s", title)
        english = article(api, "en", title)
        english["daniel_source"] = title
        api.entities_for({english["qid"]})
        japanese_title = (
            api.entities[english["qid"]]["sitelinks"].get("jawiki", {}).get("title")
        )
        english["japanese_counterpart"] = japanese_title
        articles.append(english)
        if japanese_title:
            japanese = article(api, "ja", japanese_title)
            japanese["daniel_source"] = title
            if japanese["qid"] != english["qid"]:
                raise ValueError("Language counterparts have different QIDs")
            articles.append(japanese)
    extract_unlinked(articles, cache)
    pools = page_inventory(api, articles, rng)
    dump(output / "articles_and_page_inventory.json.gz", articles)
    page_indexes = {
        page: NameIndex(sorted(pool), api.entities) for page, pool in pools.items()
    }

    def run_stage(stage: str, target: list[dict], indexes: dict | NameIndex) -> None:
        for row in target:
            index = (
                indexes[row["raw"]["Source"]] if isinstance(indexes, dict) else indexes
            )
            candidates = index.find(row["raw"]["word"], "MISC", 0.8)
            decision = choose(
                candidates,
                row["raw"]["entity_group"],
                api.entities,
                random.Random(f"{seed}:{stage}:{row['mention_id']}"),
            )
            row["attempts"].append({"stage": stage, **decision})
            if decision["status"] == "MATCHED":
                row.update(
                    {
                        "assigned_id": decision["entity_id"],
                        "matched_stage": stage,
                        "matched_name": decision["matched_name"],
                        "score": decision["name_similarity"],
                    }
                )
        LOG.info(
            "%s: %d/%d matched",
            stage,
            sum(r.get("matched_stage") == stage for r in target),
            len(target),
        )

    run_stage("PAGE_EN_JA", rows, page_indexes)
    frozen = sorted({r["assigned_id"] for r in rows if "assigned_id" in r})
    run_stage(
        "ALREADY_MATCHED",
        [r for r in rows if "assigned_id" not in r],
        NameIndex(frozen, api.entities),
    )
    unresolved = [r for r in rows if "assigned_id" not in r]
    world, query_evidence = fresh_wwii(cache)
    LOG.info(
        "Fresh WWII population: %d IDs, %d bilingual names",
        len(world),
        sum(len(v["aliases"]) for v in world.values()),
    )
    world_index = NameIndex(sorted(world), world)
    needed = {
        c["entity_id"]
        for row in rows  # Also support offline notebook replay at higher thresholds.
        for c in world_index.find(row["raw"]["word"], "MISC", 0.8)
    }
    api.hierarchy(needed)
    run_stage("FRESH_WWII", unresolved, world_index)
    for row in rows:
        if "assigned_id" not in row:
            statuses = {a["status"] for a in row["attempts"]}
            reason = (
                "TYPE_MISMATCH"
                if "TYPE_MISMATCH" in statuses
                else "TYPE_UNKNOWN"
                if "TYPE_UNKNOWN" in statuses
                else "NO_NAME_ABOVE_THRESHOLD"
            )
            row.update(
                {
                    "assigned_id": synthetic_id(row, reason),
                    "matched_stage": "SYNTHETIC",
                    "unresolved_reason": reason,
                }
            )
    # Re-read selected raw rows, and prove exact identity/scope/threshold/type rules.
    assert len(rows) == len(selected)
    assert len({r["mention_id"] for r in rows}) == len(rows)
    assert all(re.fullmatch(r"Q[1-9]\d*", q) for pool in pools.values() for q in pool)
    synthetic = [r["assigned_id"] for r in rows if r["matched_stage"] == "SYNTHETIC"]
    assert len(set(synthetic)) == len(synthetic)
    for row in rows:
        assert row["raw"] == json.loads(
            raw.loc[row["input_row_number"]].to_json(force_ascii=False)
        )
        if row["matched_stage"] != "SYNTHETIC":
            qid = row["assigned_id"]
            assert row["raw"]["entity_group"] in categories(
                api.entities[qid], api.entities
            )
            assert row["score"] >= 0.8
            assert math.isclose(
                similarity(row["raw"]["word"], row["matched_name"]), row["score"]
            )
            if row["matched_stage"] == "PAGE_EN_JA":
                assert qid in pools[row["raw"]["Source"]]
            elif row["matched_stage"] == "ALREADY_MATCHED":
                assert qid in frozen
            else:
                assert qid in world
    summary = {
        "mentions": len(rows),
        "by_stage": dict(Counter(r["matched_stage"] for r in rows)),
        "by_page": {
            page: dict(
                Counter(r["matched_stage"] for r in rows if r["raw"]["Source"] == page)
            )
            for page in PAGES
        },
        "by_type": {
            group: dict(
                Counter(
                    r["matched_stage"]
                    for r in rows
                    if r["raw"]["entity_group"] == group
                )
            )
            for group in sorted(selected.entity_group.unique())
        },
        "unresolved_reasons": dict(
            Counter(
                r.get("unresolved_reason")
                for r in rows
                if r["matched_stage"] == "SYNTHETIC"
            )
        ),
        "page_pool_sizes": {page: len(pool) for page, pool in pools.items()},
        "japanese_articles": {
            a["daniel_source"]: a["japanese_counterpart"]
            for a in articles
            if a["language"] == "en"
        },
        "fresh_wwii_ids": len(world),
        "fresh_wwii_ids_without_bilingual_name": sum(
            not e["aliases"] for e in world.values()
        ),
        "stage_2_frozen_ids": frozen,
        "verification": "PASS: denominator, raw row equality, separate synthetic IDs, score, compatible type, stage pool membership",
    }
    dump(output / "matches.json.gz", rows)
    dump(output / "entity_metadata.json.gz", api.entities)
    dump(output / "fresh_wwii_names.json.gz", world)
    dump(output / "request_evidence.json.gz", api.requests)
    dump(output / "summary.json", summary)
    with (output / "matches.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        fields = [
            "input_row_number",
            "Source",
            "word",
            "entity_group",
            "assigned_id",
            "matched_stage",
            "matched_name",
            "score",
            "unresolved_reason",
        ]
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {field: row.get(field, row["raw"].get(field, "")) for field in fields}
            )
    report(output, rows, summary, api.entities, articles)
    if digest(Path(__file__)) != execution_code_sha256:
        raise RuntimeError("Code changed during execution; resume the incomplete run")
    manifest = {
        "status": "COMPLETED",
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "pages": PAGES,
        "seed": seed,
        "threshold": 0.8,
        "similarity": "Unicode-normalized character trigram Dice",
        "type_roots": {k: sorted(v) for k, v in TYPE_ROOTS.items()},
        "extractors": EXTRACTORS,
        "fresh_wwii_queries": query_evidence,
        "input_sha256": digest(raw_path),
        "code_sha256": execution_code_sha256,
        "shared_similarity_code_sha256": digest(
            Path(__file__).with_name("generate_candidates.py")
        ),
        "outputs": {
            p.name: digest(p) for p in output.iterdir() if p.name != "run_manifest.json"
        },
        "limitations": [
            "Article links plus lexical phrase extraction and exact bilingual label/alias lookup are not guaranteed exhaustive; no trained NER or matching model is used. Homonymous unlinked phrases can add unrelated provisional QIDs.",
            "Fresh WWII population is defined by the saved explicit-statement query, not every semantically WWII-related entity.",
            "Trigram scores are similarities, not correctness probabilities; equal-highest QID ties use saved-seed random selection.",
            "Type categories use the saved broad root policy; MISC is a residual known category.",
            "Synthetic IDs identify mentions, not verified new real-world entities.",
        ],
    }
    dump(output / "run_manifest.json", manifest)
    LOG.info("COMPLETED %s", json.dumps(summary, ensure_ascii=True))


def report(
    output: Path, rows: list[dict], summary: dict, metadata: dict, articles: list[dict]
) -> None:
    def esc(value: object) -> str:
        return html.escape(str(value))

    table_rows = []
    for row in rows:
        attempts = " → ".join(
            a["stage"]
            + ": "
            + a["status"]
            + (
                " ["
                + "; ".join(
                    c["entity_id"]
                    + " "
                    + c["matched_name"]
                    + f" ({c['name_similarity']:.3f}; "
                    + ",".join(sorted(categories(metadata[c["entity_id"]], metadata)))
                    + ")"
                    for c in a.get("rejected", [])[:3]
                )
                + "]"
                if a.get("rejected")
                else ""
            )
            for a in row["attempts"]
        )
        values = [
            row["raw"]["Source"],
            row["raw"]["word"],
            row["raw"]["entity_group"],
            row["assigned_id"],
            row["matched_stage"],
            row.get("matched_name", ""),
            f"{row['score']:.3f}" if "score" in row else "",
            row.get("unresolved_reason", ""),
            attempts,
        ]
        table_rows.append(
            "<tr>" + "".join("<td>" + esc(v) + "</td>" for v in values) + "</tr>"
        )
    headers = [
        "Page",
        "Daniel mention",
        "Type",
        "Assigned ID",
        "Matched stage",
        "Reference name",
        "Similarity",
        "Unresolved reason",
        "All steps",
    ]
    inventory_html = "<h2>Independent page entity lists</h2>"
    inventory_rows = []
    for page in PAGES:
        sources = [a for a in articles if a["daniel_source"] == page]
        pool = sorted({q for a in sources for q in a["pool"]})
        inventory_html += (
            "<details><summary>" + esc(page) + f" — {len(pool)} QIDs</summary><p>"
        )
        inventory_html += " | ".join(
            f'<a href="{esc(a["url"])}">{esc(a["language"])} page {a["pageid"]}, revision {a["revision"]["revid"]}</a>'
            for a in sources
        )
        inventory_html += "</p><table><thead><tr><th>QID</th><th>English</th><th>Japanese</th><th>Compatible types</th></tr></thead><tbody>"
        for qid in pool:
            entity = metadata[qid]
            record = {
                "Source": page,
                "qid": qid,
                "english": entity["labels"].get("en", ""),
                "japanese": entity["labels"].get("ja", ""),
                "types": ",".join(sorted(categories(entity, metadata))),
            }
            inventory_rows.append(record)
            inventory_html += (
                "<tr>"
                + "".join(
                    "<td>" + esc(record[k]) + "</td>"
                    for k in ("qid", "english", "japanese", "types")
                )
                + "</tr>"
            )
        inventory_html += "</tbody></table></details>"
    with (output / "page_inventory.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as stream:
        writer = csv.DictWriter(
            stream, ["Source", "qid", "english", "japanese", "types"]
        )
        writer.writeheader()
        writer.writerows(inventory_rows)
    document = (
        """<!doctype html><meta charset='utf-8'><title>Bilingual matching pilot</title>
    <style>body{font:15px system-ui;margin:25px}table{border-collapse:collapse;width:100%}th,td{border:1px solid #ddd;padding:7px;text-align:left}th{background:#eaf0f7;position:sticky;top:0}tr:nth-child(even){background:#fafafa}input{padding:10px;width:420px}</style>
    <h1>Bilingual matching pilot — all selected mentions</h1>
    <p>1. English + Japanese article entities → 2. Frozen already-matched IDs → 3. Fresh WWII Wikidata → 4. One synthetic ID per unresolved mention.</p>
    <p>Highest compatible name similarity ≥ 0.80. Random ties use a saved seed. Scores are not correctness probabilities.</p>
    <p>Full body, tables and bibliography are processed. Automatic extraction and exact label/alias lookup can miss entities. Ambiguous phrases can add unrelated provisional candidates. The Indian division has no Japanese counterpart in the retrieved Wikidata record.</p>
    <input id='search' placeholder='Filter page, mention, ID, type or stage'>
    """
        + "<pre>"
        + esc(json.dumps(summary, ensure_ascii=False, indent=2))
        + "</pre><table><thead><tr>"
        + "".join("<th>" + esc(h) + "</th>" for h in headers)
        + "</tr></thead><tbody>"
        + "".join(table_rows)
        + "</tbody></table>"
        + inventory_html
        + """<script>document.querySelector('#search').oninput=e=>{let q=e.target.value.toLowerCase();document.querySelectorAll('tbody tr').forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q))}</script>"""
    )
    (output / "report.html").write_text(document, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--cache",
        type=Path,
        default=Path.home() / ".cache/geoai_bilingual_pilot_20261018",
    )
    parser.add_argument("--seed", type=int, default=20261018)
    parser.add_argument(
        "--metadata-snapshot",
        type=Path,
        help="Reuse verified item/type records from a completed run",
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    execute(args.output, args.cache, args.seed, args.metadata_snapshot)
