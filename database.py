"""
Database module for Lead Management System.
SQLite backend with users, leads, and lead_notes tables.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager
from typing import Optional, List, Dict, Tuple

DB_PATH = Path(__file__).parent / "lead_management.db"


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create tables if they do not exist."""
    with get_connection() as conn:
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin', 'sales')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                created_date TIMESTAMP NOT NULL,
                assigned_to INTEGER REFERENCES users(id),
                status TEXT NOT NULL DEFAULT 'new'
                    CHECK(status IN ('new', 'active')),
                imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                source_file TEXT,
                UNIQUE(phone, created_date)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS lead_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id),
                note_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("CREATE INDEX IF NOT EXISTS idx_leads_assigned ON leads(assigned_to)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_leads_created_date ON leads(created_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_lead_notes_lead ON lead_notes(lead_id)")

        # CRM v2: add call_status (Vietnamese from Excel) and assigned_at if missing
        for col, sql in [
            ("call_status", "ALTER TABLE leads ADD COLUMN call_status TEXT"),
            ("assigned_at", "ALTER TABLE leads ADD COLUMN assigned_at TIMESTAMP"),
        ]:
            try:
                cur.execute(sql)
            except sqlite3.OperationalError:
                pass  # column already exists

        # Sessions: one session_id per tab/URL for multiple concurrent logins
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")


# ---------------- SESSIONS (multi-account via session_id in URL) ----------------

def create_session(session_id: str, user_id: int) -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO sessions (session_id, user_id) VALUES (?, ?)", (session_id, user_id))


def get_user_by_session(session_id: str) -> Optional[Dict]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM sessions WHERE session_id = ?", (session_id,))
        row = cur.fetchone()
        if not row:
            return None
        return get_user_by_id(row["user_id"])


def delete_session(session_id: str) -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))


# ---------------- USERS ----------------

def create_user(email: str, password_hash: str, name: str, role: str) -> int:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (email, password_hash, name, role) VALUES (?, ?, ?, ?)",
            (email, password_hash, name, role)
        )
        return cur.lastrowid


def get_user_by_email(email: str) -> Optional[Dict]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[Dict]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def list_users(role: Optional[str] = None) -> List[Dict]:
    with get_connection() as conn:
        cur = conn.cursor()
        if role:
            cur.execute("SELECT * FROM users WHERE role = ? ORDER BY name", (role,))
        else:
            cur.execute("SELECT * FROM users ORDER BY name")
        return [dict(r) for r in cur.fetchall()]


def update_user(
    user_id: int,
    name: Optional[str] = None,
    role: Optional[str] = None,
    password_hash: Optional[str] = None
):
    with get_connection() as conn:
        cur = conn.cursor()

        if password_hash:
            cur.execute(
                "UPDATE users SET name=COALESCE(?,name), role=COALESCE(?,role), password_hash=? WHERE id=?",
                (name, role, password_hash, user_id)
            )
        else:
            cur.execute(
                "UPDATE users SET name=COALESCE(?,name), role=COALESCE(?,role) WHERE id=?",
                (name, role, user_id)
            )


def delete_user(user_id: int):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE id = ?", (user_id,))


# ---------------- LEADS ----------------

def insert_lead(
    name: str,
    phone: str,
    created_date: datetime,
    source_file: Optional[str] = None
) -> Optional[int]:

    with get_connection() as conn:
        cur = conn.cursor()

        created_str = (
            created_date.strftime("%Y-%m-%d %H:%M:%S")
            if isinstance(created_date, datetime)
            else created_date
        )

        cur.execute(
            "INSERT OR IGNORE INTO leads (name, phone, created_date, source_file) VALUES (?, ?, ?, ?)",
            (name, phone, created_str, source_file)
        )

        return cur.lastrowid if cur.lastrowid else None


