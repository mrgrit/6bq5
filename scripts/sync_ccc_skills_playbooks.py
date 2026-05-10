"""Sync CCC SKILLS dict + playbook YAMLs into 6bq5 KG.

Why: CCC seeded only 18 of 33 SKILLS into the KG (R3 동적 확장이 코드만 반영,
KG 미반영 — CCC inflight P10). 6bq5 입장에선 카탈로그가 빈약하면 LLM craft 가
받는 KG context 가 약해진다. 이 스크립트가 정직하게 둘을 KG 로 끌어온다.

Source:
  - SKILLS dict at packages/bastion/skills.py  (CCC 또는 ~/bastion 둘 다 시도)
  - playbooks yaml dir at contents/playbooks/  (동일)

Target: 6bq5 data/kg.db

Marks every imported node with meta.synced_from = 'ccc-code' so they can be
distinguished from manually-edited or poisoned nodes.

Usage:
  python3 scripts/sync_ccc_skills_playbooks.py
  CCC_HOME=/path/to/ccc python3 scripts/sync_ccc_skills_playbooks.py
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
DST_DB = (HERE.parent / "data" / "kg.db").resolve()


def _candidate_homes() -> list[Path]:
    if os.environ.get("CCC_HOME"):
        return [Path(os.environ["CCC_HOME"])]
    return [
        Path.home() / "ccc",
        Path("/home/opsclaw/ccc"),
        Path("/opt/ccc"),
        Path.home() / "bastion",
        Path("/home/opsclaw/bastion"),
    ]


def _find_skills_module() -> Path | None:
    for h in _candidate_homes():
        for sub in ("packages/bastion/skills.py",):
            p = h / sub
            if p.is_file():
                return p
    return None


def _find_playbooks_dir() -> Path | None:
    for h in _candidate_homes():
        for sub in ("contents/playbooks", "playbooks"):
            p = h / sub
            if p.is_dir() and any(p.glob("*.yaml")):
                return p
    return None


def _load_skills(skills_py: Path) -> dict:
    """Import the module without triggering the .env required-vars check."""
    # bastion __init__.py requires several env vars — set placeholders so import works
    placeholders = {
        "LLM_BASE_URL": "http://localhost:11434",
        "LLM_MODEL": "gemma3:4b",
        "LLM_MANAGER_MODEL": "gemma3:4b",
        "LLM_SUBAGENT_MODEL": "gemma3:4b",
        "LLM_HEAVY_MODEL": "gemma3:4b",
        "LLM_FAST_MODEL": "gemma3:4b",
        "OLLAMA_KEEP_ALIVE": "5m",
        "BASTION_API_KEY": "ccc-api-key-2026",
        "API_KEY": "ccc-api-key-2026",
    }
    for k, v in placeholders.items():
        os.environ.setdefault(k, v)
    repo_root = skills_py.parent.parent.parent  # …/<repo>/packages/bastion/skills.py → <repo>
    sys.path.insert(0, str(repo_root))
    from packages.bastion.skills import SKILLS, SKILL_CATEGORIES  # type: ignore
    return {"skills": SKILLS, "categories": SKILL_CATEGORIES}


def _load_playbook_yaml(p: Path) -> dict:
    # Avoid hard yaml dep — use a tiny parser via json fallback if pyyaml absent
    try:
        import yaml  # type: ignore
        return yaml.safe_load(p.read_text())
    except ImportError:
        # naive: most CCC playbooks have a JSON-compatible header. Best effort.
        text = p.read_text()
        # Try to find a name + description with simple grep
        return {"name": p.stem, "raw": text[:1500]}


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DST_DB)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode = WAL")
    c.execute("PRAGMA busy_timeout = 5000")
    return c


def _upsert(c: sqlite3.Connection, nid: str, ntype: str, name: str, content: dict, meta: dict):
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
        (nid, ntype, name, json.dumps(content, ensure_ascii=False), json.dumps(meta, ensure_ascii=False)),
    )
    c.execute("DELETE FROM nodes_fts WHERE id = ?", (nid,))
    fts = name + " " + (content.get("description") or "") + " " + (content.get("category") or "")
    c.execute(
        "INSERT INTO nodes_fts (id, type, name, content_text) VALUES (?,?,?,?)",
        (nid, ntype, name, fts),
    )


def main() -> None:
    if not DST_DB.exists():
        print(f"[FATAL] {DST_DB} not found. run scripts/import_kg.py first.", file=sys.stderr)
        sys.exit(1)

    skills_py = _find_skills_module()
    pb_dir = _find_playbooks_dir()

    if not skills_py and not pb_dir:
        print("[FATAL] Neither CCC SKILLS nor playbooks dir found.", file=sys.stderr)
        print("Hint: set CCC_HOME=/path/to/ccc", file=sys.stderr)
        sys.exit(2)

    c = _conn()
    skills_added = 0
    pbs_added = 0

    # ── Skills ──────────────────────────────────────────────
    if skills_py:
        print(f"[skills] loading from {skills_py}")
        try:
            data = _load_skills(skills_py)
        except Exception as e:
            print(f"[WARN] could not import SKILLS: {e}", file=sys.stderr)
            data = None
        if data:
            sk = data["skills"]
            cat_lookup = {}
            for cat_name, payload in data["categories"].items():
                # SKILL_CATEGORIES values are dicts: {"skills": [...], "trigger": "..."}
                names = payload.get("skills") if isinstance(payload, dict) else payload
                for sk_name in (names or []):
                    cat_lookup[sk_name] = cat_name
            for name, definition in sk.items():
                desc = (definition.get("description") if isinstance(definition, dict) else "") or ""
                params = (definition.get("parameters") if isinstance(definition, dict) else {}) or {}
                cat = cat_lookup.get(name, "Uncategorized")
                _upsert(
                    c,
                    nid=f"skill-{name}",
                    ntype="Skill",
                    name=name,
                    content={"description": desc, "parameters": list(params.keys()) if isinstance(params, dict) else [], "category": cat},
                    meta={"synced_from": "ccc-code", "category": cat},
                )
                skills_added += 1

    # ── Playbooks ────────────────────────────────────────────
    if pb_dir:
        print(f"[playbooks] loading from {pb_dir}")
        for f in sorted(pb_dir.glob("*.yaml")):
            try:
                pb = _load_playbook_yaml(f)
            except Exception as e:
                print(f"[WARN] {f.name} parse failed: {e}", file=sys.stderr)
                continue
            pid = pb.get("playbook_id") or f.stem
            name = pb.get("name") or f.stem
            desc = pb.get("description") or ""
            steps = pb.get("plan") or pb.get("steps") or []
            _upsert(
                c,
                nid=f"pb-{pid}",
                ntype="Playbook",
                name=name,
                content={
                    "playbook_id": pid,
                    "name": name,
                    "description": desc,
                    "version": pb.get("version", ""),
                    "risk_level": pb.get("risk_level", "low"),
                    "step_count": len(steps),
                    "step_names": [s.get("name") for s in steps if isinstance(s, dict)][:30],
                },
                meta={"synced_from": "ccc-yaml", "source_path": str(f)},
            )
            pbs_added += 1
            # Edge: Playbook --uses--> Skill (if step.skill listed)
            for s in steps:
                if not isinstance(s, dict):
                    continue
                sk = s.get("skill")
                if sk:
                    try:
                        c.execute(
                            "INSERT INTO edges (src, dst, type, weight, meta) VALUES (?,?,?,?,?) "
                            "ON CONFLICT(src,dst,type) DO UPDATE SET weight = edges.weight + 1",
                            (f"pb-{pid}", f"skill-{sk}", "uses", 1.0, json.dumps({"synced_from": "ccc-yaml"})),
                        )
                    except sqlite3.IntegrityError:
                        pass

    c.commit()
    # Stats
    sk_total = c.execute("SELECT COUNT(*) FROM nodes WHERE type='Skill'").fetchone()[0]
    pb_total = c.execute("SELECT COUNT(*) FROM nodes WHERE type='Playbook'").fetchone()[0]
    c.close()

    print()
    print(f"[done] upserted {skills_added} Skills + {pbs_added} Playbooks")
    print(f"[kg]   total Skills now {sk_total}, Playbooks now {pb_total}")


if __name__ == "__main__":
    main()
