"""
Authentication utilities: password hashing, login, and registration with role-based codes.
Registration codes are loaded from environment variables (not stored in source code).
"""

import os
import bcrypt
import database as db
from typing import Optional, Dict, Tuple


def _get_registration_code(role: str) -> str:
    """Get registration code for role from environment. Codes must not be in source code."""
    if role == "admin":
        return (os.environ.get("ADMIN_REGISTRATION_CODE") or "").strip()
    if role == "sales":
        return (os.environ.get("SALES_REGISTRATION_CODE") or "").strip()
    return ""


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def authenticate(email: str, password: str) -> Optional[Dict]:
    user = db.get_user_by_email(email)

    if not user:
        return None

    if not verify_password(password, user["password_hash"]):
        return None

    return user


def register(name: str, email: str, password: str, role: str, registration_code: str) -> Tuple[bool, str]:
    """
    Register a new user. Validates registration code for the selected role (from env vars).
    Returns (success, error_message). On success error_message is empty.
    Error messages are in Vietnamese for UI display.
    """
    if not name or not email or not password or not role or not registration_code:
        return False, "Vui lòng điền đủ các trường."

    role = role.strip().lower()
    if role not in ("admin", "sales"):
        return False, "Vai trò không hợp lệ."

    expected_code = _get_registration_code(role)
    if not expected_code or registration_code.strip() != expected_code:
        return False, "Đăng ký thất bại: mã đăng ký không đúng."

    if db.get_user_by_email(email.strip()):
        return False, "Email đã được đăng ký."

    db.create_user(
        email=email.strip(),
        password_hash=hash_password(password),
        name=name.strip(),
        role=role,
    )
    return True, ""


def ensure_admin_user():
    """Create default admin if no users exist (email: adminFPT@gmail.com, password: adminFPT2026)."""

    if db.get_user_by_email("adminFPT@gmail.com") is None:
        db.create_user(
            email="adminFPT@gmail.com",
            password_hash=hash_password("adminFPT2026"),
            name="Administrator",
            role="admin",
        )