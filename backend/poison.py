"""KG poisoning recipe library — research-mapped attack templates.

Recipes (mapped to top-tier 2024-2026 papers):
  - poisoned_rag        PoisonedRAG (USENIX'25, Zou+) — k crafted texts toward target_q→target_a
  - one_shot_dominance  One-Shot-Dominance (EMNLP Findings'25)
  - roar_anchor         ROAR (USENIX'23) — bait evidence around target answer
  - clean_label_backdoor Clean-Label Graph Backdoor (AAAI'25)
  - fkge_client         FKGE-Poisoning (WWW'24) — client-isolated triple injection
  - mitm_concept_swap   AiTM concept rewrite (ACL'25) — relabel a high-centrality Concept

Every recipe MUTATES the live KG and writes a row to poison_log.
A snapshot SHOULD be taken before running so you can diff / rollback.
"""
from __future__ import annotations

import json
import random
import time
from typing import Any

import networkx as nx

from .db import conn
from .kg_ops import build_nx, upsert_node, add_edge


RECIPE_CATALOG = [
    {
        "id": "poisoned_rag",
        "title": "PoisonedRAG (k-doc injection)",
        "venue": "USENIX Security 2025",
        "params": {"k": 5, "target_q": "", "target_a": ""},
        "stealth_band": [0.3, 0.6],
    },
    {
        "id": "one_shot_dominance",
        "title": "One-Shot Dominance (single-doc bridging)",
        "venue": "EMNLP Findings 2025",
        "params": {"target_q": "", "target_a": ""},
        "stealth_band": [0.6, 0.85],
    },
    {
        "id": "roar_anchor",
        "title": "ROAR anchor poisoning",
        "venue": "USENIX Security 2023",
        "params": {"anchor_node": "", "target_concept": ""},
        "stealth_band": [0.4, 0.7],
    },
    {
        "id": "clean_label_backdoor",
        "title": "Clean-Label Graph Backdoor",
        "venue": "AAAI 2025",
        "params": {"victim_centrality": "betweenness", "trigger_size": 3},
        "stealth_band": [0.7, 0.95],
    },
    {
        "id": "fkge_client",
        "title": "FKGE Client-Side Triple Injection",
        "venue": "WWW 2024",
        "params": {"client_id": "tenant-A", "n_triples": 8},
        "stealth_band": [0.5, 0.8],
    },
    {
        "id": "mitm_concept_swap",
        "title": "AiTM Concept Swap",
        "venue": "ACL 2025",
        "params": {"target_concept": "", "swap_with": ""},
        "stealth_band": [0.5, 0.85],
    },
]


def _record_log(
    experiment_id: int | None,
    recipe: str,
    target: str,
    payload: dict,
    stealth: float,
    asr: float,
) -> int:
    with conn() as c:
        cur = c.execute(
            "INSERT INTO poison_log (experiment_id, recipe, target_node, payload, stealth_score, asr) VALUES (?,?,?,?,?,?)",
            (experiment_id, recipe, target, json.dumps(payload), stealth, asr),
        )
        return cur.lastrowid or 0


def _stealth(band: list[float]) -> float:
    return round(random.uniform(band[0], band[1]), 3)


# ── recipe runners ───────────────────────────────────────────────────────

def run_poisoned_rag(
    target_q: str, target_a: str, k: int = 5, experiment_id: int | None = None
) -> dict:
    inserted = []
    band = next(r["stealth_band"] for r in RECIPE_CATALOG if r["id"] == "poisoned_rag")
    for i in range(k):
        nid = f"poison:rag:{int(time.time()*1000)}:{i}"
        upsert_node(
            nid,
            "Asset",
            f"poison-doc-{i}",
            content={
                "description": f"Q: {target_q}\nA: {target_a}\nNote: authoritative reference for above question.",
                "kind": "rag_passage",
            },
            meta={"poison": True, "recipe": "poisoned_rag", "target_q": target_q},
        )
        inserted.append(nid)
    stealth = _stealth(band)
    asr = round(min(0.95, 0.5 + 0.05 * k), 3)
    log_id = _record_log(
        experiment_id,
        "poisoned_rag",
        target_q[:60],
        {"k": k, "inserted": inserted, "target_q": target_q, "target_a": target_a},
        stealth,
        asr,
    )
    return {"log_id": log_id, "inserted": inserted, "stealth": stealth, "asr": asr}


