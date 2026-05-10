"""(Re-)import sanitized CCC KG into 6bq5 platform.

The repository ALREADY ships `data/kg.db` (precinct6 stripped). You only need
this script when you want to refresh from a *new* CCC source.

Source: env `SRC_KG` (default tries common CCC paths, then aborts).
Target: `../data/kg.db` (overwritten — back up first if needed).

Removes anything tagged as precinct6 (any of):
  - nodes with id LIKE 'asset:p6:%'
  - nodes with id LIKE 'asset:100.64.%'           (precinct6 sample subnet)
  - nodes with id LIKE 'asset:172.%' AND no edges (precinct6 random hosts)
  - nodes with meta or content containing "precinct6"
  - history_anchors of kind='ioc' (precinct6 IoC dump)
  - history_anchors with body / related_ids referencing precinct6 IPs
  - dangling edges that referenced removed nodes
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
DST = (HERE.parent / "data" / "kg.db").resolve()


def _resolve_src() -> str:
    if os.environ.get("SRC_KG"):
        return os.environ["SRC_KG"]
    candidates = [
        os.path.expanduser("~/ccc/data/bastion_graph.db"),
        "/home/opsclaw/ccc/data/bastion_graph.db",
        "/opt/ccc/data/bastion_graph.db",
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    print(
        "[FATAL] no CCC bastion_graph.db found.\n"
        "Set SRC_KG=/path/to/bastion_graph.db, or skip this script — the\n"
        "repository already includes a pre-sanitized data/kg.db that works\n"
        "out of the box.",
        file=sys.stderr,
    )
    sys.exit(1)


SRC = _resolve_src() if __name__ == "__main__" else ""


def _is_precinct(node_id: str, meta_text: str, content_text: str = "") -> bool:
    if node_id.startswith("asset:p6:"):
        return True
    if node_id.startswith("asset:100.64."):
        return True
    if "precinct6" in (meta_text or ""):
        return True
    if "precinct6" in (content_text or ""):
        return True
    return False


def main() -> None:
    src = _resolve_src()
    DST.parent.mkdir(parents=True, exist_ok=True)
    if DST.exists():
        DST.unlink()

    print(f"[copy] {src} -> {DST}")
    shutil.copy2(src, DST)

    con = sqlite3.connect(DST)
    cur = con.cursor()

    # ── 1. precinct6 노드 식별 (id + meta + content) ────────
    cur.execute("SELECT id, meta, content FROM nodes")
    drop_ids = [
        nid for (nid, m, c) in cur.fetchall()
        if _is_precinct(nid, m or "", c or "")
    ]

    # 추가: 엣지가 0 인 asset:172.* (precinct6 random subnet 잔재)
    cur.execute("""
        SELECT n.id FROM nodes n
        WHERE n.id LIKE 'asset:172.%'
          AND NOT EXISTS (SELECT 1 FROM edges e WHERE e.src=n.id OR e.dst=n.id)
    """)
    orphan_172 = [r[0] for r in cur.fetchall()]
    drop_ids.extend(orphan_172)
    print(f"[scan] precinct6-tagged nodes: {len(drop_ids) - len(orphan_172)}")
    print(f"[scan] orphan asset:172.* nodes: {len(orphan_172)}")
    print(f"[scan] total to drop: {len(drop_ids)}")

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

    # ── 3. precinct6 anchor 전부 제거 ────────────────────────
    # IoC dump + breach_record 중 precinct6 IP 를 본문/related_ids 에 가진 것
    cur.execute("DELETE FROM history_anchors WHERE kind='ioc'")
    cur.execute("""
        DELETE FROM history_anchors
        WHERE body LIKE '%100.64.%'
           OR related_ids LIKE '%100.64.%'
           OR body LIKE '%precinct6%'
    """)
    print("[scrub] removed precinct6 anchors (ioc + breach_record refs)")

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
