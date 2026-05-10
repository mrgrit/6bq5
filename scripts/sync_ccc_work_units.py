"""Sync the REAL work units of CCC into 6bq5 KG as Playbook nodes.

Background: CCC seeded only 8 'operational playbooks' (probe/IR/audit/...)
into the KG, but the platform's actual work-unit assets are spread across
contents/labs/, contents/education/, contents/battle-scenarios/, etc. and
total ~6,700 distinct work units. Without these the KG can't answer questions
like "what does the platform actually DO" or rank-by-importance the things
that learners and the agent really exercise.

Mapping (each becomes one Playbook node):

  labs/<course>/<week>.yaml        each `steps[]` entry  → pb:lab:<course>:<week>:<order>
  battle-scenarios/<file>.yaml      whole file            → pb:battle:<stem>
  education/<course>/<week>/lecture.md  whole file        → pb:lecture:<course>:<week>
  threats/<file>                    whole file            → pb:threat:<stem>
  rules/<wazuh|suricata>/<file>     whole file            → pb:rule:<source>:<stem>
  curriculum/<file>                 whole file            → pb:curriculum:<stem>
  contents/playbooks/<file>.yaml    whole file            → pb-<id>          (legacy 8)

Edges added:
  pb:lab:<c>:<w>:<o>  --uses-->        skill-<step.skill>
  pb:lab:<c>:<w>:<o>  --targets-->     asset-vm-<step.target_vm>
  pb:lab:<c>:<w>:<o>  --handles-->     concept:category:<step.category>
  pb:lab:<c>:<w>:<o>  --belongs_to-->  pb:lab-week:<c>:<w>     (course-week 묶음)
  pb:lab-week:<c>:<w> --belongs_to-->  pb:lab-course:<c>
  pb:lecture:<c>:<w>  --belongs_to-->  pb:lab-course:<c>

All synced nodes carry meta.synced_from = 'ccc-work-units'.

Usage:
  python3 scripts/sync_ccc_work_units.py
  CCC_HOME=/path/to/ccc python3 scripts/sync_ccc_work_units.py
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("[FATAL] pyyaml required: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


HERE = Path(__file__).resolve().parent
DST_DB = (HERE.parent / "data" / "kg.db").resolve()


def _ccc_root() -> Path | None:
    if os.environ.get("CCC_HOME"):
        return Path(os.environ["CCC_HOME"])
    for c in [Path.home() / "ccc", Path("/home/opsclaw/ccc"), Path("/opt/ccc")]:
        if (c / "contents").is_dir():
            return c
    return None


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DST_DB)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode = WAL")
    c.execute("PRAGMA busy_timeout = 5000")
    return c


def _safe_text(v) -> str:
    if v is None:
        return ""
    return str(v)[:1500]


def _upsert_node(c, nid: str, ntype: str, name: str, content: dict, meta: dict):
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
        (nid, ntype, name[:200], json.dumps(content, ensure_ascii=False),
         json.dumps(meta, ensure_ascii=False)),
    )
    c.execute("DELETE FROM nodes_fts WHERE id = ?", (nid,))
    fts = " ".join([
        name,
        _safe_text(content.get("description")),
        _safe_text(content.get("instruction")),
        _safe_text(content.get("category")),
    ])
    c.execute(
        "INSERT INTO nodes_fts (id, type, name, content_text) VALUES (?,?,?,?)",
        (nid, ntype, name[:200], fts),
    )


def _upsert_edge(c, src, dst, etype, weight=1.0, meta=None):
    try:
        c.execute(
            """
            INSERT INTO edges (src, dst, type, weight, meta)
            VALUES (?,?,?,?,?)
            ON CONFLICT(src, dst, type) DO UPDATE SET
                weight = edges.weight + 1,
                meta = excluded.meta
            """,
            (src, dst, etype, weight, json.dumps(meta or {"synced_from": "ccc-work-units"})),
        )
    except sqlite3.IntegrityError:
        pass


# ──────────────────────────────────────────────────────────────────────
# Importers
# ──────────────────────────────────────────────────────────────────────

def import_labs(c, root: Path) -> dict:
    counts = {"course": 0, "week": 0, "step": 0, "edges": 0}
    seen_courses: set[str] = set()
    for f in sorted((root / "contents/labs").rglob("*.yaml")):
        try:
            d = yaml.safe_load(f.read_text())
        except Exception:
            continue
        if not d or not isinstance(d, dict):
            continue
        course = d.get("course") or f.parent.name
        week = d.get("week") or f.stem  # weekNN
        # course node
        course_id = f"pb:lab-course:{course}"
        if course not in seen_courses:
            _upsert_node(c, course_id, "Playbook",
                         f"[course] {course}",
                         content={"kind": "lab_course", "course": course},
                         meta={"synced_from": "ccc-work-units", "kind": "lab_course"})
            counts["course"] += 1
            seen_courses.add(course)
        # week node
        week_id = f"pb:lab-week:{course}:{week}"
        _upsert_node(c, week_id, "Playbook",
                     f"[week] {course}/{week} — {d.get('title','')}",
                     content={
                         "kind": "lab_week",
                         "course": course,
                         "week": week,
                         "title": d.get("title", ""),
                         "description": d.get("description", "")[:500],
                         "objectives": d.get("objectives", []),
                         "difficulty": d.get("difficulty"),
                         "duration_minutes": d.get("duration_minutes"),
                         "step_count": len(d.get("steps") or []),
                     },
                     meta={"synced_from": "ccc-work-units", "kind": "lab_week",
                           "course": course, "week": str(week)})
        _upsert_edge(c, week_id, course_id, "belongs_to")
        counts["week"] += 1
        # step nodes
        for step in (d.get("steps") or []):
            order = step.get("order")
            if order is None:
                continue
            sid = f"pb:lab:{course}:{week}:{order}"
            instr = step.get("instruction", "")
            _upsert_node(c, sid, "Playbook",
                         f"{course}/{week}/step{order}: {instr[:80]}",
                         content={
                             "kind": "lab_step",
                             "course": course,
                             "week": week,
                             "order": order,
                             "instruction": instr[:600],
                             "hint": step.get("hint", "")[:300],
                             "category": step.get("category"),
                             "points": step.get("points"),
                             "answer": str(step.get("answer", ""))[:200],
                             "verify": step.get("verify"),
                             "target_vm": step.get("target_vm"),
                             "risk_level": step.get("risk_level", "low"),
                             "bastion_prompt": step.get("bastion_prompt", "")[:300],
                         },
                         meta={"synced_from": "ccc-work-units", "kind": "lab_step",
                               "course": course, "week": str(week), "order": order,
                               "category": step.get("category"),
                               "risk_level": step.get("risk_level", "low")})
            _upsert_edge(c, sid, week_id, "belongs_to")
            counts["step"] += 1
            # uses → skill (if present)
            sk = step.get("skill") or (step.get("verify", {}) or {}).get("skill")
            if sk:
                _upsert_edge(c, sid, f"skill-{sk}", "uses")
                counts["edges"] += 1
            # targets → asset
            tgt = step.get("target_vm")
            if tgt:
                _upsert_edge(c, sid, f"asset-vm-{tgt}", "targets")
                counts["edges"] += 1
            # handles → concept (category)
            cat = step.get("category")
            if cat:
                _upsert_node(c, f"concept:category:{cat}", "Concept",
                             cat, content={"kind": "lab_category"},
                             meta={"synced_from": "ccc-work-units", "kind": "lab_category"})
                _upsert_edge(c, sid, f"concept:category:{cat}", "handles")
                counts["edges"] += 1
    return counts


def import_battle(c, root: Path) -> dict:
    n = 0
    edges = 0
    bdir = root / "contents/battle-scenarios"
    if not bdir.is_dir():
        return {"battle": 0}
    for f in sorted(bdir.glob("*.yaml")):
        try:
            d = yaml.safe_load(f.read_text())
        except Exception:
            continue
        if not d:
            continue
        bid = f"pb:battle:{f.stem}"
        missions = d.get("missions") or d.get("phases") or d.get("steps") or []
        _upsert_node(c, bid, "Playbook",
                     f"[battle] {d.get('title') or f.stem}",
                     content={
                         "kind": "battle_scenario",
                         "title": d.get("title", f.stem),
                         "description": _safe_text(d.get("description")),
                         "phases": len(missions),
                         "phase_titles": [m.get("title") if isinstance(m, dict) else str(m) for m in missions[:30]],
                     },
                     meta={"synced_from": "ccc-work-units", "kind": "battle_scenario"})
        n += 1
        # mission nodes
        for i, m in enumerate(missions, 1):
            if not isinstance(m, dict):
                continue
            mid = f"{bid}:m{i}"
            _upsert_node(c, mid, "Playbook",
                         f"{f.stem}/m{i}: {(m.get('title') or '')[:80]}",
                         content={"kind": "battle_mission", "scenario": f.stem,
                                  "phase": i, **{k: m.get(k) for k in ('title', 'description', 'objective', 'verify') if k in m}},
                         meta={"synced_from": "ccc-work-units", "kind": "battle_mission"})
            _upsert_edge(c, mid, bid, "belongs_to")
            n += 1
            edges += 1
    return {"battle": n, "battle_edges": edges}


def import_education(c, root: Path) -> dict:
    n = 0
    for f in sorted((root / "contents/education").rglob("lecture.md")):
        # path: .../education/<course>/<week>/lecture.md
        parts = f.relative_to(root / "contents/education").parts
        if len(parts) < 3:
            continue
        course, week = parts[0], parts[1]
        body = f.read_text()
        sections = re.findall(r"^##\s+(.+)$", body, re.M)[:30]
        lid = f"pb:lecture:{course}:{week}"
        _upsert_node(c, lid, "Playbook",
                     f"[lecture] {course}/{week}",
                     content={
                         "kind": "lecture",
                         "course": course, "week": week,
                         "lines": body.count("\n"),
                         "section_count": len(sections),
                         "section_titles": sections,
                         "head": body[:600],
                     },
                     meta={"synced_from": "ccc-work-units", "kind": "lecture",
                           "course": course, "week": week})
        _upsert_edge(c, lid, f"pb:lab-course:{course}", "belongs_to")
        n += 1
    return {"lecture": n}


def import_threats(c, root: Path) -> dict:
    n = 0
    tdir = root / "contents/threats"
    if not tdir.is_dir():
        return {"threat": 0}
    for f in sorted(tdir.rglob("*")):
        if not f.is_file():
            continue
        if f.suffix not in (".yaml", ".yml", ".md", ".json"):
            continue
        tid = f"pb:threat:{f.stem}"
        title = f.stem
        desc = ""
        if f.suffix in (".yaml", ".yml"):
            try:
                d = yaml.safe_load(f.read_text()) or {}
                title = d.get("title") or d.get("name") or f.stem
                desc = _safe_text(d.get("description"))
            except Exception:
                pass
        else:
            desc = f.read_text()[:600]
        _upsert_node(c, tid, "Playbook",
                     f"[threat] {title}",
                     content={"kind": "threat", "title": title, "description": desc, "source": str(f.relative_to(root))},
                     meta={"synced_from": "ccc-work-units", "kind": "threat"})
        n += 1
    return {"threat": n}


def import_rules(c, root: Path) -> dict:
    n = 0
    for src in ("wazuh", "suricata"):
        d = root / "contents/rules" / src
        if not d.is_dir():
            continue
        for f in sorted(d.iterdir()):
            if not f.is_file():
                continue
            rid = f"pb:rule:{src}:{f.stem}"
            _upsert_node(c, rid, "Playbook",
                         f"[rule:{src}] {f.stem}",
                         content={"kind": f"rule_{src}", "head": f.read_text()[:600], "source": str(f.relative_to(root))},
                         meta={"synced_from": "ccc-work-units", "kind": f"rule_{src}"})
            n += 1
    return {"rule": n}


def import_curriculum(c, root: Path) -> dict:
    n = 0
    cdir = root / "contents/curriculum"
    if not cdir.is_dir():
        return {"curriculum": 0}
    for f in sorted(cdir.rglob("*")):
        if not f.is_file() or f.suffix not in (".yaml", ".yml", ".md", ".json"):
            continue
        cid = f"pb:curriculum:{f.stem}"
        _upsert_node(c, cid, "Playbook",
                     f"[curriculum] {f.stem}",
                     content={"kind": "curriculum", "head": f.read_text()[:600], "source": str(f.relative_to(root))},
                     meta={"synced_from": "ccc-work-units", "kind": "curriculum"})
        n += 1
    return {"curriculum": n}


# ──────────────────────────────────────────────────────────────────────

def main() -> None:
    root = _ccc_root()
    if not root:
        print("[FATAL] CCC not found. CCC_HOME=/path/to/ccc", file=sys.stderr)
        sys.exit(1)
    if not DST_DB.exists():
        print(f"[FATAL] {DST_DB} not found. run scripts/import_kg.py first.", file=sys.stderr)
        sys.exit(1)

    print(f"[ccc]  {root}")
    print(f"[dst]  {DST_DB}")
    print()

    c = _conn()
    print("[1/5] importing labs...")
    r1 = import_labs(c, root)
    c.commit()
    print(f"      courses={r1['course']}  weeks={r1['week']}  steps={r1['step']}  edges={r1['edges']}")

    print("[2/5] importing battle-scenarios...")
    r2 = import_battle(c, root)
    c.commit()
    print(f"      {r2}")

    print("[3/5] importing education lectures...")
    r3 = import_education(c, root)
    c.commit()
    print(f"      {r3}")

    print("[4/5] importing threats...")
    r4 = import_threats(c, root)
    c.commit()
    print(f"      {r4}")

    print("[5/5] importing rules + curriculum...")
    r5 = import_rules(c, root)
    r6 = import_curriculum(c, root)
    c.commit()
    print(f"      rules={r5} curriculum={r6}")

    # Summary
    pb = c.execute("SELECT COUNT(*) FROM nodes WHERE type='Playbook'").fetchone()[0]
    sk = c.execute("SELECT COUNT(*) FROM nodes WHERE type='Skill'").fetchone()[0]
    asset = c.execute("SELECT COUNT(*) FROM nodes WHERE type='Asset'").fetchone()[0]
    cp = c.execute("SELECT COUNT(*) FROM nodes WHERE type='Concept'").fetchone()[0]
    edges = c.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    total = c.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
    c.close()

    print()
    print("=" * 50)
    print(f"KG totals after sync:")
    print(f"  Playbook : {pb}")
    print(f"  Skill    : {sk}")
    print(f"  Asset    : {asset}")
    print(f"  Concept  : {cp}")
    print(f"  edges    : {edges}")
    print(f"  total    : {total}")


if __name__ == "__main__":
    main()