def insert_leads_batch(
    rows: List[Tuple],
    source_file: Optional[str] = None
) -> int:
    """Insert or update leads. Each row: (name, phone, created_date) or (name, phone, created_date, status)
    or (name, phone, created_date, status, call_status). call_status stored in Vietnamese."""
    count = 0

    with get_connection() as conn:
        cur = conn.cursor()

        for row in rows:
            if len(row) >= 5:
                name, phone, created_date, status, call_status = row[0], row[1], row[2], row[3], row[4]
            elif len(row) >= 4:
                name, phone, created_date, status = row[0], row[1], row[2], row[3]
                call_status = ""
            else:
                name, phone, created_date = row[0], row[1], row[2]
                status = "new"
                call_status = ""

            created_str = (
                created_date.strftime("%Y-%m-%d %H:%M:%S")
                if isinstance(created_date, datetime)
                else created_date
            )
            if status not in ("new", "active"):
                status = "new"
            call_status = (call_status or "").strip() if call_status is not None else ""

            cur.execute(
                """INSERT INTO leads (name, phone, created_date, source_file, status, call_status)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(phone, created_date) DO UPDATE SET
                     name = excluded.name,
                     status = excluded.status,
                     source_file = excluded.source_file,
                     call_status = excluded.call_status""",
                (name, phone, created_str, source_file, status, call_status)
            )
            count += 1

    return count


def get_leads(
    assigned_to: Optional[int] = None,
    status: Optional[str] = None,
    phone_search: Optional[str] = None
) -> List[Dict]:

    with get_connection() as conn:

        cur = conn.cursor()

        sql = """
        SELECT l.*, u.name AS assigned_name
        FROM leads l
        LEFT JOIN users u ON l.assigned_to = u.id
        WHERE 1=1
        """

        params = []

        if assigned_to is not None:
            sql += " AND l.assigned_to=?"
            params.append(assigned_to)

        if status:
            sql += " AND l.status=?"
            params.append(status)

        if phone_search:
            sql += " AND l.phone LIKE ?"
            params.append(f"%{phone_search}%")

        sql += " ORDER BY l.created_date DESC"

        cur.execute(sql, params)

        return [dict(r) for r in cur.fetchall()]


def assign_lead(lead_id: int, user_id: int):
    """Assign lead to sales consultant; set assigned_at timestamp."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE leads SET assigned_to=?, assigned_at=CURRENT_TIMESTAMP WHERE id=?",
            (user_id, lead_id)
        )


def set_lead_status(lead_id: int, status: str):

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE leads SET status=? WHERE id=?", (status, lead_id))


def add_lead_note(lead_id: int, user_id: int, note_text: str):

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO lead_notes (lead_id,user_id,note_text) VALUES (?,?,?)",
            (lead_id, user_id, note_text)
        )


def get_lead_notes(lead_id: int) -> List[Dict]:

    with get_connection() as conn:

        cur = conn.cursor()

        cur.execute("""
        SELECT n.*, u.name AS user_name
        FROM lead_notes n
        JOIN users u ON n.user_id=u.id
        WHERE n.lead_id=?
        ORDER BY n.created_at DESC
        """, (lead_id,))

        return [dict(r) for r in cur.fetchall()]


def get_lead_by_id(lead_id: int) -> Optional[Dict]:

    with get_connection() as conn:

        cur = conn.cursor()

        cur.execute("""
        SELECT l.*, u.name AS assigned_name
        FROM leads l
        LEFT JOIN users u ON l.assigned_to=u.id
        WHERE l.id=?
        """, (lead_id,))

        row = cur.fetchone()

        return dict(row) if row else None


# ---------------- DASHBOARD ----------------

def count_leads_total() -> int:

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM leads")
        return cur.fetchone()[0]


def count_leads_today() -> int:

    with get_connection() as conn:
        cur = conn.cursor()

        cur.execute("""
        SELECT COUNT(*)
        FROM leads
        WHERE date(created_date)=date('now','localtime')
        """)

        return cur.fetchone()[0]


def count_leads_overdue() -> int:

    with get_connection() as conn:
        cur = conn.cursor()

        cur.execute("""
        SELECT COUNT(*)
        FROM leads
        WHERE status!='active'
        AND (julianday('now','localtime') - julianday(created_date))*24 > 16
        """)

        return cur.fetchone()[0]


def count_leads_active() -> int:

    with get_connection() as conn:
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM leads WHERE status='active'")

        return cur.fetchone()[0]


def get_leads_for_export() -> List[Dict]:

    with get_connection() as conn:

        cur = conn.cursor()

        cur.execute("""
        SELECT l.id,l.name,l.phone,l.created_date,l.status,l.assigned_to,
               u.name AS assigned_name
        FROM leads l
        LEFT JOIN users u ON l.assigned_to=u.id
        ORDER BY l.created_date DESC
        """)

        return [dict(r) for r in cur.fetchall()]