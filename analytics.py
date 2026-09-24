"""
Module theo dõi truy cập — có cache cho stats.
"""

import hashlib
from datetime import datetime, timedelta
from typing import Dict, List
import streamlit as st

from db import get_connection, execute, fetchall, fetchone, is_postgres


def _ensure_visits_table():
    with get_connection() as conn:
        if is_postgres():
            execute(conn, """
                CREATE TABLE IF NOT EXISTS visits (
                    id SERIAL PRIMARY KEY, session_id TEXT NOT NULL,
                    user_id INTEGER, username TEXT, ip_hash TEXT,
                    user_agent TEXT, page TEXT, action TEXT,
                    created_at TEXT NOT NULL)
            """)
        else:
            execute(conn, """
                CREATE TABLE IF NOT EXISTS visits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL, user_id INTEGER,
                    username TEXT, ip_hash TEXT, user_agent TEXT,
                    page TEXT, action TEXT, created_at TEXT NOT NULL)
            """)
        try:
            execute(conn,
                "CREATE INDEX IF NOT EXISTS idx_visits_created ON visits(created_at)")
        except Exception:
            pass


def log_visit(session_id: str, user_id: int = None, username: str = None,
              ip: str = None, user_agent: str = None,
              page: str = "main", action: str = "view"):
    _ensure_visits_table()
    ip_hash = hashlib.md5(ip.encode()).hexdigest()[:16] if ip else ""
    try:
        with get_connection() as conn:
            execute(conn, """
                INSERT INTO visits
                (session_id, user_id, username, ip_hash, user_agent,
                 page, action, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (session_id, user_id, username, ip_hash,
                  (user_agent or "")[:200], page, action,
                  datetime.utcnow().isoformat()))
    except Exception as e:
        print(f"[ANALYTICS] Lỗi: {e}")


def _count(conn, sql, params=None):
    row = fetchone(conn, sql, params)
    if not row:
        return 0
    return list(row.values())[0] or 0


@st.cache_data(ttl=120, show_spinner=False)
def get_stats() -> Dict:
    """Cached 2 phút."""
    _ensure_visits_table()
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0).isoformat()
    week_start = (now - timedelta(days=7)).isoformat()
    month_start = (now - timedelta(days=30)).isoformat()

    stats = {}
    with get_connection() as conn:
        stats["total_views"] = _count(conn, "SELECT COUNT(*) as c FROM visits")
        stats["unique_sessions"] = _count(conn,
            "SELECT COUNT(DISTINCT session_id) as c FROM visits")
        stats["views_today"] = _count(conn,
            "SELECT COUNT(*) as c FROM visits WHERE created_at >= ?",
            (today_start,))
        stats["unique_today"] = _count(conn,
            "SELECT COUNT(DISTINCT session_id) as c FROM visits WHERE created_at >= ?",
            (today_start,))
        stats["views_week"] = _count(conn,
            "SELECT COUNT(*) as c FROM visits WHERE created_at >= ?",
            (week_start,))
        stats["unique_week"] = _count(conn,
            "SELECT COUNT(DISTINCT session_id) as c FROM visits WHERE created_at >= ?",
            (week_start,))
        stats["views_month"] = _count(conn,
            "SELECT COUNT(*) as c FROM visits WHERE created_at >= ?",
            (month_start,))
        try:
            stats["total_users"] = _count(conn, "SELECT COUNT(*) as c FROM users")
            stats["active_users"] = _count(conn,
                "SELECT COUNT(*) as c FROM users WHERE is_active = 1")
        except Exception:
            stats["total_users"] = 0
            stats["active_users"] = 0
    return stats


@st.cache_data(ttl=300, show_spinner=False)
def get_visits_by_day(days: int = 30) -> List[Dict]:
    """Cached 5 phút."""
    _ensure_visits_table()
    start = (datetime.utcnow() - timedelta(days=days)).isoformat()
    with get_connection() as conn:
        rows = fetchall(conn, """
            SELECT substr(created_at, 1, 10) AS day,
                   COUNT(*) AS views,
                   COUNT(DISTINCT session_id) AS unique_sessions
            FROM visits WHERE created_at >= ?
            GROUP BY substr(created_at, 1, 10)
            ORDER BY day
        """, (start,))
    return [{"day": r["day"], "views": r["views"],
             "unique_sessions": r["unique_sessions"]} for r in rows]


@st.cache_data(ttl=60, show_spinner=False)
def get_recent_visits(limit: int = 100) -> List[Dict]:
    """Cached 1 phút."""
    _ensure_visits_table()
    with get_connection() as conn:
        return fetchall(conn, """
            SELECT id, session_id, username, page, action, created_at
            FROM visits ORDER BY created_at DESC LIMIT ?
        """, (limit,))


@st.cache_data(ttl=300, show_spinner=False)
def get_top_pages(limit: int = 10) -> List[Dict]:
    """Cached 5 phút."""
    _ensure_visits_table()
    with get_connection() as conn:
        rows = fetchall(conn, """
            SELECT page, COUNT(*) AS views FROM visits
            GROUP BY page ORDER BY views DESC LIMIT ?
        """, (limit,))
    return [{"page": r["page"], "views": r["views"]} for r in rows]