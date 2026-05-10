"""KG defense layer — rule-based + structural anomaly + certified-radius badges.

Mapped to:
  - KnowGraph (CCS'24)        FOL rule engine (string-pattern light version)
  - DShield   (NDSS'25)       discrepancy / centrality-spike detection
  - AGNNCert  (USENIX'25)     certified perturbation radius (placeholder model)
  - DPSBA     (NeurIPS'25)    distribution-distance stealth metric
"""
from __future__ import annotations

import json
import math
import statistics
from typing import Any

import networkx as nx

from .db import conn
from .kg_ops import build_nx


# ── 규칙 관리 ─────────────────────────────────────────────────────────

def list_rules() -> list[dict]:
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM defense_rules ORDER BY id")]


def upsert_rule(name: str, kind: str, body: str, enabled: int = 1, rule_id: int | None = None) -> dict:
    with conn() as c:
        if rule_id:
            c.execute(
                "UPDATE defense_rules SET name=?, kind=?, body=?, enabled=? WHERE id=?",
                (name, kind, body, enabled, rule_id),
            )
        else:
            cur = c.execute(
                "INSERT INTO defense_rules (name, kind, body, enabled) VALUES (?,?,?,?)",
                (name, kind, body, enabled),
            )
            rule_id = cur.lastrowid
    return {"id": rule_id, "name": name, "kind": kind}


def delete_rule(rule_id: int) -> int:
    with conn() as c:
        return c.execute("DELETE FROM defense_rules WHERE id = ?", (rule_id,)).rowcount


def list_alerts(limit: int = 100) -> list[dict]:
    with conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM defense_alerts ORDER BY id DESC LIMIT ?", (limit,)
        )]


_PENDING_ALERTS: list[tuple] = []


def _emit(rule_id: int | None, severity: str, target: str, message: str, experiment_id: int | None = None) -> int:
    """Buffer alert; flushed by `_flush_alerts()` at end of a scan call.

    Avoids re-opening sqlite during nested reads (caused 'database is locked').
    """
    _PENDING_ALERTS.append((rule_id, experiment_id, severity, target, message))
    return 0


def _flush_alerts() -> int:
    if not _PENDING_ALERTS:
        return 0
    pending = list(_PENDING_ALERTS)
    _PENDING_ALERTS.clear()
    with conn() as c:
        c.executemany(
            "INSERT INTO defense_alerts (rule_id, experiment_id, severity, target, message) VALUES (?,?,?,?,?)",
            pending,
        )
    return len(pending)


# ── 검출기 ────────────────────────────────────────────────────────────

def scan_poison_markers(experiment_id: int | None = None) -> dict:
    """Trivial: nodes with meta.poison=true. Kept as smoke test."""
    found = []
    with conn() as c:
        rows = c.execute(
            "SELECT id, name FROM nodes WHERE meta LIKE '%\"poison\": true%'"
        ).fetchall()
    for r in rows:
        found.append({"id": r["id"], "name": r["name"]})
        _emit(None, "low", r["id"], "node carries poison marker", experiment_id)
    return {"hits": found}


def scan_orphan_mitre(experiment_id: int | None = None) -> dict:
    """FOL: every Concept of mitre:* must have at least one inbound `handles` edge."""
    g = build_nx()
    orphans = []
    for n, attrs in g.nodes(data=True):
        if str(n).startswith("mitre:") and attrs.get("type") == "Concept":
            in_edges = [e for e in g.in_edges(n, data=True) if e[2].get("type") == "handles"]
            if not in_edges:
                orphans.append(n)
    for n in orphans:
        _emit(None, "medium", n, "mitre concept lacks any handles() inbound", experiment_id)
    return {"orphans": orphans}


