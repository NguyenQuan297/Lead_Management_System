"""
Authentication utilities: password hashing, login, and registration with role-based codes.
Registration codes are loaded from environment variables (not stored in source code).
"""

import os
from pathlib import Path

import bcrypt
import database as db
import streamlit as st
from typing import Optional, Dict, Tuple


def _get_config_value(key: str, default: str = "") -> str:
    """
    Read config values from Streamlit Secrets first, then fall back to env vars.
    Works on Streamlit Cloud where secrets may not populate os.environ.
    """
    # 1) Prefer environment variables (works on some deploy setups)
    v = os.environ.get(key)
    if v is not None:
        return (v or "").strip()

    # 2) Fallback to Streamlit Secrets only if a secrets.toml actually exists.
    # On local dev, accessing st.secrets without secrets.toml can show:
    # "Secrets file not found..." and break the page rendering.
    try:
        secrets_toml = Path(__file__).resolve().parent / ".streamlit" / "secrets.toml"
        if secrets_toml.exists() and hasattr(st, "secrets") and key in st.secrets:
            v2 = st.secrets.get(key)
            return (v2 or "").strip()
    except Exception:
        pass

    return (default or "").strip()


def _get_registration_code(role: str) -> str:
    """Get registration code for role from environment. Codes must not be in source code."""
    if role == "admin":
        return _get_config_value("ADMIN_REGISTRATION_CODE")
    if role == "sales":
        return _get_config_value("SALES_REGISTRATION_CODE")
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
    registration_code = registration_code.strip()
    if not expected_code:
        # Expected code is missing on the server (e.g. Streamlit Secrets not configured).
        return False, "Đăng ký thất bại: hệ thống chưa cấu hình mã đăng ký cho vai trò này trên server."
    if registration_code != expected_code:
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
    """Create default admin if no users exist (credentials from environment variables)."""

    admin_email = _get_config_value("DEFAULT_ADMIN_EMAIL")
    admin_password = _get_config_value("DEFAULT_ADMIN_PASSWORD")

    if not admin_email or not admin_password:
        return

    if db.get_user_by_email(admin_email) is None:
        db.create_user(
            email=admin_email,
            password_hash=hash_password(admin_password),
            name="Administrator",
            role="admin",
        )