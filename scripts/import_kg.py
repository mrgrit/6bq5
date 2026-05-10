"""Import sanitized CCC KG into 6bq5 platform.

Source : /home/opsclaw/ccc/data/bastion_graph.db   (or BASTION_GRAPH_DB env)
Target : ../data/kg.db

Removes anything tagged as precinct6:
  - nodes with id LIKE 'asset:p6:%'
  - nodes with meta JSON containing "precinct6"
  - history_anchors of kind='ioc' (precinct6 IoC dump)
  - dangling edges that referenced removed nodes
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path


SRC = os.environ.get(
    "SRC_KG", "/home/opsclaw/ccc/data/bastion_graph.db"
)
HERE = Path(__file__).resolve().parent
DST = (HERE.parent / "data" / "kg.db").resolve()


def _is_precinct(node_id: str, meta_text: str) -> bool:
    if node_id.startswith("asset:p6:"):
        return True
    if "precinct6" in (meta_text or ""):
        return True
    return False


def main() -> None:
    if not os.path.isfile(SRC):
        print(f"[FATAL] source KG not found: {SRC}", file=sys.stderr)
        sys.exit(1)

    DST.parent.mkdir(parents=True, exist_ok=True)
    if DST.exists():
        DST.unlink()

    print(f"[copy] {SRC} -> {DST}")
    shutil.copy2(SRC, DST)

    con = sqlite3.connect(DST)
    cur = con.cursor()

    # ── 1. precinct6 노드 식별 ──────────────────────────────
    cur.execute("SELECT id, meta FROM nodes")
    drop_ids = [
        nid for (nid, m) in cur.fetchall() if _is_precinct(nid, m or "")
    ]
    print(f"[scan] precinct6 nodes to drop: {len(drop_ids)}")

    # ── 2. 노드 + FTS + 엣지 삭제 ───────────────────────────
    BATCH = 500
    for i in range(0, len(drop_ids), BATCH):
        chunk = drop_ids[i : i + BATCH]
        ph = ",".join("?" * len(chunk))
        cur.execute(f"DELETE FROM nodes WHERE id IN ({ph})", chunk)
        cur.execute(f"DELETE FROM nodes_fts WHERE id IN ({ph})", chunk)
        cur.execute(
            f"DELETE FROM edges WHERE src IN ({ph}) OR dst IN ({ph})",
            chunk + chunk,
        )

    # ── 3. precinct6 IoC anchor 삭제 ────────────────────────
    cur.execute("DELETE FROM history_anchors WHERE kind='ioc'")
    print(f"[scrub] removed history_anchors kind=ioc rows")

    # ── 4. 6bq5 전용 테이블 생성 ────────────────────────────
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS experiments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,        -- 'manipulation' | 'pentest' | 'defense'
            title TEXT,
            description TEXT,
            params TEXT DEFAULT '{}',
            status TEXT DEFAULT 'planned',
            created_at TEXT DEFAULT (datetime('now')),
            started_at TEXT,
            finished_at TEXT
        );

        CREATE TABLE IF NOT EXISTS experiment_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id INTEGER REFERENCES experiments(id) ON DELETE CASCADE,
            phase TEXT,                -- 'attack' | 'defense' | 'replay'
            payload TEXT DEFAULT '{}',
            result TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id INTEGER,
            tag TEXT,
            body TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS kg_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT NOT NULL,
            description TEXT,
            node_count INTEGER,
            edge_count INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS kg_snapshot_nodes (
            snapshot_id INTEGER REFERENCES kg_snapshots(id) ON DELETE CASCADE,
            id TEXT, type TEXT, name TEXT, content TEXT, meta TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_snap_n_snap ON kg_snapshot_nodes(snapshot_id);

        CREATE TABLE IF NOT EXISTS kg_snapshot_edges (
            snapshot_id INTEGER REFERENCES kg_snapshots(id) ON DELETE CASCADE,
            src TEXT, dst TEXT, type TEXT, weight REAL, meta TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_snap_e_snap ON kg_snapshot_edges(snapshot_id);

        CREATE TABLE IF NOT EXISTS poison_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id INTEGER,
            recipe TEXT NOT NULL,
            target_node TEXT,
            payload TEXT,
            stealth_score REAL,
            asr REAL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS rag_traces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id INTEGER,
            query TEXT,
            retrieved TEXT,           -- json: list[node_id]
            generation TEXT,
            poisoned INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS memory_trace (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id INTEGER,
            agent TEXT,
            op TEXT,                  -- 'write' | 'read' | 'rollback'
            node_id TEXT,
            content TEXT,
            ts TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS defense_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            kind TEXT,                -- 'fol' | 'anomaly' | 'centrality' | 'embedding'
            body TEXT NOT NULL,       -- rule body / config
            enabled INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS defense_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id INTEGER REFERENCES defense_rules(id),
            experiment_id INTEGER,
            severity TEXT,
            target TEXT,
            message TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS infra_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            host TEXT, op TEXT, status TEXT, output TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        """
    )

    # 기본 보호 규칙 시드
    seeds = [
        (
            "no_orphan_mitre",
            "fol",
            "for every Concept c with id LIKE 'mitre:%': exists Asset a with edge handles(p,c)",
        ),
        (
            "asset_unique_ip",
            "fol",
            "for every Asset a: meta.ip is unique across nodes",
        ),
        (
            "centrality_spike",
            "centrality",
            json.dumps(
                {
                    "metric": "betweenness",
                    "z_threshold": 3.0,
                    "window": 50,
                }
            ),
        ),
        (
            "anchor_provenance",
            "anomaly",
            json.dumps({"require_signed_provenance": True}),
        ),
    ]
    cur.executemany(
        "INSERT INTO defense_rules (name, kind, body) VALUES (?,?,?)",
        seeds,
    )

    con.commit()

    # ── 5. stats ───────────────────────────────────────────
    cur.execute("SELECT type, COUNT(*) FROM nodes GROUP BY type ORDER BY 2 DESC")
    type_counts = cur.fetchall()
    cur.execute("SELECT COUNT(*) FROM nodes")
    n = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM edges")
    e = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM history_anchors")
    a = cur.fetchone()[0]

    print(f"\n[done] kept nodes={n}  edges={e}  anchors={a}")
    print("[types]")
    for t, c in type_counts:
        print(f"  {t:12s} {c}")

    cur.execute("VACUUM")
    con.close()


if __name__ == "__main__":
    main()