def scan_centrality_spike(z_threshold: float = 3.0, experiment_id: int | None = None) -> dict:
    """DShield-style: betweenness z-score above threshold for poisoned nodes."""
    g = build_nx()
    if g.number_of_nodes() < 5:
        return {"hits": [], "note": "graph too small"}
    try:
        bw = nx.betweenness_centrality(g.to_undirected(), k=min(50, g.number_of_nodes()))
    except Exception:
        return {"hits": [], "note": "betweenness failed"}
    vals = list(bw.values())
    mean = statistics.mean(vals)
    sd = statistics.pstdev(vals) or 1e-9
    hits = []
    for n, v in bw.items():
        z = (v - mean) / sd
        if z >= z_threshold:
            hits.append({"id": n, "z": round(z, 3), "betweenness": round(v, 5)})
            _emit(None, "high", n, f"betweenness z-score {z:.2f} ≥ {z_threshold}", experiment_id)
    hits.sort(key=lambda x: -x["z"])
    return {"hits": hits[:30], "mean": mean, "sd": sd}


def scan_unsigned_anchor(experiment_id: int | None = None) -> dict:
    """anchor_provenance rule: anchors without `signed_by` in body are flagged."""
    found = []
    with conn() as c:
        rows = c.execute(
            "SELECT id, label, body FROM history_anchors WHERE body NOT LIKE '%signed_by%' LIMIT 20"
        ).fetchall()
    for r in rows:
        found.append({"id": r["id"], "label": r["label"]})
        _emit(None, "low", str(r["id"]), "anchor has no provenance signature", experiment_id)
    return {"unsigned": len(found), "sample": found}


# ── 인증 robustness 배지 (placeholder model) ─────────────────────────

def certified_radius(node_id: str) -> dict:
    """AGNNCert-inspired: smaller-degree → smaller certified radius.

    This is a teaching placeholder; not a real certification.
    Real impl would call a smoothed classifier with sample budget.
    """
    g = build_nx()
    if node_id not in g:
        return {"error": "not in graph"}
    deg = g.degree(node_id)
    radius = max(0, math.floor(math.log2(deg + 1) - 1))
    return {
        "node": node_id,
        "degree": deg,
        "certified_radius": radius,
        "interpretation": "edge-perturbation budget under which prediction provably stable",
    }


# ── 분포 스텔스 메트릭 (DPSBA inspired) ──────────────────────────────

def distribution_distance(snap_id: int) -> dict:
    """KL of degree-distribution between snapshot and live. Lower → stealthier poison."""
    g_live = build_nx()
    with conn() as c:
        snap_edges = c.execute(
            "SELECT src, dst FROM kg_snapshot_edges WHERE snapshot_id = ?",
            (snap_id,),
        ).fetchall()
    g_snap = nx.DiGraph()
    g_snap.add_edges_from([(r["src"], r["dst"]) for r in snap_edges])

    def deg_dist(g: nx.DiGraph) -> dict[int, float]:
        from collections import Counter
        c = Counter(d for _, d in g.degree())
        total = sum(c.values()) or 1
        return {k: v / total for k, v in c.items()}

    a = deg_dist(g_live)
    b = deg_dist(g_snap)
    keys = set(a) | set(b)
    eps = 1e-9
    kl = 0.0
    for k in keys:
        p = a.get(k, eps)
        q = b.get(k, eps)
        kl += p * math.log(p / q)
    return {
        "snapshot_id": snap_id,
        "kl_divergence": round(kl, 5),
        "interpretation": "KL(live ‖ snapshot) of degree distributions; near 0 means stealthy poison",
    }


def run_full_scan(experiment_id: int | None = None) -> dict:
    """Run every detector once — used by the Defense Studio “Run all” button."""
    out = {
        "poison_markers": scan_poison_markers(experiment_id),
        "orphan_mitre": scan_orphan_mitre(experiment_id),
        "centrality_spike": scan_centrality_spike(experiment_id=experiment_id),
        "unsigned_anchor": scan_unsigned_anchor(experiment_id),
    }
    out["alerts_emitted"] = _flush_alerts()
    return out
