"""
Module kết nối DB tập trung: Supabase PostgreSQL hoặc SQLite local.
Tự động chọn dựa trên biến môi trường DATABASE_URL.
Hỗ trợ: psycopg (v3) → psycopg2 → SQLite fallback.
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

# Phát hiện driver khả dụng
_DRIVER = None
if _USE_POSTGRES:
    try:
        import psycopg  # v3
        from psycopg.rows import dict_row
        _DRIVER = "psycopg3"
        print("[DB] Sử dụng driver: psycopg (v3)")
    except ImportError:
        try:
            import psycopg2
            import psycopg2.extras
            _DRIVER = "psycopg2"
            print("[DB] Sử dụng driver: psycopg2 (v2)")
        except ImportError:
            print("[DB] ⚠️ Không có psycopg/psycopg2 → chuyển sang SQLite")
            _USE_POSTGRES = False
            _DRIVER = None


# ============================================================
# HELPERS
# ============================================================
def _adapt_sql(sql: str) -> str:
    """SQLite dùng ?, Postgres dùng %s."""
    if _USE_POSTGRES:
        return sql.replace("?", "%s")
    return sql


def _clean_dsn(url: str) -> str:
    """
    Chuẩn hóa DSN:
    - Bỏ khoảng trắng đầu/cuối
    - Thêm sslmode=require nếu chưa có
    """
    url = url.strip()
    if _USE_POSTGRES and "sslmode" not in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}sslmode=require"
    return url


@contextmanager
def get_connection():
    """Trả về connection tới Postgres hoặc SQLite."""
    if _USE_POSTGRES and _DRIVER:
        dsn = _clean_dsn(DATABASE_URL)

        if _DRIVER == "psycopg3":
            import psycopg
            conn = psycopg.connect(dsn, connect_timeout=15)
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

        elif _DRIVER == "psycopg2":
            import psycopg2
            conn = psycopg2.connect(dsn, connect_timeout=15)
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
    else:
        # SQLite fallback
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
    """Trả về cursor phù hợp với driver."""
    if _DRIVER == "psycopg3":
        from psycopg.rows import dict_row
        return conn.cursor(row_factory=dict_row)
    elif _DRIVER == "psycopg2":
        import psycopg2.extras
        return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn.cursor()


def execute(conn, sql: str, params: tuple = None):
    """Execute SQL với placeholder tự động chuyển đổi."""
    cur = _get_cursor(conn)
    sql = _adapt_sql(sql)
    if params:
        cur.execute(sql, params)
    else:
        cur.execute(sql)
    return cur


def fetchall(conn, sql: str, params: tuple = None):
    """Execute + fetch all, trả về list of dict."""
    cur = execute(conn, sql, params)
    rows = cur.fetchall()
    return [dict(r) for r in rows]


def fetchone(conn, sql: str, params: tuple = None):
    """Execute + fetch one."""
    cur = execute(conn, sql, params)
    row = cur.fetchone()
    return dict(row) if row else None


# ============================================================
# THÔNG TIN DB
# ============================================================
def is_postgres() -> bool:
    return _USE_POSTGRES and _DRIVER is not None


def get_db_info() -> dict:
    if is_postgres():
        url_safe = DATABASE_URL
        if "@" in url_safe and ":" in url_safe.split("@")[0]:
            parts = url_safe.split("@")
            user_part = parts[0].split("//")[-1]
            user = user_part.split(":")[0]
            url_safe = f"postgresql://{user}:***@{parts[1]}"
        return {"type": f"PostgreSQL ({_DRIVER})", "url": url_safe, "persistent": True}
    return {
        "type": "SQLite (local)",
        "path": _SQLITE_PATH,
        "persistent": False,
        "reason": "Thiếu driver hoặc DATABASE_URL",
    }