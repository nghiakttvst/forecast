"""
Module theo dõi lượt truy cập, thống kê người dùng.
"""

import sqlite3
import os
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List
from config import DB_PATH


def _ensure_visits_table():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            user_id INTEGER,
            username TEXT,
            ip_hash TEXT,
            user_agent TEXT,
            page TEXT,
            action TEXT,
            created_at TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_visits_created
        ON visits(created_at)
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_visits_session
        ON visits(session_id)
    """)
    conn.commit()
    conn.close()


def log_visit(
    session_id: str,
    user_id: int = None,
    username: str = None,
    ip: str = None,
    user_agent: str = None,
    page: str = "main",
    action: str = "view",
):
    """Ghi log 1 lượt truy cập."""
    _ensure_visits_table()

    ip_hash = ""
    if ip:
        ip_hash = hashlib.md5(ip.encode()).hexdigest()[:16]

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO visits
            (session_id, user_id, username, ip_hash, user_agent, page, action, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id, user_id, username, ip_hash,
            (user_agent or "")[:200], page, action,
            datetime.utcnow().isoformat(),
        ))
        conn.commit()
    except Exception as e:
        print(f"[ANALYTICS] Lỗi log: {e}")
    finally:
        conn.close()


# ============================================================
# THỐNG KÊ
# ============================================================
def get_stats() -> Dict:
    """Thống kê tổng quan."""
    _ensure_visits_table()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0).isoformat()
    week_start = (now - timedelta(days=7)).isoformat()
    month_start = (now - timedelta(days=30)).isoformat()

    stats = {}

    cur.execute("SELECT COUNT(*) FROM visits")
    stats["total_views"] = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT session_id) FROM visits")
    stats["unique_sessions"] = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM visits WHERE created_at >= ?", (today_start,))
    stats["views_today"] = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(DISTINCT session_id) FROM visits WHERE created_at >= ?",
        (today_start,),
    )
    stats["unique_today"] = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM visits WHERE created_at >= ?", (week_start,))
    stats["views_week"] = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(DISTINCT session_id) FROM visits WHERE created_at >= ?",
        (week_start,),
    )
    stats["unique_week"] = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM visits WHERE created_at >= ?", (month_start,))
    stats["views_month"] = cur.fetchone()[0]

    try:
        cur.execute("SELECT COUNT(*) FROM users")
        stats["total_users"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
        stats["active_users"] = cur.fetchone()[0]
    except Exception:
        stats["total_users"] = 0
        stats["active_users"] = 0

    conn.close()
    return stats


def get_visits_by_day(days: int = 30) -> List[Dict]:
    """Lấy lượt xem theo ngày trong N ngày qua."""
    _ensure_visits_table()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    start = (datetime.utcnow() - timedelta(days=days)).isoformat()
    cur.execute("""
        SELECT
            substr(created_at, 1, 10) AS day,
            COUNT(*) AS views,
            COUNT(DISTINCT session_id) AS unique_sessions
        FROM visits
        WHERE created_at >= ?
        GROUP BY day
        ORDER BY day
    """, (start,))
    rows = cur.fetchall()
    conn.close()
    return [
        {"day": r[0], "views": r[1], "unique_sessions": r[2]}
        for r in rows
    ]


def get_recent_visits(limit: int = 100) -> List[Dict]:
    """Lấy danh sách lượt truy cập gần đây."""
    _ensure_visits_table()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT id, session_id, username, page, action, created_at
        FROM visits
        ORDER BY created_at DESC LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_top_pages(limit: int = 10) -> List[Dict]:
    """Top các page được xem nhiều nhất."""
    _ensure_visits_table()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT page, COUNT(*) AS views
        FROM visits
        GROUP BY page
        ORDER BY views DESC LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return [{"page": r[0], "views": r[1]} for r in rows]
