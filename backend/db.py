from __future__ import annotations

import json
import threading
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from psycopg2 import pool as pg_pool

from .config import settings

_pool: pg_pool.ThreadedConnectionPool | None = None
_lock = threading.Lock()


def _get_pool() -> pg_pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        with _lock:
            if _pool is None:
                _pool = pg_pool.ThreadedConnectionPool(
                    minconn=1,
                    maxconn=10,
                    dsn=settings.DATABASE_URL,
                )
    return _pool


@contextmanager
def get_conn():
    conn = _get_pool().getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _get_pool().putconn(conn)


def query(sql: str, params: tuple | list | dict | None = None, one: bool = False):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            if one:
                return rows[0] if rows else None
            return rows


def execute(sql: str, params: tuple | list | dict | None = None) -> str | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if cur.description is not None:
                return cur.fetchone()[0]
            return None


def to_uuid(value) -> str:
    return str(value)


def jsonb(val):
    return json.dumps(val)
