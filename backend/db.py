"""Single-file sqlite handle for 6bq5.

The KG schema is inherited from CCC (`packages/bastion/graph.py`).
Experiment / poison / defense tables are added by `scripts/import_kg.py`.
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


HERE = Path(__file__).resolve().parent
DEFAULT_DB = (HERE.parent / "data" / "kg.db").resolve()


def db_path() -> str:
    return os.environ.get("KG_DB", str(DEFAULT_DB))


_WAL_INITIALIZED = False


def _init_wal(c: sqlite3.Connection) -> None:
    global _WAL_INITIALIZED
    if _WAL_INITIALIZED:
        return
    try:
        c.execute("PRAGMA journal_mode = WAL")
        c.execute("PRAGMA synchronous = NORMAL")
        _WAL_INITIALIZED = True
    except Exception:
        pass


@contextmanager
def conn() -> Iterator[sqlite3.Connection]:
    c = sqlite3.connect(db_path(), timeout=10.0)
    c.row_factory = sqlite3.Row
    try:
        _init_wal(c)
        c.execute("PRAGMA foreign_keys = ON")
        c.execute("PRAGMA busy_timeout = 5000")
        yield c
        c.commit()
    finally:
        c.close()


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k in row.keys():
        v = row[k]
        if k in ("content", "meta", "params", "result", "payload", "retrieved") and isinstance(v, str):
            try:
                out[k] = json.loads(v) if v else {}
                continue
            except json.JSONDecodeError:
                pass
        out[k] = v
    return out