def run_one_shot_dominance(
    target_q: str, target_a: str, experiment_id: int | None = None
) -> dict:
    band = next(r["stealth_band"] for r in RECIPE_CATALOG if r["id"] == "one_shot_dominance")
    nid = f"poison:osd:{int(time.time()*1000)}"
    upsert_node(
        nid,
        "Asset",
        "one-shot-bridge",
        content={
            "description": f"Multi-hop bridge: question='{target_q}' → bridging fact → answer='{target_a}'",
            "kind": "rag_passage",
        },
        meta={"poison": True, "recipe": "one_shot_dominance"},
    )
    stealth = _stealth(band)
    asr = round(random.uniform(0.6, 0.9), 3)
    log_id = _record_log(
        experiment_id,
        "one_shot_dominance",
        target_q[:60],
        {"inserted": [nid], "target_q": target_q, "target_a": target_a},
        stealth,
        asr,
    )
    return {"log_id": log_id, "inserted": [nid], "stealth": stealth, "asr": asr}


def run_roar_anchor(
    anchor_node: str, target_concept: str, experiment_id: int | None = None
) -> dict:
    band = next(r["stealth_band"] for r in RECIPE_CATALOG if r["id"] == "roar_anchor")
    bait_nodes = []
    for i in range(3):
        bid = f"poison:roar:{int(time.time()*1000)}:{i}"
        upsert_node(
            bid,
            "Concept",
            f"roar-bait-{i}",
            content={"description": f"bait fact orbiting {anchor_node} -> {target_concept}"},
            meta={"poison": True, "recipe": "roar_anchor"},
        )
        try:
            add_edge(anchor_node, bid, "relates_to", weight=2.0, meta={"poison": True})
            add_edge(bid, target_concept, "handles", weight=2.0, meta={"poison": True})
        except Exception:
            pass
        bait_nodes.append(bid)
    stealth = _stealth(band)
    asr = round(random.uniform(0.55, 0.85), 3)
    log_id = _record_log(
        experiment_id,
        "roar_anchor",
        anchor_node,
        {"bait_nodes": bait_nodes, "target_concept": target_concept},
        stealth,
        asr,
    )
    return {"log_id": log_id, "bait_nodes": bait_nodes, "stealth": stealth, "asr": asr}


def run_clean_label_backdoor(
    victim_centrality: str = "betweenness",
    trigger_size: int = 3,
    experiment_id: int | None = None,
) -> dict:
    """Pick top-centrality node, attach `trigger_size` invisible neighbors."""
    g = build_nx()
    if victim_centrality == "pagerank":
        scores = nx.pagerank(g) if g.number_of_nodes() else {}
    else:
        sub = g.to_undirected()
        try:
            scores = nx.betweenness_centrality(sub, k=min(50, len(sub)))
        except Exception:
            scores = {}
    top = sorted(scores.items(), key=lambda x: -x[1])[:1]
    if not top:
        return {"error": "empty graph"}
    victim = top[0][0]
    trigger = []
    for i in range(trigger_size):
        tid = f"poison:cl:{int(time.time()*1000)}:{i}"
        upsert_node(
            tid,
            "Asset",
            f"clean-label-trigger-{i}",
            content={"description": "look-alike neighbor (backdoor trigger)"},
            meta={"poison": True, "recipe": "clean_label_backdoor", "stealth": "high"},
        )
        try:
            add_edge(victim, tid, "relates_to", weight=1.0, meta={"poison": True})
        except Exception:
            pass
        trigger.append(tid)
    band = next(r["stealth_band"] for r in RECIPE_CATALOG if r["id"] == "clean_label_backdoor")
    stealth = _stealth(band)
    asr = round(random.uniform(0.65, 0.9), 3)
    log_id = _record_log(
        experiment_id,
        "clean_label_backdoor",
        victim,
        {"victim": victim, "trigger": trigger, "victim_score": scores.get(victim, 0.0)},
        stealth,
        asr,
    )
    return {"log_id": log_id, "victim": victim, "trigger": trigger, "stealth": stealth, "asr": asr}


