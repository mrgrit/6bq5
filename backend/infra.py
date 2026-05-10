"""6v6 docker-infra control + bastion agent reachability.

Runs `docker compose` against /home/opsclaw/6v6 (override with INFRA_DIR).
All commands are recorded into infra_events for audit.
"""
from __future__ import annotations

import json
import os
import subprocess
from typing import Any

from .db import conn


INFRA_DIR = os.environ.get("INFRA_DIR", "/home/opsclaw/6v6")


def _record(host: str, op: str, status: str, output: str) -> int:
    with conn() as c:
        cur = c.execute(
            "INSERT INTO infra_events (host, op, status, output) VALUES (?,?,?,?)",
            (host, op, status, output[-4000:]),
        )
        return cur.lastrowid or 0


def _run(cmd: list[str], timeout: int = 60) -> dict:
    try:
        p = subprocess.run(
            cmd, cwd=INFRA_DIR, capture_output=True, text=True, timeout=timeout
        )
        return {"rc": p.returncode, "stdout": p.stdout, "stderr": p.stderr}
    except subprocess.TimeoutExpired as e:
        return {"rc": -1, "stdout": "", "stderr": f"timeout: {e}"}
    except FileNotFoundError as e:
        return {"rc": -2, "stdout": "", "stderr": f"binary not found: {e}"}


def status() -> dict:
    out = _run(["docker", "compose", "ps", "--format", "json"], timeout=15)
    services: list[dict] = []
    for line in (out.get("stdout") or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            services.append(json.loads(line))
        except Exception:
            pass
    _record("compose", "ps", "ok" if out["rc"] == 0 else "err", out.get("stderr", ""))
    return {
        "infra_dir": INFRA_DIR,
        "rc": out["rc"],
        "services": services,
        "stderr": out.get("stderr", ""),
    }


def up(services: list[str] | None = None) -> dict:
    cmd = ["docker", "compose", "up", "-d"]
    if services:
        cmd += services
    out = _run(cmd, timeout=180)
    _record(",".join(services or []) or "all", "up", "ok" if out["rc"] == 0 else "err", out.get("stderr", ""))
    return out


def down() -> dict:
    out = _run(["docker", "compose", "down"], timeout=120)
    _record("all", "down", "ok" if out["rc"] == 0 else "err", out.get("stderr", ""))
    return out


def restart(service: str) -> dict:
    out = _run(["docker", "compose", "restart", service], timeout=60)
    _record(service, "restart", "ok" if out["rc"] == 0 else "err", out.get("stderr", ""))
    return out


def logs(service: str, tail: int = 200) -> dict:
    out = _run(["docker", "compose", "logs", "--tail", str(tail), service], timeout=30)
    return out


def exec_in(service: str, command: str, timeout: int = 30) -> dict:
    cmd = ["docker", "compose", "exec", "-T", service, "sh", "-c", command]
    out = _run(cmd, timeout=timeout)
    _record(service, "exec", "ok" if out["rc"] == 0 else "err", out.get("stderr", "") + out.get("stdout", ""))
    return out


def history(limit: int = 100) -> list[dict]:
    with conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM infra_events ORDER BY id DESC LIMIT ?", (limit,)
        )]
