"""Read-only SQLite query index derived from the complete compact graph JSON."""

from __future__ import annotations

import itertools
import json
import math
import sqlite3
from pathlib import Path

from .compact_format import records, sha256
from .graph_store import GraphStore, Node

RELATION = "CO_OCCURS_ON_PAGE"


class CompactGraphStore(GraphStore):
    @classmethod
    def load(cls, path, *, model_dir=None):
        path = Path(path)
        graph_sha = sha256(path)
        index = path.with_name(path.name + ".sqlite")
        receipt = index.with_name(index.name + ".json")
        cached = index.exists() and receipt.exists()
        if cached:
            proof = json.loads(receipt.read_text(encoding="utf-8"))
            if proof != dict(graph_sha256=graph_sha, index_sha256=sha256(index)):
                raise ValueError("Derived graph index hash changed")
        reader = records(path)
        _, metadata = next(reader)
        nodes = [
            Node.model_validate(row)
            for kind, row in itertools.islice(reader, metadata["node_count"])
        ]
        counts = [n.attributes.get("page_count") for n in nodes]
        pages = [set(n.attributes.get("page_indices", [])) for n in nodes]
        if any(
            type(c) is not int or c <= 0 or c != len(p) for c, p in zip(counts, pages)
        ):
            raise ValueError("Invalid entity page denominator")
        if not cached:
            if index.exists() or receipt.exists():
                raise FileExistsError("Incomplete existing derived index")
            temporary = index.with_name(index.name + ".part")
            if temporary.exists():
                raise FileExistsError(temporary)
            db = sqlite3.connect(temporary)
            try:
                db.execute("PRAGMA journal_mode=OFF")
                db.execute("PRAGMA synchronous=OFF")
                db.execute("PRAGMA temp_store=FILE")
                db.execute("PRAGMA cache_size=-131072")
                db.execute(
                    "CREATE TABLE nodes(i INTEGER PRIMARY KEY,id TEXT UNIQUE,c INTEGER,type TEXT)"
                )
                db.executemany(
                    "INSERT INTO nodes VALUES(?,?,?,?)",
                    [(i, n.id, counts[i], n.type) for i, n in enumerate(nodes)],
                )
                db.execute(
                    "CREATE TABLE pairs(s INTEGER,t INTEGER,n INTEGER,PRIMARY KEY(s,t)) WITHOUT ROWID"
                )
                batch = []
                seen = 0
                for kind, row in reader:
                    if kind != "pair" or not isinstance(row, list) or len(row) != 5:
                        raise ValueError("Invalid compact pair")
                    s, t, n, forward, reverse = row
                    if any(
                        type(x) is not int for x in [s, t, n]
                    ) or not 0 <= s < t < len(nodes):
                        raise ValueError("Invalid compact pair endpoint")
                    if (
                        not 0 < n <= min(counts[s], counts[t])
                        or len(pages[s] & pages[t]) != n
                    ):
                        raise ValueError("Shared-page count differs from membership")
                    if (
                        any(
                            not isinstance(v, (int, float))
                            or isinstance(v, bool)
                            or not math.isfinite(v)
                            for v in [forward, reverse]
                        )
                        or not math.isclose(forward, n / counts[s], rel_tol=1e-12)
                        or not math.isclose(reverse, n / counts[t], rel_tol=1e-12)
                    ):
                        raise ValueError("Invalid directional strength")
                    batch.append((s, t, n))
                    seen += 1
                    if len(batch) >= 16384:
                        db.executemany("INSERT INTO pairs VALUES(?,?,?)", batch)
                        batch.clear()
                db.executemany("INSERT INTO pairs VALUES(?,?,?)", batch)
                if seen != metadata["pair_count"]:
                    raise ValueError("Incomplete compact pair population")
                db.execute("CREATE INDEX pairs_target ON pairs(t,s)")
                db.commit()
            finally:
                db.close()
            temporary.replace(index)
            receipt.write_text(
                json.dumps(dict(graph_sha256=graph_sha, index_sha256=sha256(index))),
                encoding="utf-8",
            )
        else:
            reader.close()
        store = cls(nodes, [])
        store.metadata = metadata
        store.connection = sqlite3.connect(
            index.resolve().as_uri() + "?mode=ro", uri=True
        )
        store.indices = {n.id: i for i, n in enumerate(nodes)}
        store.node_ids = [n.id for n in nodes]
        store.source_pages = {p["page_index"]: p for p in metadata.get("pages", [])}
        store.relation_types = {RELATION}
        if model_dir is not None:
            raise ValueError(
                "Compact Geography must be embedded in the versioned graph"
            )
        return store

    def schema(self):
        result = super().schema()
        count = self.metadata["pair_count"]
        return dict(
            result,
            edge_count=2 * count,
            assertion_count=count,
            relation_types={RELATION: 2 * count},
            relation_semantics="PAGE_CO_OCCURRENCE_ONLY",
            strength_rule="shared_page_count / distinct_pages_containing_source",
            page_scope_id=self.metadata["page_scope_id"],
            geography_status=self.metadata.get("geography_status"),
        )

    def get_entity(self, entity_id, text_chars=1500):
        result = super().get_entity(entity_id, text_chars)
        if result is not None:
            i = self.indices[entity_id]
            result["degree"] = self.connection.execute(
                "SELECT (SELECT count(*) FROM pairs WHERE s=?)+(SELECT count(*) FROM pairs WHERE t=?)",
                (i, i),
            ).fetchone()[0]
        return result

    def _query(self, source_id=None, target_id=None, neighbor_type=None, limit=50):
        if any(k is not None and k not in self.indices for k in [source_id, target_id]):
            return []
        selects, parameters = [], []
        for source, target in [("s", "t"), ("t", "s")]:
            conditions = []
            for column, key in [(source, source_id), (target, target_id)]:
                if key is not None:
                    conditions.append(f"p.{column}=?")
                    parameters.append(self.indices[key])
            selects.append(
                f"SELECT p.{source} source,p.{target} target,p.n FROM pairs p"
                + (" WHERE " + " AND ".join(conditions) if conditions else "")
            )
        sql = (
            "SELECT v.source,v.target,v.n,ns.c,nt.c FROM ("
            + " UNION ALL ".join(selects)
            + ") v JOIN nodes ns ON ns.i=v.source JOIN nodes nt ON nt.i=v.target"
        )
        if neighbor_type:
            sql += " WHERE " + ("ns.type=?" if target_id else "nt.type=?")
            parameters.append(neighbor_type)
        sql += " ORDER BY CAST(v.n AS REAL)/ns.c DESC,v.n DESC,v.source,v.target"
        if limit is not None:
            sql += " LIMIT ?"
            parameters.append(max(0, limit))
        return [self._relation(*r) for r in self.connection.execute(sql, parameters)]

    def _relation(self, s, t, n, source_count, target_count):
        a, b = self.node_ids[s], self.node_ids[t]
        shared = sorted(
            set(self.nodes[a].attributes["page_indices"])
            & set(self.nodes[b].attributes["page_indices"])
        )
        return dict(
            id=f"pair:{min(s,t)}:{max(s,t)}:{s}",
            assertion_id=f"pair:{min(s,t)}:{max(s,t)}",
            source=self.summarize_node(a),
            target=self.summarize_node(b),
            relation=RELATION,
            count=n,
            shared_page_count=n,
            source_page_count=source_count,
            target_page_count=target_count,
            strength=n / source_count,
            reverse_strength=n / target_count,
            denominator_unit="distinct_source_pages",
            shared_page_indices=shared,
            sources=[
                self.source_pages[i]["title"] for i in shared if i in self.source_pages
            ],
            source_pages=[
                self.source_pages[i] for i in shared if i in self.source_pages
            ],
            page_scope_id=self.metadata["page_scope_id"],
            semantics="PAGE_CO_OCCURRENCE_ONLY",
        )

    def find_relations(
        self,
        source_id=None,
        target_id=None,
        relation_type=None,
        date_from=None,
        date_to=None,
        include_sublocations=True,
        limit=50,
    ):
        if (
            date_from
            or date_to
            or (relation_type and relation_type.upper() != RELATION)
        ):
            return []
        return self._query(source_id, target_id, limit=limit)

    def neighbors(
        self,
        entity_id,
        relation_types=None,
        direction="both",
        neighbor_type=None,
        date_from=None,
        date_to=None,
        limit=50,
    ):
        if direction not in {"out", "in", "both"}:
            raise ValueError("Invalid query direction")
        if (
            date_from
            or date_to
            or (relation_types and RELATION not in {r.upper() for r in relation_types})
        ):
            return []
        rows = []
        if direction in {"out", "both"}:
            rows.extend(
                dict(r, neighbor=r["target"])
                for r in self._query(
                    source_id=entity_id, neighbor_type=neighbor_type, limit=limit
                )
            )
        if direction in {"in", "both"}:
            rows.extend(
                dict(r, neighbor=r["source"])
                for r in self._query(
                    target_id=entity_id, neighbor_type=neighbor_type, limit=limit
                )
            )
        return sorted(rows, key=lambda r: (-r["strength"], -r["count"], r["id"]))[
            :limit
        ]

    def locations_of(self, entity_id):
        if entity_id in self.geoms:
            return [dict(self.summarize_node(entity_id), relations=["SELF"])]
        return [
            dict(
                r["target"],
                relations=[r],
                semantics="CO_APPEARANCE_DOES_NOT_ESTABLISH_LOCATION",
            )
            for r in self._query(
                source_id=entity_id, neighbor_type="location", limit=None
            )
            if r["target"]["id"] in self.geoms
        ]

    def what_happened_at(self, lat, lon, radius_km=50, text_chars=400):
        places = self.near(lat, lon, radius_km, type="location")
        relations = [
            r
            for p in places
            for r in self._query(source_id=p["id"], neighbor_type="event", limit=None)
        ]
        event_ids = {r["target"]["id"] for r in relations}
        return dict(
            places=places,
            events=[self.get_entity(i, text_chars) for i in sorted(event_ids)],
            relations=relations,
            semantics="PAGE_CO_OCCURRENCE_ONLY; DOES_NOT_ESTABLISH_WHAT_HAPPENED_AT_A_PLACE",
            date_filter_status="NOT_SUPPORTED_BY_EXISTING_SPATIAL_TOOL",
        )
