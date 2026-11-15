"""
Tiny database layer that runs the SAME SQL on SQLite (dev/tests) and
PostgreSQL (docker-compose). Queries are written with ``:name`` parameters;
for PostgreSQL they are rewritten to psycopg's ``%(name)s`` style.
"""
from __future__ import annotations

import re
import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional

_NAMED = re.compile(r"(?<![:\w]):(\w+)")
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


class Database:
    def __init__(self, url: str):
        self.url = url
        self._lock = threading.RLock()
        if url.startswith("sqlite"):
            self.dialect = "sqlite"
            rest = url[len("sqlite:"):]
            path = rest[3:] if rest.startswith("///") else ""
            path = path or ":memory:"
            if path != ":memory:":
                Path(path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        elif url.startswith(("postgresql://", "postgres://")):
            self.dialect = "postgres"
            import psycopg  # imported lazily so SQLite dev needs no driver
            from psycopg.rows import dict_row

            self._conn = psycopg.connect(url, autocommit=True, row_factory=dict_row)
        else:
            raise ValueError(f"Unsupported DATABASE_URL: {url!r}")

    # -- internals ---------------------------------------------------------
    def _prepare(self, sql: str) -> str:
        return _NAMED.sub(r"%(\1)s", sql) if self.dialect == "postgres" else sql

    # -- public API --------------------------------------------------------
    def execute(self, sql: str, params: Optional[dict[str, Any]] = None) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(self._prepare(sql), params or {})
            if self.dialect == "sqlite":
                self._conn.commit()
            cur.close()

    def query(self, sql: str, params: Optional[dict[str, Any]] = None) -> list[dict]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(self._prepare(sql), params or {})
            rows = [dict(r) for r in cur.fetchall()]
            cur.close()
            return rows

    def init_schema(self) -> None:
        script = SCHEMA_PATH.read_text(encoding="utf-8")
        # drop SQL comments, then run statement by statement (works on both engines)
        script = "\n".join(l for l in script.splitlines() if not l.strip().startswith("--"))
        for stmt in (s.strip() for s in script.split(";")):
            if stmt:
                self.execute(stmt)

    def close(self) -> None:
        with self._lock:
            self._conn.close()
