"""Sync 6v6 docker containers → KG Asset nodes + network edges.

Strategy:
  1. `docker inspect` every running container whose name starts with 6v6-
  2. Upsert each as an Asset node (id = asset:6v6:<container>) with:
       kind = container_6v6
       container = name
       hostname / image / status / role
       networks = {netname: ip, ...}
       ports    = [...]
  3. For each docker network, create/refresh a Concept node
       id = net:6v6:<netname>
       kind = network
       cidr = <inferred>
  4. Edges:
       Asset --connects_to--> Concept(net)        (per network membership)
       Concept(net) --connects_to--> Asset        (reverse for graph view)
       Asset --hosts--> Asset                     (compose `depends_on`,
                                                   if container metadata exposes it)
  5. Stale 6v6 nodes (missing in current docker) get marked meta.stale=true
     instead of deleted — diff-friendly.

Returns a summary dict that's also exposed via /api/infra/sync.
"""
from __future__ import annotations

import json
import subprocess
from typing import Any

from .db import conn
from .infra import INFRA_DIR
from .kg_ops import upsert_node, add_edge


def _docker_json(cmd: list[str]) -> Any:
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or "docker call failed")
    out = p.stdout.strip()
    if not out:
        return []
    if out.startswith("["):
        return json.loads(out)
    # JSON-stream (one obj per line)
    rows = []
    for line in out.splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _list_6v6_containers() -> list[dict]:
    rows = _docker_json(["docker", "ps", "-a", "--format", "{{json .}}"])
    return [r for r in rows if str(r.get("Names", "")).startswith("6v6-")]


def _inspect(name: str) -> dict | None:
    try:
        data = _docker_json(["docker", "inspect", name])
        return data[0] if data else None
    except Exception:
        return None


def _list_networks() -> list[dict]:
    return _docker_json(["docker", "network", "ls", "--format", "{{json .}}"])


def _inspect_network(name: str) -> dict | None:
    try:
        data = _docker_json(["docker", "network", "inspect", name])
        return data[0] if data else None
    except Exception:
        return None


def _container_summary(insp: dict, ps_row: dict) -> dict:
    name = insp["Name"].lstrip("/")
    role = name.removeprefix("6v6-")
    state = insp.get("State", {})
    nets = (insp.get("NetworkSettings", {}) or {}).get("Networks", {}) or {}
    network_map = {nname: ndata.get("IPAddress", "") for nname, ndata in nets.items()}
    primary_ip = next(iter(network_map.values()), "")
    image = insp.get("Config", {}).get("Image") or insp.get("Image", "")
    hostname = insp.get("Config", {}).get("Hostname") or role
    ports = list((insp.get("NetworkSettings", {}) or {}).get("Ports", {}).keys())
    labels = insp.get("Config", {}).get("Labels", {}) or {}
    compose_svc = labels.get("com.docker.compose.service") or role
    return {
        "id": f"asset:6v6:{role}",
        "name": role,
        "container": name,
        "image": image,
        "hostname": hostname,
        "role": compose_svc,
        "ip": primary_ip,
        "networks": network_map,
        "ports": ports,
        "state": state.get("Status", "unknown"),
        "running": bool(state.get("Running")),
        "started_at": state.get("StartedAt"),
    }


def _network_id(name: str) -> str:
    short = name.removeprefix("6v6_").removeprefix("6v6-")
    return f"net:6v6:{short}"


def sync() -> dict:
    if not INFRA_DIR:
        return {"ok": False, "error": "INFRA_DIR not set / 6v6 not found"}

    try:
        ps_rows = _list_6v6_containers()
    except Exception as e:
        return {"ok": False, "error": f"docker ps failed: {e}"}

    upserted_nodes: list[str] = []
    edges_added = 0
    network_nodes: dict[str, set[str]] = {}  # net_id → {asset_ids}

    for r in ps_rows:
        insp = _inspect(r["Names"])
        if not insp:
            continue
        s = _container_summary(insp, r)
        upsert_node(
            s["id"],
            "Asset",
            s["name"],
            content={
                "description": f"6v6 docker container '{s['container']}' (role={s['role']}, image={s['image']})",
                "ports": s["ports"],
            },
            meta={
                "kind": "container_6v6",
                "container": s["container"],
                "image": s["image"],
                "hostname": s["hostname"],
                "role": s["role"],
                "ip": s["ip"],
                "networks": s["networks"],
                "state": s["state"],
                "running": s["running"],
                "started_at": s["started_at"],
                "synced_from": "6v6",
            },
        )
        upserted_nodes.append(s["id"])
        for nname in s["networks"]:
            net_id = _network_id(nname)
            network_nodes.setdefault(net_id, set()).add(s["id"])

    # Network nodes
    for net_id, members in network_nodes.items():
        short = net_id.removeprefix("net:6v6:")
        cidr = ""
        try:
            ninsp = _inspect_network(short) or _inspect_network(f"6v6_{short}") or _inspect_network(f"6v6-{short}")
            if ninsp:
                ipam = (ninsp.get("IPAM", {}) or {}).get("Config", []) or []
                if ipam:
                    cidr = ipam[0].get("Subnet", "")
        except Exception:
            pass
        upsert_node(
            net_id,
            "Concept",
            f"6v6 net: {short}",
            content={"description": f"docker network {short} (cidr={cidr or 'unknown'})"},
            meta={"kind": "network", "network": short, "cidr": cidr, "synced_from": "6v6"},
        )

    # Edges (Asset ↔ Concept(net))
    for net_id, members in network_nodes.items():
        for aid in members:
            try:
                add_edge(aid, net_id, "connects_to", weight=1.0, meta={"synced_from": "6v6"})
                edges_added += 1
            except Exception:
                pass

    # Mark stale
    stale = []
    with conn() as c:
        rows = c.execute(
            "SELECT id FROM nodes WHERE meta LIKE '%\"synced_from\": \"6v6\"%' AND meta LIKE '%container_6v6%'"
        ).fetchall()
        for r in rows:
            if r["id"] not in upserted_nodes:
                stale.append(r["id"])
        for sid in stale:
            row = c.execute("SELECT meta FROM nodes WHERE id = ?", (sid,)).fetchone()
            if row:
                m = json.loads(row["meta"] or "{}")
                m["stale"] = True
                c.execute(
                    "UPDATE nodes SET meta = ?, updated_at = datetime('now') WHERE id = ?",
                    (json.dumps(m, ensure_ascii=False), sid),
                )

    return {
        "ok": True,
        "containers_synced": len(upserted_nodes),
        "networks_synced": len(network_nodes),
        "edges_added": edges_added,
        "stale_marked": len(stale),
        "asset_ids": upserted_nodes,
    }
