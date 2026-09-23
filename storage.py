"""
Module lưu trữ dự báo, đánh giá, ghim, bản tin.
"""

import json
import base64
from datetime import datetime
from typing import Dict, List
import pandas as pd

from db import get_connection, execute, fetchall, fetchone, is_postgres


def _ensure_db():
    with get_connection() as conn:
        if is_postgres():
            for sql in [
                """CREATE TABLE IF NOT EXISTS forecasts (
                    id SERIAL PRIMARY KEY, created_at TEXT NOT NULL,
                    location TEXT, lat REAL, lon REAL,
                    model_key TEXT, variable TEXT,
                    horizon_days INTEGER, summary_json TEXT)""",
                """CREATE TABLE IF NOT EXISTS evaluations (
                    id SERIAL PRIMARY KEY, created_at TEXT NOT NULL,
                    location TEXT, lat REAL, lon REAL,
                    model_key TEXT, variable TEXT,
                    ME REAL, MAE REAL, RMSE REAL, Bias REAL,
                    PC REAL, Scf_mean REAL, pct_within_qcvn REAL,
                    n_points INTEGER)""",
                """CREATE TABLE IF NOT EXISTS favorites (
                    id SERIAL PRIMARY KEY, created_at TEXT NOT NULL,
                    address TEXT NOT NULL, display TEXT NOT NULL,
                    lat REAL, lon REAL)""",
            ]:
                execute(conn, sql)
        else:
            for sql in [
                """CREATE TABLE IF NOT EXISTS forecasts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL, location TEXT, lat REAL,
                    lon REAL, model_key TEXT, variable TEXT,
                    horizon_days INTEGER, summary_json TEXT)""",
                """CREATE TABLE IF NOT EXISTS evaluations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL, location TEXT, lat REAL,
                    lon REAL, model_key TEXT, variable TEXT,
                    ME REAL, MAE REAL, RMSE REAL, Bias REAL, PC REAL,
                    Scf_mean REAL, pct_within_qcvn REAL, n_points INTEGER)""",
                """CREATE TABLE IF NOT EXISTS favorites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL, address TEXT NOT NULL,
                    display TEXT NOT NULL, lat REAL, lon REAL)""",
            ]:
                execute(conn, sql)


# ============================================================
# FORECASTS
# ============================================================
def save_forecast(location, lat, lon, model_key, variable,
                  horizon_days, summary):
    _ensure_db()
    with get_connection() as conn:
        execute(conn, """
            INSERT INTO forecasts
            (created_at, location, lat, lon, model_key, variable,
             horizon_days, summary_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (datetime.utcnow().isoformat(), location, lat, lon,
              model_key, variable, horizon_days,
              json.dumps(summary, default=str)))


def load_forecasts(limit: int = 500) -> pd.DataFrame:
    _ensure_db()
    with get_connection() as conn:
        rows = fetchall(conn,
            "SELECT * FROM forecasts ORDER BY created_at DESC LIMIT ?",
            (limit,))
    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ============================================================
# EVALUATIONS
# ============================================================
def save_evaluation(location, lat, lon, model_key, variable, summary):
    _ensure_db()
    with get_connection() as conn:
        execute(conn, """
            INSERT INTO evaluations
            (created_at, location, lat, lon, model_key, variable,
             ME, MAE, RMSE, Bias, PC, Scf_mean, pct_within_qcvn, n_points)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (datetime.utcnow().isoformat(), location, lat, lon,
              model_key, variable,
              summary.get("ME"), summary.get("MAE"), summary.get("RMSE"),
              summary.get("Bias"), summary.get("PC"),
              summary.get("Scf_mean"), summary.get("pct_within_qcvn"),
              summary.get("n_points")))


def load_evaluations(location=None, model_key=None, limit=500) -> pd.DataFrame:
    _ensure_db()
    with get_connection() as conn:
        rows = fetchall(conn,
            "SELECT * FROM evaluations ORDER BY created_at DESC LIMIT ?",
            (limit,))
    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ============================================================
# FAVORITES
# ============================================================
def save_favorite(address: str, display: str, lat: float, lon: float) -> bool:
    _ensure_db()
    with get_connection() as conn:
        if fetchone(conn, "SELECT id FROM favorites WHERE display = ?",
                    (display,)):
            return False
        execute(conn, """
            INSERT INTO favorites (created_at, address, display, lat, lon)
            VALUES (?, ?, ?, ?, ?)
        """, (datetime.utcnow().isoformat(), address, display, lat, lon))
        return True


def load_favorites() -> List[Dict]:
    _ensure_db()
    with get_connection() as conn:
        return fetchall(conn,
            "SELECT id, created_at, address, display, lat, lon "
            "FROM favorites ORDER BY created_at DESC")


def delete_favorite(fav_id: int) -> bool:
    _ensure_db()
    with get_connection() as conn:
        execute(conn, "DELETE FROM favorites WHERE id = ?", (fav_id,))
        return True


# ============================================================
# BẢN TIN (BULLETINS)
# ============================================================
def save_bulletin(category: str, title: str, description: str,
                  filename: str, file_bytes: bytes,
                  uploader: str = "admin") -> int:
    _ensure_db()
    file_b64 = base64.b64encode(file_bytes).decode("ascii")
    file_size = len(file_bytes)

    with get_connection() as conn:
        if is_postgres():
            cur = execute(conn, """
                INSERT INTO bulletins
                (created_at, category, title, description,
                 filename, file_size, file_data, uploader)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
            """, (datetime.utcnow().isoformat(), category, title,
                  description, filename, file_size, file_b64, uploader))
            row = cur.fetchone()
            return row["id"] if row else 0
        else:
            execute(conn, """
                INSERT INTO bulletins
                (created_at, category, title, description,
                 filename, file_size, file_data, uploader)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (datetime.utcnow().isoformat(), category, title,
                  description, filename, file_size, file_b64, uploader))
            cur = execute(conn, "SELECT last_insert_rowid() as id")
            row = cur.fetchone()
            return row["id"] if row else 0


def list_bulletins(category: str = None, limit: int = 50) -> list:
    _ensure_db()
    with get_connection() as conn:
        if category:
            return fetchall(conn, """
                SELECT id, created_at, category, title, description,
                       filename, file_size, uploader
                FROM bulletins WHERE category = ?
                ORDER BY created_at DESC LIMIT ?
            """, (category, limit))
        return fetchall(conn, """
            SELECT id, created_at, category, title, description,
                   filename, file_size, uploader
            FROM bulletins ORDER BY created_at DESC LIMIT ?
        """, (limit,))


def get_bulletin(bulletin_id: int):
    _ensure_db()
    with get_connection() as conn:
        return fetchone(conn, "SELECT * FROM bulletins WHERE id = ?",
                        (bulletin_id,))


def delete_bulletin(bulletin_id: int) -> bool:
    _ensure_db()
    with get_connection() as conn:
        execute(conn, "DELETE FROM bulletins WHERE id = ?", (bulletin_id,))
        return True