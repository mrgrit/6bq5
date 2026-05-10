"""KG read / write / centrality / diff helpers (uses CCC's schema verbatim)."""
from __future__ import annotations

import json
import time
from typing import Any

import networkx as nx

from .db import conn, row_to_dict


# ── 노드 / 엣지 ───────────────────────────────────────────────────────

def list_nodes(
    type_filter: str | None = None,
    q: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    sql = "SELECT id, type, name, content, meta, updated_at FROM nodes"
    where = []
    args: list[Any] = []
    if type_filter:
        where.append("type = ?")
        args.append(type_filter)
    if q:
        where.append("(name LIKE ? OR id LIKE ?)")
        args += [f"%{q}%", f"%{q}%"]
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
    args += [limit, offset]
    with conn() as c:
        rows = c.execute(sql, args).fetchall()
    return [row_to_dict(r) for r in rows]


def get_node(node_id: str) -> dict | None:
    with conn() as c:
        row = c.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
    return row_to_dict(row) if row else None


def upsert_node(
    node_id: str,
    type_: str,
    name: str,
    content: dict | None = None,
    meta: dict | None = None,
) -> dict:
    content_text = json.dumps(content or {}, ensure_ascii=False)
    meta_text = json.dumps(meta or {}, ensure_ascii=False)
    fts_text = (name or "") + " " + (content or {}).get("description", "")
    with conn() as c:
        c.execute(
            """
            INSERT INTO nodes (id, type, name, content, meta, updated_at)
            VALUES (?,?,?,?,?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                content = excluded.content,
                meta = excluded.meta,
                updated_at = datetime('now')
            """,
            (node_id, type_, name, content_text, meta_text),
        )
        c.execute("DELETE FROM nodes_fts WHERE id = ?", (node_id,))
        c.execute(
            "INSERT INTO nodes_fts (id, type, name, content_text) VALUES (?,?,?,?)",
            (node_id, type_, name, fts_text),
        )
    n = get_node(node_id)
    assert n is not None
    return n


def delete_node(node_id: str) -> int:
    with conn() as c:
        n = c.execute("DELETE FROM nodes WHERE id = ?", (node_id,)).rowcount
        c.execute("DELETE FROM nodes_fts WHERE id = ?", (node_id,))
        c.execute(
            "DELETE FROM edges WHERE src = ? OR dst = ?", (node_id, node_id)
        )
    return n


def list_edges(limit: int = 5000) -> list[dict]:
    with conn() as c:
        rows = c.execute(
            "SELECT id, src, dst, type, weight, meta FROM edges LIMIT ?",
            (limit,),
        ).fetchall()
    return [row_to_dict(r) for r in rows]


def add_edge(
    src: str, dst: str, type_: str, weight: float = 1.0, meta: dict | None = None
) -> int:
    with conn() as c:
        cur = c.execute(
            """
            INSERT INTO edges (src, dst, type, weight, meta)
            VALUES (?,?,?,?,?)
            ON CONFLICT(src, dst, type) DO UPDATE SET
                weight = edges.weight + excluded.weight,
                meta = excluded.meta
            """,
            (src, dst, type_, weight, json.dumps(meta or {})),
        )
        return cur.lastrowid or 0


def delete_edge(edge_id: int) -> int:
    with conn() as c:
        return c.execute("DELETE FROM edges WHERE id = ?", (edge_id,)).rowcount


def stats() -> dict:
    with conn() as c:
        node_counts = {
            r["type"]: r["n"]
            for r in c.execute(
                "SELECT type, COUNT(*) AS n FROM nodes GROUP BY type"
            )
        }
        edge_counts = {
            r["type"]: r["n"]
            for r in c.execute(
                "SELECT type, COUNT(*) AS n FROM edges GROUP BY type"
            )
        }
        anchor_counts = {
            r["kind"]: r["n"]
            for r in c.execute(
                "SELECT kind, COUNT(*) AS n FROM history_anchors GROUP BY kind"
            )
        }
        last10 = [
            row_to_dict(r)
            for r in c.execute(
                "SELECT id, type, name, updated_at FROM nodes "
                "ORDER BY updated_at DESC LIMIT 10"
            )
        ]
        exp = c.execute("SELECT COUNT(*) AS n FROM experiments").fetchone()["n"]
        notes = c.execute("SELECT COUNT(*) AS n FROM notes").fetchone()["n"]
        alerts = c.execute("SELECT COUNT(*) AS n FROM defense_alerts").fetchone()["n"]
    return {
        "node_counts": node_counts,
        "edge_counts": edge_counts,
        "anchor_counts": anchor_counts,
        "total_nodes": sum(node_counts.values()),
        "total_edges": sum(edge_counts.values()),
        "total_anchors": sum(anchor_counts.values()),
        "experiments": exp,
        "notes": notes,
        "alerts": alerts,
        "recent": last10,
    }


def search_fts(query: str, limit: int = 30) -> list[dict]:
    safe = query.replace('"', '""')
    with conn() as c:
        rows = c.execute(
            "SELECT n.* FROM nodes_fts f JOIN nodes n ON n.id = f.id "
            "WHERE nodes_fts MATCH ? ORDER BY bm25(nodes_fts) LIMIT ?",
            (f'"{safe}"', limit),
        ).fetchall()
    return [row_to_dict(r) for r in rows]


# ── 그래프 (networkx 빌드) ────────────────────────────────────────────

def build_nx() -> nx.DiGraph:
    g = nx.DiGraph()
    with conn() as c:
        for r in c.execute("SELECT id, type, name FROM nodes"):
            g.add_node(r["id"], type=r["type"], name=r["name"])
        for r in c.execute("SELECT src, dst, type, weight FROM edges"):
            g.add_edge(
                r["src"], r["dst"], type=r["type"], weight=float(r["weight"] or 1.0)
            )
    return g


def importance_table(top_k: int = 50) -> list[dict]:
    """PageRank + betweenness + degree per node — node-value matrix view."""
    g = build_nx()
    if g.number_of_nodes() == 0:
        return []
    try:
        pr = nx.pagerank(g, alpha=0.85, max_iter=100)
    except Exception:
        pr = {n: 0.0 for n in g.nodes}
    deg_in = dict(g.in_degree())
    deg_out = dict(g.out_degree())
    # Betweenness on a sampled subgraph if the graph is big (>500)
    if g.number_of_nodes() > 500:
        sample = list(g.nodes)[:500]
        sub = g.subgraph(sample).copy()
        try:
            bw = nx.betweenness_centrality(sub.to_undirected(), k=min(50, len(sub)))
        except Exception:
            bw = {}
    else:
        try:
            bw = nx.betweenness_centrality(g.to_undirected())
        except Exception:
            bw = {}
    rows = []
    for n in g.nodes:
        rows.append(
            {
                "id": n,
                "type": g.nodes[n].get("type"),
                "name": g.nodes[n].get("name"),
                "pagerank": pr.get(n, 0.0),
                "betweenness": bw.get(n, 0.0),
                "in_degree": deg_in.get(n, 0),
                "out_degree": deg_out.get(n, 0),
            }
        )
    rows.sort(key=lambda r: r["pagerank"], reverse=True)
    return rows[:top_k]


def neighbors_subgraph(node_id: str, hops: int = 1) -> dict:
    """{nodes: [...], edges: [...]} for graph viewer."""
    g = build_nx()
    if node_id not in g:
        return {"nodes": [], "edges": []}
    seen: set[str] = {node_id}
    frontier = {node_id}
    for _ in range(max(0, hops)):
        nxt: set[str] = set()
        for n in frontier:
            nxt.update(g.successors(n))
            nxt.update(g.predecessors(n))
        seen.update(nxt)
        frontier = nxt
    nodes = [
        {"id": n, "type": g.nodes[n].get("type"), "name": g.nodes[n].get("name")}
        for n in seen
    ]
    edges = []
    for u, v, d in g.edges(data=True):
        if u in seen and v in seen:
            edges.append({"src": u, "dst": v, "type": d.get("type"), "weight": d.get("weight", 1.0)})
    return {"nodes": nodes, "edges": edges, "anchor": node_id}


# ── 스냅샷 + diff ─────────────────────────────────────────────────────

def take_snapshot(label: str, description: str = "") -> dict:
    with conn() as c:
        nodes = c.execute(
            "SELECT id, type, name, content, meta FROM nodes"
        ).fetchall()
        edges = c.execute(
            "SELECT src, dst, type, weight, meta FROM edges"
        ).fetchall()
        cur = c.execute(
            "INSERT INTO kg_snapshots (label, description, node_count, edge_count) VALUES (?,?,?,?)",
            (label, description, len(nodes), len(edges)),
        )
        sid = cur.lastrowid
        c.executemany(
            "INSERT INTO kg_snapshot_nodes (snapshot_id, id, type, name, content, meta) VALUES (?,?,?,?,?,?)",
            [(sid, *r) for r in nodes],
        )
        c.executemany(
            "INSERT INTO kg_snapshot_edges (snapshot_id, src, dst, type, weight, meta) VALUES (?,?,?,?,?,?)",
            [(sid, *r) for r in edges],
        )
    return {
        "id": sid,
        "label": label,
        "description": description,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }


def list_snapshots() -> list[dict]:
    with conn() as c:
        return [
            row_to_dict(r)
            for r in c.execute(
                "SELECT id, label, description, node_count, edge_count, created_at FROM kg_snapshots ORDER BY id DESC"
            )
        ]


def diff_snapshot_against_live(snap_id: int) -> dict:
    with conn() as c:
        snap_nodes = {
            r["id"]: row_to_dict(r)
            for r in c.execute(
                "SELECT id, type, name, content, meta FROM kg_snapshot_nodes WHERE snapshot_id = ?",
                (snap_id,),
            )
        }
        snap_edges = {
            (r["src"], r["dst"], r["type"]): row_to_dict(r)
            for r in c.execute(
                "SELECT src, dst, type, weight, meta FROM kg_snapshot_edges WHERE snapshot_id = ?",
                (snap_id,),
            )
        }
        live_nodes = {
            r["id"]: row_to_dict(r)
            for r in c.execute("SELECT id, type, name, content, meta FROM nodes")
        }
        live_edges = {
            (r["src"], r["dst"], r["type"]): row_to_dict(r)
            for r in c.execute("SELECT src, dst, type, weight, meta FROM edges")
        }

    added_nodes = [v for k, v in live_nodes.items() if k not in snap_nodes]
    removed_nodes = [v for k, v in snap_nodes.items() if k not in live_nodes]
    changed_nodes = []
    for k, v in live_nodes.items():
        if k in snap_nodes and (
            v.get("name") != snap_nodes[k].get("name")
            or v.get("content") != snap_nodes[k].get("content")
            or v.get("meta") != snap_nodes[k].get("meta")
        ):
            changed_nodes.append({"id": k, "before": snap_nodes[k], "after": v})

    added_edges = [v for k, v in live_edges.items() if k not in snap_edges]
    removed_edges = [v for k, v in snap_edges.items() if k not in live_edges]

    return {
        "snapshot_id": snap_id,
        "summary": {
            "nodes_added": len(added_nodes),
            "nodes_removed": len(removed_nodes),
            "nodes_changed": len(changed_nodes),
            "edges_added": len(added_edges),
            "edges_removed": len(removed_edges),
        },
        "added_nodes": added_nodes,
        "removed_nodes": removed_nodes,
        "changed_nodes": changed_nodes,
        "added_edges": added_edges,
        "removed_edges": removed_edges,
    }


def restore_snapshot(snap_id: int) -> dict:
    """Rollback: drop all live nodes/edges, repopulate from snapshot."""
    with conn() as c:
        c.execute("DELETE FROM nodes")
        c.execute("DELETE FROM nodes_fts")
        c.execute("DELETE FROM edges")
        rows = c.execute(
            "SELECT id, type, name, content, meta FROM kg_snapshot_nodes WHERE snapshot_id = ?",
            (snap_id,),
        ).fetchall()
        for r in rows:
            c.execute(
                "INSERT INTO nodes (id, type, name, content, meta) VALUES (?,?,?,?,?)",
                (r["id"], r["type"], r["name"], r["content"], r["meta"]),
            )
            c.execute(
                "INSERT INTO nodes_fts (id, type, name, content_text) VALUES (?,?,?,?)",
                (r["id"], r["type"], r["name"], r["name"]),
            )
        edges = c.execute(
            "SELECT src, dst, type, weight, meta FROM kg_snapshot_edges WHERE snapshot_id = ?",
            (snap_id,),
        ).fetchall()
        for e in edges:
            c.execute(
                "INSERT INTO edges (src, dst, type, weight, meta) VALUES (?,?,?,?,?)",
                (e["src"], e["dst"], e["type"], e["weight"], e["meta"]),
            )
    return {"restored_from": snap_id, "nodes": len(rows), "edges": len(edges)}
