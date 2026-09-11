"""
Module xác thực người dùng: đăng ký, đăng nhập, phân quyền.
Sử dụng hashlib.pbkdf2_hmac (có sẵn trong Python).
"""

import hashlib
import os
import sqlite3
from datetime import datetime
from typing import Optional, Dict, List
from config import DB_PATH


# ============================================================
# BẢNG USERS
# ============================================================
def _ensure_users_table():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            email TEXT,
            full_name TEXT,
            role TEXT DEFAULT 'user',
            created_at TEXT NOT NULL,
            last_login TEXT,
            login_count INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1
        )
    """)
    conn.commit()
    conn.close()


# ============================================================
# HASH PASSWORD
# ============================================================
def _hash_password(password: str, salt: str) -> str:
    """Hash password bằng PBKDF2-HMAC-SHA256."""
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    ).hex()


def _generate_salt() -> str:
    return os.urandom(16).hex()


# ============================================================
# ĐĂNG KÝ
# ============================================================
def register_user(
    username: str,
    password: str,
    email: str = "",
    full_name: str = "",
    role: str = "user",
) -> Dict:
    """
    Đăng ký người dùng mới.
    Trả về: {"success": bool, "message": str}
    """
    _ensure_users_table()

    username = username.strip().lower()
    if len(username) < 3:
        return {"success": False, "message": "Tên đăng nhập tối thiểu 3 ký tự."}
    if len(password) < 6:
        return {"success": False, "message": "Mật khẩu tối thiểu 6 ký tự."}

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT id FROM users WHERE username = ?", (username,))
    if cur.fetchone():
        conn.close()
        return {"success": False, "message": "Tên đăng nhập đã tồn tại."}

    salt = _generate_salt()
    pwd_hash = _hash_password(password, salt)

    try:
        cur.execute("""
            INSERT INTO users
            (username, password_hash, salt, email, full_name, role, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            username, pwd_hash, salt, email, full_name, role,
            datetime.utcnow().isoformat(),
        ))
        conn.commit()
        conn.close()
        return {"success": True, "message": "Đăng ký thành công."}
    except Exception as e:
        conn.close()
        return {"success": False, "message": f"Lỗi: {e}"}


# ============================================================
# ĐĂNG NHẬP
# ============================================================
def login_user(username: str, password: str) -> Dict:
    """
    Xác thực đăng nhập.
    Trả về: {"success": bool, "message": str, "user": dict}
    """
    _ensure_users_table()

    username = username.strip().lower()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cur.fetchone()

    if not row:
        conn.close()
        return {"success": False, "message": "Sai tên đăng nhập hoặc mật khẩu."}

    user = dict(row)
    if not user.get("is_active", 1):
        conn.close()
        return {"success": False, "message": "Tài khoản đã bị khóa."}

    pwd_hash = _hash_password(password, user["salt"])
    if pwd_hash != user["password_hash"]:
        conn.close()
        return {"success": False, "message": "Sai tên đăng nhập hoặc mật khẩu."}

    # Cập nhật last_login + tăng login_count
    cur.execute("""
        UPDATE users
        SET last_login = ?, login_count = login_count + 1
        WHERE id = ?
    """, (datetime.utcnow().isoformat(), user["id"]))
    conn.commit()
    conn.close()

    user.pop("password_hash", None)
    user.pop("salt", None)
    return {"success": True, "message": "Đăng nhập thành công.", "user": user}


# ============================================================
# ĐỔI MẬT KHẨU
# ============================================================
def change_password(user_id: int, old_password: str, new_password: str) -> Dict:
    _ensure_users_table()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return {"success": False, "message": "Không tìm thấy user."}

    user = dict(row)
    if _hash_password(old_password, user["salt"]) != user["password_hash"]:
        conn.close()
        return {"success": False, "message": "Mật khẩu cũ không đúng."}

    if len(new_password) < 6:
        conn.close()
        return {"success": False, "message": "Mật khẩu mới tối thiểu 6 ký tự."}

    new_salt = _generate_salt()
    new_hash = _hash_password(new_password, new_salt)

    cur.execute("""
        UPDATE users SET password_hash = ?, salt = ? WHERE id = ?
    """, (new_hash, new_salt, user_id))
    conn.commit()
    conn.close()
    return {"success": True, "message": "Đổi mật khẩu thành công."}


# ============================================================
# QUẢN LÝ USER
# ============================================================
def list_users() -> List[Dict]:
    _ensure_users_table()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT id, username, email, full_name, role,
               created_at, last_login, login_count, is_active
        FROM users ORDER BY created_at DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def set_user_active(user_id: int, active: bool) -> bool:
    _ensure_users_table()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE users SET is_active = ? WHERE id = ?",
                (1 if active else 0, user_id))
    affected = cur.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def delete_user(user_id: int) -> bool:
    _ensure_users_table()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
    affected = cur.rowcount
    conn.commit()
    conn.close()
    return affected > 0


# ============================================================
# KHỞI TẠO ADMIN MẶC ĐỊNH
# ============================================================
def ensure_admin_exists():
    """Tạo tài khoản admin mặc định nếu chưa có user nào."""
    _ensure_users_table()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    count = cur.fetchone()[0]
    conn.close()

    if count == 0:
        result = register_user(
            username="admin",
            password="admin123",
            email="admin@kttvcantho.gov.vn",
            full_name="Quản trị viên",
            role="admin",
        )
        print(f"[AUTH] Tạo admin mặc định: {result['message']}")
        return result
    return {"success": True, "message": "Đã có user."}