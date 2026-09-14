"""
Module kết nối DB tập trung: Supabase PostgreSQL hoặc SQLite local.
Tự động chọn dựa trên biến môi trường DATABASE_URL.
"""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from config import DB_PATH


# ============================================================
# ĐỌC CẤU HÌNH
# ============================================================
DATABASE_URL = os.getenv("DATABASE_URL", "")

try:
    import streamlit as st
    if "DATABASE_URL" in st.secrets:
        DATABASE_URL = st.secrets["DATABASE_URL"]
except Exception:
    pass

_SQLITE_PATH = os.getenv("SQLITE_PATH", DB_PATH)
_USE_POSTGRES = bool(DATABASE_URL and DATABASE_URL.startswith("postgres"))


# ============================================================
# HELPERS
# ============================================================
def _adapt_sql(sql: str) -> str:
    """SQLite dùng ?, Postgres dùng %s."""
    if _USE_POSTGRES:
        return sql.replace("?", "%s")
    return sql


@contextmanager
def get_connection():
    """Trả về connection tới Postgres hoặc SQLite."""
    if _USE_POSTGRES:
        try:
            import psycopg2
            import psycopg2.extras
        except ImportError:
            raise RuntimeError(
                "Thiếu psycopg2-binary. Chạy: pip install psycopg2-binary"
            )
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=15)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        Path(_SQLITE_PATH).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(_SQLITE_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def _get_cursor(conn):
    if _USE_POSTGRES:
        import psycopg2.extras
        return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn.cursor()


def execute(conn, sql: str, params: tuple = None):
    cur = _get_cursor(conn)
    sql = _adapt_sql(sql)
    if params:
        cur.execute(sql, params)
    else:
        cur.execute(sql)
    return cur


def fetchall(conn, sql: str, params: tuple = None):
    cur = execute(conn, sql, params)
    rows = cur.fetchall()
    return [dict(r) for r in rows]


def fetchone(conn, sql: str, params: tuple = None):
    cur = execute(conn, sql, params)
    row = cur.fetchone()
    return dict(row) if row else None


# ============================================================
# THÔNG TIN DB
# ============================================================
def is_postgres() -> bool:
    return _USE_POSTGRES


def get_db_info() -> dict:
    if _USE_POSTGRES:
        url_safe = DATABASE_URL
        if "@" in url_safe and ":" in url_safe.split("@")[0]:
            parts = url_safe.split("@")
            user_part = parts[0].split("//")[-1]
            user = user_part.split(":")[0]
            url_safe = f"postgresql://{user}:***@{parts[1]}"
        return {"type": "PostgreSQL (Supabase)", "url": url_safe, "persistent": True}
    return {"type": "SQLite (local)", "path": _SQLITE_PATH, "persistent": False}