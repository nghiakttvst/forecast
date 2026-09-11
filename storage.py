"""
Module lưu trữ lịch sử dự báo, đánh giá và vị trí yêu thích vào SQLite.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd
from config import DB_PATH


def _ensure_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS forecasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            location TEXT, lat REAL, lon REAL,
            model_key TEXT, variable TEXT,
            horizon_days INTEGER, summary_json TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            location TEXT, lat REAL, lon REAL,
            model_key TEXT, variable TEXT,
            ME REAL, MAE REAL, RMSE REAL, Bias REAL,
            PC REAL, Scf_mean REAL, pct_within_qcvn REAL, n_points INTEGER
        )
    """)
    conn.commit()
    conn.close()


def save_forecast(location: str, lat: float, lon: float, model_key: str,
                  variable: str, horizon_days: int, summary: Dict):
    _ensure_db()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO forecasts
        (created_at, location, lat, lon, model_key, variable, horizon_days, summary_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.utcnow().isoformat(),
        location, lat, lon, model_key, variable, horizon_days,
        json.dumps(summary, default=str),
    ))
    conn.commit()
    conn.close()


def load_forecasts(limit: int = 500) -> pd.DataFrame:
    _ensure_db()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        f"SELECT * FROM forecasts ORDER BY created_at DESC LIMIT {limit}", conn
    )
    conn.close()
    return df


def save_evaluation(location: str, lat: float, lon: float, model_key: str,
                    variable: str, summary: Dict):
    _ensure_db()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO evaluations
        (created_at, location, lat, lon, model_key, variable,
         ME, MAE, RMSE, Bias, PC, Scf_mean, pct_within_qcvn, n_points)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.utcnow().isoformat(),
        location, lat, lon, model_key, variable,
        summary.get("ME"), summary.get("MAE"), summary.get("RMSE"),
        summary.get("Bias"), summary.get("PC"), summary.get("Scf_mean"),
        summary.get("pct_within_qcvn"), summary.get("n_points"),
    ))
    conn.commit()
    conn.close()


def load_evaluations(location: Optional[str] = None,
                     model_key: Optional[str] = None,
                     limit: int = 500) -> pd.DataFrame:
    _ensure_db()
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT * FROM evaluations"
    params = []
    conditions = []
    if location:
        conditions.append("location LIKE ?")
        params.append(f"%{location}%")
    if model_key:
        conditions.append("model_key = ?")
        params.append(model_key)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


# ============================================================
# VỊ TRÍ YÊU THÍCH
# ============================================================
def _ensure_favorites_table():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            address TEXT NOT NULL,
            display TEXT NOT NULL,
            lat REAL, lon REAL
        )
    """)
    conn.commit()
    conn.close()


def save_favorite(address: str, display: str, lat: float, lon: float) -> bool:
    _ensure_favorites_table()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM favorites WHERE display = ?", (display,))
    if cur.fetchone():
        conn.close()
        return False
    cur.execute("""
        INSERT INTO favorites (created_at, address, display, lat, lon)
        VALUES (?, ?, ?, ?, ?)
    """, (datetime.utcnow().isoformat(), address, display, lat, lon))
    conn.commit()
    conn.close()
    return True


def load_favorites() -> List[Dict]:
    _ensure_favorites_table()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT id, created_at, address, display, lat, lon
        FROM favorites ORDER BY created_at DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_favorite(fav_id: int) -> bool:
    _ensure_favorites_table()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM favorites WHERE id = ?", (fav_id,))
    affected = cur.rowcount
    conn.commit()
    conn.close()
    return affected > 0