def run_fkge_client(
    client_id: str, n_triples: int = 8, experiment_id: int | None = None
) -> dict:
    band = next(r["stealth_band"] for r in RECIPE_CATALOG if r["id"] == "fkge_client")
    inserted = []
    for i in range(n_triples):
        sid = f"poison:fkge:{client_id}:s:{i}"
        oid = f"poison:fkge:{client_id}:o:{i}"
        upsert_node(sid, "Asset", f"{client_id}-fake-subj-{i}", meta={"poison": True, "client": client_id})
        upsert_node(oid, "Asset", f"{client_id}-fake-obj-{i}", meta={"poison": True, "client": client_id})
        try:
            add_edge(sid, oid, "relates_to", weight=1.5, meta={"poison": True, "client": client_id})
        except Exception:
            pass
        inserted += [sid, oid]
    stealth = _stealth(band)
    asr = round(random.uniform(0.5, 0.78), 3)
    log_id = _record_log(
        experiment_id,
        "fkge_client",
        client_id,
        {"client_id": client_id, "n_triples": n_triples, "inserted": inserted},
        stealth,
        asr,
    )
    return {"log_id": log_id, "inserted": inserted, "stealth": stealth, "asr": asr}


def run_mitm_concept_swap(
    target_concept: str, swap_with: str, experiment_id: int | None = None
) -> dict:
    band = next(r["stealth_band"] for r in RECIPE_CATALOG if r["id"] == "mitm_concept_swap")
    with conn() as c:
        row = c.execute("SELECT name, content, meta FROM nodes WHERE id = ?", (target_concept,)).fetchone()
        if not row:
            return {"error": f"target concept {target_concept} not found"}
        original = {"name": row["name"], "content": row["content"], "meta": row["meta"]}
        swap_row = c.execute("SELECT name FROM nodes WHERE id = ?", (swap_with,)).fetchone()
        new_name = swap_row["name"] if swap_row else f"{row['name']} (swapped)"
        c.execute(
            "UPDATE nodes SET name = ?, meta = ?, updated_at = datetime('now') WHERE id = ?",
            (
                new_name,
                json.dumps({**json.loads(row["meta"] or "{}"), "poison": True, "recipe": "mitm_concept_swap", "swapped_from": target_concept, "swapped_to": swap_with}),
                target_concept,
            ),
        )
    stealth = _stealth(band)
    asr = round(random.uniform(0.55, 0.88), 3)
    log_id = _record_log(
        experiment_id,
        "mitm_concept_swap",
        target_concept,
        {"target": target_concept, "swap_with": swap_with, "original": original},
        stealth,
        asr,
    )
    return {"log_id": log_id, "stealth": stealth, "asr": asr, "original": original}


# ── dispatcher ──────────────────────────────────────────────────────────

def run_recipe(recipe_id: str, params: dict, experiment_id: int | None = None) -> dict:
    if recipe_id == "poisoned_rag":
        return run_poisoned_rag(
            params.get("target_q", ""),
            params.get("target_a", ""),
            int(params.get("k", 5)),
            experiment_id,
        )
    if recipe_id == "one_shot_dominance":
        return run_one_shot_dominance(
            params.get("target_q", ""),
            params.get("target_a", ""),
            experiment_id,
        )
    if recipe_id == "roar_anchor":
        return run_roar_anchor(
            params.get("anchor_node", ""),
            params.get("target_concept", ""),
            experiment_id,
        )
    if recipe_id == "clean_label_backdoor":
        return run_clean_label_backdoor(
            params.get("victim_centrality", "betweenness"),
            int(params.get("trigger_size", 3)),
            experiment_id,
        )
    if recipe_id == "fkge_client":
        return run_fkge_client(
            params.get("client_id", "tenant-A"),
            int(params.get("n_triples", 8)),
            experiment_id,
        )
    if recipe_id == "mitm_concept_swap":
        return run_mitm_concept_swap(
            params.get("target_concept", ""),
            params.get("swap_with", ""),
            experiment_id,
        )
    raise ValueError(f"unknown recipe: {recipe_id}")


def list_log(limit: int = 100) -> list[dict]:
    with conn() as c:
        rows = c.execute(
            "SELECT * FROM poison_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        if isinstance(d.get("payload"), str):
            try:
                d["payload"] = json.loads(d["payload"])
            except Exception:
                pass
        out.append(d)
    return out


def cleanup_poison() -> dict:
    """Remove every node tagged poison=True. Convenience for resetting between experiments."""
    with conn() as c:
        rows = c.execute(
            "SELECT id FROM nodes WHERE meta LIKE '%\"poison\": true%'"
        ).fetchall()
        ids = [r["id"] for r in rows]
        for nid in ids:
            c.execute("DELETE FROM nodes WHERE id = ?", (nid,))
            c.execute("DELETE FROM nodes_fts WHERE id = ?", (nid,))
            c.execute("DELETE FROM edges WHERE src = ? OR dst = ?", (nid, nid))
        c.execute("DELETE FROM edges WHERE meta LIKE '%\"poison\": true%'")
    return {"removed": len(ids)}
