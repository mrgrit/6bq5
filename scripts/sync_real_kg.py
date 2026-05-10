"""Pull the REAL bastion KG from a remote bastion API and merge into 6bq5 KG.

Why: the bastion that actually ran ReAct cycles accumulated thousands of
auto-generated Playbook + Experience nodes (`pb-auto-*`, `exp-*`). Locally
we may only see the seed 8. This script pulls the live data over HTTP and
upserts it.

Source endpoint:
  GET  /graph/nodes?types=Playbook,Experience,Skill,Asset,Concept&limit=10000
  GET  /graph/edges?limit=20000
  GET  /history/anchors?limit=...           (optional, large)

Target: 6bq5 data/kg.db

Usage:
  REMOTE_BASTION=http://192.168.0.103:8003 \
  REMOTE_API_KEY=ccc-api-key-2026 \
    python3 scripts/sync_real_kg.py

  # dry run — count only
  python3 scripts/sync_real_kg.py --dry
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

import httpx


HERE = Path(__file__).resolve().parent
DST_DB = (HERE.parent / "data" / "kg.db").resolve()


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DST_DB)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode = WAL")
    c.execute("PRAGMA busy_timeout = 5000")
    return c


def _upsert_node(c, n: dict, mark: str):
    nid = n["id"]
    ntype = n["type"]
    name = n.get("name") or ""
    content = n.get("content") if isinstance(n.get("content"), dict) else {}
    meta = n.get("meta") if isinstance(n.get("meta"), dict) else {}
    meta = {**meta, "synced_from": mark}
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
        (nid, ntype, name[:500], json.dumps(content, ensure_ascii=False),
         json.dumps(meta, ensure_ascii=False)),
    )
    c.execute("DELETE FROM nodes_fts WHERE id = ?", (nid,))
    fts = name + " " + json.dumps(content, ensure_ascii=False)[:2000]
    c.execute(
        "INSERT INTO nodes_fts (id, type, name, content_text) VALUES (?,?,?,?)",
        (nid, ntype, name[:500], fts),
    )


def _upsert_edge(c, e: dict, mark: str):
    src = e.get("src")
    dst = e.get("dst")
    etype = e.get("type")
    weight = float(e.get("weight") or 1.0)
    meta = e.get("meta") if isinstance(e.get("meta"), dict) else {}
    meta = {**meta, "synced_from": mark}
    if not (src and dst and etype):
        return
    try:
        c.execute(
            """
            INSERT INTO edges (src, dst, type, weight, meta)
            VALUES (?,?,?,?,?)
            ON CONFLICT(src, dst, type) DO UPDATE SET
                weight = excluded.weight,
                meta = excluded.meta
            """,
            (src, dst, etype, weight, json.dumps(meta, ensure_ascii=False)),
        )
    except sqlite3.IntegrityError:
        pass


def _fetch_nodes(cli: httpx.Client, base: str, headers: dict, types: str, limit: int = 10000) -> list[dict]:
    # /graph/nodes returns {"nodes": [...]} OR full node records (with content)
    # We try both: enriched + minimal. Enriched needs per-node fetch via /graph/node/{id}.
    out: list[dict] = []
    r = cli.get(f"{base}/graph/nodes", headers=headers, params={"types": types, "limit": limit})
    r.raise_for_status()
    data = r.json()
    rows = data.get("nodes") if isinstance(data, dict) else data
    out.extend(rows or [])
    return out


def _fetch_node_full(cli: httpx.Client, base: str, headers: dict, nid: str) -> dict | None:
    try:
        r = cli.get(f"{base}/graph/node/{nid}", headers=headers, timeout=30)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def _fetch_edges(cli: httpx.Client, base: str, headers: dict, limit: int = 20000) -> list[dict]:
    r = cli.get(f"{base}/graph/edges", headers=headers, params={"limit": limit})
    r.raise_for_status()
    data = r.json()
    return data.get("edges") if isinstance(data, dict) else data


def _stats(cli: httpx.Client, base: str, headers: dict) -> dict:
    r = cli.get(f"{base}/graph/stats", headers=headers)
    r.raise_for_status()
    return r.json()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="show counts only, don't write")
    ap.add_argument("--types", default="Playbook,Experience,Skill,Asset,Concept",
                    help="comma list of types to pull")
    ap.add_argument("--with-content", action="store_true",
                    help="fetch each node's full content via /graph/node/{id} (slower but richer)")
    ap.add_argument("--limit", type=int, default=10000)
    args = ap.parse_args()

    base = os.environ.get("REMOTE_BASTION", "http://192.168.0.103:8003").rstrip("/")
    api_key = os.environ.get("REMOTE_API_KEY", "ccc-api-key-2026")
    headers = {"X-API-Key": api_key}

    print(f"[remote] {base}")
    if not DST_DB.exists():
        print(f"[FATAL] {DST_DB} missing — run scripts/import_kg.py first.", file=sys.stderr)
        sys.exit(1)

    with httpx.Client(timeout=60) as cli:
        st = _stats(cli, base, headers)
        print(f"[remote stats] node_counts={st.get('node_counts')}")
        print(f"[remote stats] edge_counts={st.get('edge_counts')}")

        print(f"\n[1/2] fetching nodes (types={args.types}, limit={args.limit})…")
        nodes = _fetch_nodes(cli, base, headers, args.types, args.limit)
        print(f"      received {len(nodes)} node summaries")

        if args.with_content:
            print("[1b]  fetching full content per node (slow)…")
            full = []
            for i, n in enumerate(nodes):
                if i % 250 == 0:
                    print(f"        {i}/{len(nodes)}")
                f = _fetch_node_full(cli, base, headers, n["id"])
                if f:
                    full.append(f)
                else:
                    full.append(n)
            nodes = full

        print(f"\n[2/2] fetching edges (limit={args.limit*2})…")
        edges = _fetch_edges(cli, base, headers, args.limit * 2)
        print(f"      received {len(edges)} edges")

    if args.dry:
        # Show distribution
        from collections import Counter
        type_counts = Counter(n.get("type") for n in nodes)
        edge_counts = Counter(e.get("type") for e in edges)
        print("\n--- DRY RUN ---")
        print("node types:", dict(type_counts))
        print("edge types:", dict(edge_counts))
        return

    print("\n[write] upserting into local KG…")
    c = _conn()
    try:
        for i, n in enumerate(nodes):
            try:
                _upsert_node(c, n, mark="ccc-remote")
            except Exception as e:
                print(f"  [warn] node {n.get('id')}: {e}", file=sys.stderr)
            if i % 500 == 499:
                c.commit()
                print(f"  nodes {i+1}/{len(nodes)} committed")
        for j, e in enumerate(edges):
            try:
                _upsert_edge(c, e, mark="ccc-remote")
            except Exception as ex:
                print(f"  [warn] edge: {ex}", file=sys.stderr)
            if j % 1000 == 999:
                c.commit()
        c.commit()

        # Final stats
        print()
        for t in ("Playbook", "Experience", "Skill", "Asset", "Concept"):
            n = c.execute("SELECT COUNT(*) FROM nodes WHERE type=?", (t,)).fetchone()[0]
            print(f"  {t:12s} {n}")
        edges_total = c.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        nodes_total = c.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        print(f"  ─────────────")
        print(f"  total nodes  {nodes_total}")
        print(f"  total edges  {edges_total}")
    finally:
        c.close()

    print("\n[done]")


if __name__ == "__main__":
    main()
