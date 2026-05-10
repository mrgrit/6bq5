"""6bq5 — KG Manipulation Risk · Targeted Pentest · Defense Platform.

Run:
    uvicorn backend.main:app --host 0.0.0.0 --port 8500
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import defense, infra, kg_ops, llm, poison, sync_infra
from .db import conn


HERE = Path(__file__).resolve().parent
FRONTEND_DIST = (HERE.parent / "frontend" / "dist").resolve()


app = FastAPI(title="6bq5 — KG Risk Platform", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 헬스 ─────────────────────────────────────────────────────────────

@app.get("/api/health")
def api_health() -> dict:
    return {"ok": True, "llm": llm.health(), "infra_dir": infra.INFRA_DIR}


# ── KG ─────────────────────────────────────────────────────────────

@app.get("/api/kg/stats")
def kg_stats() -> dict:
    return kg_ops.stats()


@app.get("/api/kg/nodes")
def kg_nodes(type: str | None = None, q: str | None = None, limit: int = 100, offset: int = 0):
    return kg_ops.list_nodes(type, q, limit, offset)


@app.get("/api/kg/node/{node_id}")
def kg_node(node_id: str):
    n = kg_ops.get_node(node_id)
    if not n:
        raise HTTPException(404, "node not found")
    return n


class NodeIn(BaseModel):
    id: str
    type: str
    name: str
    content: dict | None = None
    meta: dict | None = None


@app.post("/api/kg/node")
def kg_create_node(node: NodeIn):
    return kg_ops.upsert_node(node.id, node.type, node.name, node.content, node.meta)


@app.delete("/api/kg/node/{node_id}")
def kg_delete_node(node_id: str):
    n = kg_ops.delete_node(node_id)
    return {"deleted": n}


@app.get("/api/kg/edges")
def kg_edges(limit: int = 5000):
    return kg_ops.list_edges(limit)


class EdgeIn(BaseModel):
    src: str
    dst: str
    type: str
    weight: float = 1.0
    meta: dict | None = None


@app.post("/api/kg/edge")
def kg_create_edge(edge: EdgeIn):
    eid = kg_ops.add_edge(edge.src, edge.dst, edge.type, edge.weight, edge.meta)
    return {"id": eid}


@app.delete("/api/kg/edge/{edge_id}")
def kg_delete_edge(edge_id: int):
    return {"deleted": kg_ops.delete_edge(edge_id)}


@app.get("/api/kg/search")
def kg_search(q: str, limit: int = 30):
    return kg_ops.search_fts(q, limit)


@app.get("/api/kg/importance")
def kg_importance(top_k: int = 50):
    return kg_ops.importance_table(top_k)


@app.get("/api/kg/subgraph/{node_id}")
def kg_subgraph(node_id: str, hops: int = 1):
    return kg_ops.neighbors_subgraph(node_id, hops)


# ── 스냅샷 ──────────────────────────────────────────────────────────

class SnapshotIn(BaseModel):
    label: str
    description: str = ""


@app.post("/api/kg/snapshot")
def snap_create(s: SnapshotIn):
    return kg_ops.take_snapshot(s.label, s.description)


@app.get("/api/kg/snapshot")
def snap_list():
    return kg_ops.list_snapshots()


@app.get("/api/kg/snapshot/{snap_id}/diff")
def snap_diff(snap_id: int):
    return kg_ops.diff_snapshot_against_live(snap_id)


@app.post("/api/kg/snapshot/{snap_id}/restore")
def snap_restore(snap_id: int):
    return kg_ops.restore_snapshot(snap_id)


# ── 포이즈닝 ───────────────────────────────────────────────────────

@app.get("/api/poison/recipes")
def poison_recipes():
    return poison.RECIPE_CATALOG


class PoisonRunIn(BaseModel):
    recipe: str
    params: dict = {}
    experiment_id: int | None = None


@app.post("/api/poison/run")
def poison_run(p: PoisonRunIn):
    try:
        return poison.run_recipe(p.recipe, p.params, p.experiment_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/poison/log")
def poison_log(limit: int = 100):
    return poison.list_log(limit)


@app.post("/api/poison/cleanup")
def poison_cleanup():
    return poison.cleanup_poison()


# ── 방어 ──────────────────────────────────────────────────────────

@app.get("/api/defense/rules")
def def_rules():
    return defense.list_rules()


class RuleIn(BaseModel):
    name: str
    kind: str
    body: str
    enabled: int = 1
    id: int | None = None


@app.post("/api/defense/rules")
def def_rules_upsert(r: RuleIn):
    return defense.upsert_rule(r.name, r.kind, r.body, r.enabled, r.id)


@app.delete("/api/defense/rules/{rid}")
def def_rules_delete(rid: int):
    return {"deleted": defense.delete_rule(rid)}


@app.get("/api/defense/alerts")
def def_alerts(limit: int = 100):
    return defense.list_alerts(limit)


@app.post("/api/defense/scan/full")
def def_scan_full(experiment_id: int | None = None):
    return defense.run_full_scan(experiment_id)


@app.post("/api/defense/scan/centrality")
def def_scan_centrality(z: float = 3.0, experiment_id: int | None = None):
    return defense.scan_centrality_spike(z, experiment_id)


@app.get("/api/defense/cert/{node_id}")
def def_cert(node_id: str):
    return defense.certified_radius(node_id)


@app.get("/api/defense/distribution/{snap_id}")
def def_distribution(snap_id: int):
    return defense.distribution_distance(snap_id)


# ── Pentest ────────────────────────────────────────────────────────

class PentestIn(BaseModel):
    target_node: str
    recipe_hint: str = "exploit retrieved poisoned RAG context to gain initial access"
    use_kg_context: bool = True
    experiment_id: int | None = None


@app.post("/api/pentest/craft")
def pentest_craft(p: PentestIn):
    target = kg_ops.get_node(p.target_node)
    if not target:
        raise HTTPException(404, f"target {p.target_node} not in KG")
    ctx = ""
    if p.use_kg_context:
        sub = kg_ops.neighbors_subgraph(p.target_node, hops=1)
        ctx = json.dumps(sub, ensure_ascii=False)[:4000]
    out = llm.craft_attack(target, p.recipe_hint, ctx)
    with conn() as c:
        cur = c.execute(
            "INSERT INTO experiment_runs (experiment_id, phase, payload, result) VALUES (?,?,?,?)",
            (p.experiment_id, "attack", json.dumps(p.model_dump(), ensure_ascii=False), json.dumps(out, ensure_ascii=False)),
        )
        run_id = cur.lastrowid
    return {"run_id": run_id, **out}


class PentestExecIn(BaseModel):
    service: str = "attacker"
    command: str
    experiment_id: int | None = None


@app.post("/api/pentest/exec")
def pentest_exec(p: PentestExecIn):
    """Execute a chosen step from the LLM plan inside the 6v6 attacker container."""
    out = infra.exec_in(p.service, p.command, timeout=60)
    with conn() as c:
        c.execute(
            "INSERT INTO experiment_runs (experiment_id, phase, payload, result) VALUES (?,?,?,?)",
            (p.experiment_id, "attack_exec", json.dumps(p.model_dump()), json.dumps(out)),
        )
    return out


# ── 실험 / 노트 ────────────────────────────────────────────────────

class ExperimentIn(BaseModel):
    kind: str
    title: str
    description: str = ""
    params: dict = {}


@app.post("/api/experiments")
def exp_create(e: ExperimentIn):
    with conn() as c:
        cur = c.execute(
            "INSERT INTO experiments (kind, title, description, params, status) VALUES (?,?,?,?, 'planned')",
            (e.kind, e.title, e.description, json.dumps(e.params, ensure_ascii=False)),
        )
        eid = cur.lastrowid
    return {"id": eid, **e.model_dump()}


@app.get("/api/experiments")
def exp_list(status: str | None = None):
    sql = "SELECT * FROM experiments"
    args = []
    if status:
        sql += " WHERE status = ?"
        args.append(status)
    sql += " ORDER BY id DESC"
    with conn() as c:
        rows = c.execute(sql, args).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/experiments/{eid}")
def exp_get(eid: int):
    with conn() as c:
        row = c.execute("SELECT * FROM experiments WHERE id = ?", (eid,)).fetchone()
        if not row:
            raise HTTPException(404, "experiment not found")
        runs = [dict(r) for r in c.execute(
            "SELECT * FROM experiment_runs WHERE experiment_id = ? ORDER BY id", (eid,)
        )]
        notes = [dict(r) for r in c.execute(
            "SELECT * FROM notes WHERE experiment_id = ? ORDER BY id DESC", (eid,)
        )]
    return {"experiment": dict(row), "runs": runs, "notes": notes}


class StatusIn(BaseModel):
    status: str


@app.patch("/api/experiments/{eid}/status")
def exp_status(eid: int, s: StatusIn):
    field = "started_at" if s.status == "running" else "finished_at" if s.status in ("done", "failed", "cancelled") else None
    with conn() as c:
        if field:
            c.execute(
                f"UPDATE experiments SET status = ?, {field} = datetime('now') WHERE id = ?",
                (s.status, eid),
            )
        else:
            c.execute("UPDATE experiments SET status = ? WHERE id = ?", (s.status, eid))
    return {"ok": True}


class NoteIn(BaseModel):
    body: str
    tag: str | None = None
    experiment_id: int | None = None


@app.post("/api/notes")
def note_create(n: NoteIn):
    with conn() as c:
        cur = c.execute(
            "INSERT INTO notes (body, tag, experiment_id) VALUES (?,?,?)",
            (n.body, n.tag, n.experiment_id),
        )
        nid = cur.lastrowid
    return {"id": nid}


@app.get("/api/notes")
def note_list(experiment_id: int | None = None, tag: str | None = None, limit: int = 200):
    sql = "SELECT * FROM notes WHERE 1=1"
    args = []
    if experiment_id is not None:
        sql += " AND experiment_id = ?"
        args.append(experiment_id)
    if tag:
        sql += " AND tag = ?"
        args.append(tag)
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    with conn() as c:
        return [dict(r) for r in c.execute(sql, args)]


# ── RAG trace + memory trace ──────────────────────────────────────

class RagTraceIn(BaseModel):
    query: str
    retrieved_ids: list[str] = []
    poisoned: bool = False
    experiment_id: int | None = None


@app.post("/api/rag/trace")
def rag_trace_record(t: RagTraceIn):
    ctx_chunks = []
    for nid in t.retrieved_ids:
        n = kg_ops.get_node(nid)
        if n:
            desc = (n.get("content", {}) or {}).get("description") or n.get("name")
            ctx_chunks.append(f"[{nid}] {desc}")
    answer = llm.complete(
        f"Answer using ONLY the context.\n\n# context\n" + "\n".join(ctx_chunks) + f"\n\n# question\n{t.query}"
    )
    with conn() as c:
        cur = c.execute(
            "INSERT INTO rag_traces (experiment_id, query, retrieved, generation, poisoned) VALUES (?,?,?,?,?)",
            (t.experiment_id, t.query, json.dumps(t.retrieved_ids), answer, 1 if t.poisoned else 0),
        )
        tid = cur.lastrowid
    return {"id": tid, "answer": answer, "context_chunks": ctx_chunks}


@app.get("/api/rag/trace")
def rag_trace_list(limit: int = 100, experiment_id: int | None = None):
    sql = "SELECT * FROM rag_traces"
    args = []
    if experiment_id is not None:
        sql += " WHERE experiment_id = ?"
        args.append(experiment_id)
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    with conn() as c:
        rows = c.execute(sql, args).fetchall()
    return [dict(r) for r in rows]


class MemTraceIn(BaseModel):
    agent: str
    op: str   # 'write' | 'read' | 'rollback'
    node_id: str | None = None
    content: str | None = None
    experiment_id: int | None = None


@app.post("/api/memory/trace")
def memory_trace_record(t: MemTraceIn):
    with conn() as c:
        cur = c.execute(
            "INSERT INTO memory_trace (experiment_id, agent, op, node_id, content) VALUES (?,?,?,?,?)",
            (t.experiment_id, t.agent, t.op, t.node_id, t.content),
        )
        return {"id": cur.lastrowid}


@app.get("/api/memory/trace")
def memory_trace_list(limit: int = 200, experiment_id: int | None = None):
    sql = "SELECT * FROM memory_trace"
    args = []
    if experiment_id is not None:
        sql += " WHERE experiment_id = ?"
        args.append(experiment_id)
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    with conn() as c:
        return [dict(r) for r in c.execute(sql, args)]


# ── 인프라 / 6v6 ───────────────────────────────────────────────────

@app.get("/api/infra/status")
def infra_status():
    return infra.status()


class InfraUpIn(BaseModel):
    services: list[str] | None = None


@app.post("/api/infra/up")
def infra_up(p: InfraUpIn):
    return infra.up(p.services)


@app.post("/api/infra/down")
def infra_down():
    return infra.down()


@app.post("/api/infra/restart/{service}")
def infra_restart(service: str):
    return infra.restart(service)


@app.get("/api/infra/logs/{service}")
def infra_logs(service: str, tail: int = 200):
    return infra.logs(service, tail)


class InfraExecIn(BaseModel):
    command: str


@app.post("/api/infra/exec/{service}")
def infra_exec(service: str, p: InfraExecIn):
    return infra.exec_in(service, p.command, timeout=60)


@app.get("/api/infra/history")
def infra_history(limit: int = 100):
    return infra.history(limit)


@app.post("/api/infra/sync")
def infra_sync():
    """Introspect 6v6 docker → upsert Asset nodes + network edges into KG."""
    return sync_infra.sync()


# ── Bastion proxy ─────────────────────────────────────────────────

class BastionIn(BaseModel):
    message: str


@app.post("/api/bastion/chat")
def bastion_chat(p: BastionIn):
    return llm.bastion_chat(p.message)


# ── Anchor browse (history layer) ─────────────────────────────────

@app.get("/api/anchors")
def anchors(kind: str | None = None, limit: int = 100, q: str | None = None):
    sql = "SELECT id, kind, label, body, created_at FROM history_anchors WHERE 1=1"
    args = []
    if kind:
        sql += " AND kind = ?"
        args.append(kind)
    if q:
        sql += " AND (label LIKE ? OR body LIKE ?)"
        args += [f"%{q}%", f"%{q}%"]
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    with conn() as c:
        return [dict(r) for r in c.execute(sql, args)]


# ── 정적 파일 (UI) ────────────────────────────────────────────────

if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/")
    def root():
        return FileResponse(FRONTEND_DIST / "index.html")

    @app.get("/{path:path}")
    def spa(path: str):
        target = FRONTEND_DIST / path
        if target.is_file():
            return FileResponse(target)
        return FileResponse(FRONTEND_DIST / "index.html")
else:
    @app.get("/")
    def root_dev():
        return JSONResponse(
            {
                "ok": True,
                "msg": "6bq5 backend up. Build the frontend (npm run build) to serve UI here, or run the Vite dev server.",
                "docs": "/docs",
            }
        )
