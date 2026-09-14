"""
Module xác thực người dùng — hỗ trợ Supabase/SQLite.
"""

import hashlib
import os
from datetime import datetime
from typing import Dict, List

from db import get_connection, execute, fetchall, fetchone, is_postgres


def _ensure_users_table():
    with get_connection() as conn:
        if is_postgres():
            execute(conn, """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    password_plain TEXT,
                    salt TEXT NOT NULL,
                    email TEXT, full_name TEXT,
                    role TEXT DEFAULT 'user',
                    created_at TEXT NOT NULL, last_login TEXT,
                    login_count INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1)
            """)
            for col, typ in [("password_plain", "TEXT"),
                             ("login_count", "INTEGER DEFAULT 0"),
                             ("is_active", "INTEGER DEFAULT 1")]:
                try:
                    execute(conn, f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} {typ}")
                except Exception:
                    pass
        else:
            execute(conn, """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    password_plain TEXT,
                    salt TEXT NOT NULL,
                    email TEXT, full_name TEXT,
                    role TEXT DEFAULT 'user',
                    created_at TEXT NOT NULL, last_login TEXT,
                    login_count INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1)
            """)


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"),
        salt.encode("utf-8"), 100_000).hex()


def _generate_salt() -> str:
    return os.urandom(16).hex()


def register_user(username: str, password: str, email: str = "",
                  full_name: str = "", role: str = "user") -> Dict:
    _ensure_users_table()
    username = username.strip().lower()
    if len(username) < 3:
        return {"success": False, "message": "Tên đăng nhập tối thiểu 3 ký tự."}
    if len(password) < 6:
        return {"success": False, "message": "Mật khẩu tối thiểu 6 ký tự."}

    with get_connection() as conn:
        if fetchone(conn, "SELECT id FROM users WHERE username = ?", (username,)):
            return {"success": False, "message": "Tên đăng nhập đã tồn tại."}

        salt = _generate_salt()
        pwd_hash = _hash_password(password, salt)
        try:
            execute(conn, """
                INSERT INTO users
                (username, password_hash, password_plain, salt,
                 email, full_name, role, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (username, pwd_hash, password, salt, email, full_name,
                  role, datetime.utcnow().isoformat()))
            return {"success": True, "message": "Đăng ký thành công."}
        except Exception as e:
            return {"success": False, "message": f"Lỗi: {e}"}


def login_user(username: str, password: str) -> Dict:
    _ensure_users_table()
    username = username.strip().lower()
    with get_connection() as conn:
        user = fetchone(conn, "SELECT * FROM users WHERE username = ?", (username,))
        if not user:
            return {"success": False, "message": "Sai tên đăng nhập hoặc mật khẩu."}
        if not user.get("is_active", 1):
            return {"success": False, "message": "Tài khoản đã bị khóa."}
        if _hash_password(password, user["salt"]) != user["password_hash"]:
            return {"success": False, "message": "Sai tên đăng nhập hoặc mật khẩu."}

        execute(conn, """
            UPDATE users SET last_login = ?, login_count = login_count + 1
            WHERE id = ?
        """, (datetime.utcnow().isoformat(), user["id"]))

        user.pop("password_hash", None)
        user.pop("salt", None)
        return {"success": True, "message": "Đăng nhập thành công.", "user": user}


def change_password(user_id: int, old_password: str, new_password: str) -> Dict:
    _ensure_users_table()
    with get_connection() as conn:
        user = fetchone(conn, "SELECT * FROM users WHERE id = ?", (user_id,))
        if not user:
            return {"success": False, "message": "Không tìm thấy user."}
        if _hash_password(old_password, user["salt"]) != user["password_hash"]:
            return {"success": False, "message": "Mật khẩu cũ không đúng."}
        if len(new_password) < 6:
            return {"success": False, "message": "Mật khẩu mới tối thiểu 6 ký tự."}

        new_salt = _generate_salt()
        new_hash = _hash_password(new_password, new_salt)
        execute(conn, """
            UPDATE users SET password_hash = ?, password_plain = ?, salt = ?
            WHERE id = ?
        """, (new_hash, new_password, new_salt, user_id))
        return {"success": True, "message": "Đổi mật khẩu thành công."}


def admin_reset_password(user_id: int, new_password: str) -> Dict:
    _ensure_users_table()
    if len(new_password) < 6:
        return {"success": False, "message": "Mật khẩu tối thiểu 6 ký tự."}
    with get_connection() as conn:
        new_salt = _generate_salt()
        new_hash = _hash_password(new_password, new_salt)
        execute(conn, """
            UPDATE users SET password_hash = ?, password_plain = ?, salt = ?
            WHERE id = ?
        """, (new_hash, new_password, new_salt, user_id))
        return {"success": True, "message": "Đã đặt lại mật khẩu."}


def list_users() -> List[Dict]:
    _ensure_users_table()
    with get_connection() as conn:
        return fetchall(conn, """
            SELECT id, username, password_plain, email, full_name, role,
                   created_at, last_login, login_count, is_active
            FROM users ORDER BY created_at DESC
        """)


def set_user_active(user_id: int, active: bool) -> bool:
    _ensure_users_table()
    with get_connection() as conn:
        execute(conn, "UPDATE users SET is_active = ? WHERE id = ?",
                (1 if active else 0, user_id))
    return True


def delete_user(user_id: int) -> bool:
    _ensure_users_table()
    with get_connection() as conn:
        execute(conn, "DELETE FROM users WHERE id = ?", (user_id,))
    return True


def ensure_admin_exists():
    _ensure_users_table()
    with get_connection() as conn:
        row = fetchone(conn, "SELECT COUNT(*) as cnt FROM users")
        count = row["cnt"] if row else 0

    if count == 0:
        r = register_user(
            username="admin", password="admin123",
            email="admin@kttvcantho.gov.vn",
            full_name="Quản trị viên", role="admin")
        print(f"[AUTH] Tạo admin: {r['message']}")
        return r
    return {"success": True, "message": "Đã có user."}