"""
Module kết nối DB: Supabase PostgreSQL hoặc SQLite local.
Tự động fallback về SQLite nếu Supabase lỗi.
"""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from config import DB_PATH


DATABASE_URL = os.getenv("DATABASE_URL", "")

try:
    import streamlit as st
    if "DATABASE_URL" in st.secrets:
        DATABASE_URL = st.secrets["DATABASE_URL"]
except Exception:
    pass

_SQLITE_PATH = os.getenv("SQLITE_PATH", DB_PATH)
_USE_POSTGRES = False
_DRIVER = None
_FALLBACK_REASON = ""
_CONNECTION_TESTED = False


def _test_postgres_connection():
    global _USE_POSTGRES, _DRIVER, _FALLBACK_REASON, _CONNECTION_TESTED

    if _CONNECTION_TESTED:
        return
    _CONNECTION_TESTED = True

    if not DATABASE_URL or not DATABASE_URL.startswith("postgres"):
        _FALLBACK_REASON = "Không có DATABASE_URL"
        print("[DB] Không có DATABASE_URL → SQLite")
        return

    try:
        import psycopg
        _DRIVER = "psycopg3"
    except ImportError:
        try:
            import psycopg2
            _DRIVER = "psycopg2"
        except ImportError:
            _FALLBACK_REASON = "Không có driver"
            print("[DB] Không có driver → SQLite")
            return

    dsn = DATABASE_URL.strip()
    if "sslmode" not in dsn:
        sep = "&" if "?" in dsn else "?"
        dsn = f"{dsn}{sep}sslmode=require"

    try:
        if _DRIVER == "psycopg3":
            import psycopg
            conn = psycopg.connect(dsn, connect_timeout=10,
                                   prepare_threshold=None)
            conn.close()
        else:
            import psycopg2
            conn = psycopg2.connect(dsn, connect_timeout=10)
            conn.close()
        _USE_POSTGRES = True
        print(f"[DB] ✅ Supabase OK ({_DRIVER})")
    except Exception as e:
        _USE_POSTGRES = False
        _FALLBACK_REASON = f"Supabase lỗi: {str(e)[:200]}"
        print(f"[DB] ⚠️ {_FALLBACK_REASON}")
        print(f"[DB] → Fallback SQLite: {_SQLITE_PATH}")


def _adapt_sql(sql: str) -> str:
    return sql.replace("?", "%s") if _USE_POSTGRES else sql


@contextmanager
def get_connection():
    _test_postgres_connection()

    if _USE_POSTGRES and _DRIVER:
        dsn = DATABASE_URL.strip()
        if "sslmode" not in dsn:
            sep = "&" if "?" in dsn else "?"
            dsn = f"{dsn}{sep}sslmode=require"
        try:
            if _DRIVER == "psycopg3":
                import psycopg
                conn = psycopg.connect(dsn, connect_timeout=15,
                                       prepare_threshold=None)
            else:
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
            return
        except Exception as e:
            print(f"[DB] ⚠️ Postgres runtime lỗi: {e}")
            print(f"[DB] → Fallback SQLite")

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
    if isinstance(conn, sqlite3.Connection):
        return conn.cursor()
    if _DRIVER == "psycopg3":
        try:
            from psycopg.rows import dict_row
            return conn.cursor(row_factory=dict_row)
        except Exception:
            return conn.cursor()
    elif _DRIVER == "psycopg2":
        try:
            import psycopg2.extras
            return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        except Exception:
            return conn.cursor()
    return conn.cursor()


def execute(conn, sql: str, params: tuple = None):
    is_sqlite = isinstance(conn, sqlite3.Connection)
    cur = _get_cursor(conn)
    final_sql = sql if is_sqlite else _adapt_sql(sql)
    if params:
        cur.execute(final_sql, params)
    else:
        cur.execute(final_sql)
    return cur


def fetchall(conn, sql: str, params: tuple = None):
    cur = execute(conn, sql, params)
    return [dict(r) for r in cur.fetchall()]


def fetchone(conn, sql: str, params: tuple = None):
    cur = execute(conn, sql, params)
    row = cur.fetchone()
    return dict(row) if row else None


def is_postgres() -> bool:
    _test_postgres_connection()
    return _USE_POSTGRES


def get_db_info() -> dict:
    _test_postgres_connection()
    if _USE_POSTGRES:
        url_safe = DATABASE_URL
        if "@" in url_safe and ":" in url_safe.split("@")[0]:
            parts = url_safe.split("@")
            user_part = parts[0].split("//")[-1]
            user = user_part.split(":")[0]
            url_safe = f"postgresql://{user}:***@{parts[1]}"
        return {"type": f"PostgreSQL ({_DRIVER})", "url": url_safe,
                "persistent": True}
    return {"type": "SQLite (local)", "path": _SQLITE_PATH,
            "persistent": False, "reason": _FALLBACK_REASON or "Không có URL"}


# ============================================================
# TỰ ĐỘNG TẠO BẢNG BULLETINS
# ============================================================
def _ensure_bulletins_table():
    try:
        with get_connection() as conn:
            if _USE_POSTGRES and _DRIVER:
                execute(conn, """
                    CREATE TABLE IF NOT EXISTS bulletins (
                        id SERIAL PRIMARY KEY,
                        created_at TEXT NOT NULL,
                        category TEXT NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT,
                        filename TEXT,
                        file_size INTEGER,
                        file_data TEXT,
                        uploader TEXT DEFAULT 'admin'
                    )
                """)
            else:
                execute(conn, """
                    CREATE TABLE IF NOT EXISTS bulletins (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        created_at TEXT NOT NULL,
                        category TEXT NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT,
                        filename TEXT,
                        file_size INTEGER,
                        file_data TEXT,
                        uploader TEXT DEFAULT 'admin'
                    )
                """)
    except Exception as e:
        print(f"[DB] Lỗi tạo bảng bulletins: {e}")


try:
    _ensure_bulletins_table()
except Exception as e:
    print(f"[DB] Không thể khởi tạo bảng: {e}")