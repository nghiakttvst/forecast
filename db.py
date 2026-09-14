"""
Module kết nối DB tập trung.
Tự động fallback: Supabase → SQLite nếu kết nối thất bại.
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

# Trạng thái kết nối
_CONNECTION_TESTED = False
_USE_POSTGRES = False
_DRIVER = None
_FALLBACK_REASON = ""


def _test_postgres_connection():
    """Test kết nối Postgres 1 lần. Nếu fail → fallback SQLite."""
    global _USE_POSTGRES, _DRIVER, _FALLBACK_REASON, _CONNECTION_TESTED

    if _CONNECTION_TESTED:
        return

    _CONNECTION_TESTED = True

    if not DATABASE_URL or not DATABASE_URL.startswith("postgres"):
        _FALLBACK_REASON = "Không có DATABASE_URL"
        print("[DB] ℹ️ Không có DATABASE_URL → dùng SQLite")
        return

    # Thử psycopg3
    try:
        import psycopg
        _DRIVER = "psycopg3"
    except ImportError:
        try:
            import psycopg2
            _DRIVER = "psycopg2"
        except ImportError:
            _FALLBACK_REASON = "Không có driver psycopg/psycopg2"
            print("[DB] ⚠️ Không có driver → dùng SQLite")
            return

    # Test kết nối thực tế
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
        print(f"[DB] ✅ Kết nối Supabase OK ({_DRIVER})")

    except Exception as e:
        _USE_POSTGRES = False
        _FALLBACK_REASON = f"Kết nối Supabase thất bại: {str(e)[:200]}"
        print(f"[DB] ⚠️ {_FALLBACK_REASON}")
        print(f"[DB] → Fallback sang SQLite: {_SQLITE_PATH}")


def _adapt_sql(sql: str) -> str:
    if _USE_POSTGRES:
        return sql.replace("?", "%s")
    return sql


@contextmanager
def get_connection():
    """Trả về connection tới Postgres hoặc SQLite (tự động fallback)."""
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
            print(f"[DB] ⚠️ Postgres lỗi runtime: {e}")
            print(f"[DB] → Chuyển sang SQLite")
            # Không return → rơi xuống SQLite
            _FALLBACK_REASON = str(e)[:200]
            # Chỉ fallback trong phiên này, không đổi global
            _use_sqlite_now = True
    else:
        _use_sqlite_now = True

    # SQLite
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
    if _USE_POSTGRES and _DRIVER == "psycopg3":
        try:
            from psycopg.rows import dict_row
            return conn.cursor(row_factory=dict_row)
        except Exception:
            return conn.cursor()
    elif _USE_POSTGRES and _DRIVER == "psycopg2":
        try:
            import psycopg2.extras
            return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        except Exception:
            return conn.cursor()
    return conn.cursor()


def execute(conn, sql: str, params: tuple = None):
    # Xác định đang dùng DB nào dựa vào kiểu conn
    is_sqlite_conn = isinstance(conn, sqlite3.Connection)

    if is_sqlite_conn:
        cur = conn.cursor()
        if params:
            cur.execute(sql, params)
        else:
            cur.execute(sql)
    else:
        cur = _get_cursor(conn)
        sql_adapted = _adapt_sql(sql)
        if params:
            cur.execute(sql_adapted, params)
        else:
            cur.execute(sql_adapted)
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
        return {
            "type": f"PostgreSQL ({_DRIVER})",
            "url": url_safe,
            "persistent": True,
        }

    return {
        "type": "SQLite (local)",
        "path": _SQLITE_PATH,
        "persistent": False,
        "reason": _FALLBACK_REASON or "Không có DATABASE_URL",
    }