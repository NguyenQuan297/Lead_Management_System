"""
Lead Management System - Main entry point.
Session: session_id in URL (one per tab) for multiple concurrent logins (e.g. Admin + Sales).
"""
import base64
import io
import json
import os
import sys
import uuid
import streamlit as st
from datetime import datetime, timedelta
from pathlib import Path

# Logo path (absolute); process to remove white background and resize for display
_LOGO_PATH = (Path(__file__).resolve().parent / "assets" / "fpt_education_logo.png")
_LOGO_BYTES = None
_LOGO_BYTES_SMALL = None  # smaller, no white background, for sidebar
_LOGO_FAVICON_BYTES = None  # tiny for header/favicon (replaces Streamlit crown)
_page_icon = "📋"
if _LOGO_PATH.exists():
    try:
        from PIL import Image
        resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
        with open(_LOGO_PATH, "rb") as f:
            img = Image.open(f).convert("RGBA")
        w, h = img.size
        data = img.getdata()
        # Make white and near-white pixels transparent (keep colored text)
        threshold = 248
        new_data = []
        for item in data:
            r, g, b, a = item
            if r >= threshold and g >= threshold and b >= threshold:
                new_data.append((255, 255, 255, 0))
            else:
                new_data.append(item)
        img.putdata(new_data)
        # Full size for login page (max width 280)
        w_full = min(w, 280)
        h_full = int(h * w_full / w)
        img_full = img.resize((w_full, h_full), resample)
        buf = io.BytesIO()
        img_full.save(buf, format="PNG")
        buf.seek(0)
        _LOGO_BYTES = buf.getvalue()
        # Small for sidebar (max width 140)
        w_small = min(w, 140)
        h_small = int(h * w_small / w)
        img_small = img.resize((w_small, h_small), resample)
        buf_s = io.BytesIO()
        img_small.save(buf_s, format="PNG")
        buf_s.seek(0)
        _LOGO_BYTES_SMALL = buf_s.getvalue()
        # Header/favicon: high resolution so FPT stays sharp when displayed small
        size_fav = 96
        w_fav = min(w, size_fav)
        h_fav = int(h * w_fav / w) if w > 0 else size_fav
        img_fav = img.resize((w_fav, h_fav), resample)
        buf_fav = io.BytesIO()
        img_fav.save(buf_fav, format="PNG")
        buf_fav.seek(0)
        _LOGO_FAVICON_BYTES = buf_fav.getvalue()
        _page_icon = "data:image/png;base64," + base64.b64encode(_LOGO_FAVICON_BYTES).decode("utf-8")
    except Exception:
        try:
            with open(_LOGO_PATH, "rb") as f:
                _LOGO_BYTES = f.read()
            _LOGO_BYTES_SMALL = _LOGO_BYTES
            _LOGO_FAVICON_BYTES = _LOGO_BYTES
            _page_icon = "data:image/png;base64," + base64.b64encode(_LOGO_BYTES).decode("utf-8")
        except Exception:
            pass

# Required: set_page_config() must be the first Streamlit call in the file
st.set_page_config(page_title="Hệ thống Quản lý Lead", page_icon=_page_icon, layout="wide")

# CSS: uniform sidebar buttons, consistent main content spacing
st.markdown("""
<style>
    /* Sidebar: full-width buttons, same size */
    [data-testid="stSidebar"] .stButton > button {
        width: 100%%;
        min-height: 2.75rem;
        padding: 0.5rem 1rem;
        font-size: 0.95rem;
        border-radius: 8px;
        justify-content: center;
    }
    [data-testid="stSidebar"] .stButton { width: 100%%; }
    [data-testid="stSidebar"] h1 { font-size: 1.35rem; margin-bottom: 0.5rem; }
    [data-testid="stSidebar"] .stMarkdown { margin-bottom: 0.25rem; }
    [data-testid="stSidebar"] hr { margin: 1rem 0; }
    /* Sidebar logo: small, at top corner */
    [data-testid="stSidebar"] .stImage:first-child { margin-top: 0; margin-bottom: 0.25rem; }
    [data-testid="stSidebar"] .stImage:first-child img { max-width: 140px; }
    /* Main: consistent spacing */
    .main .block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1100px; }
    h1 { font-size: 1.75rem; margin-bottom: 0.5rem; }
    h2 { font-size: 1.25rem; margin-top: 1rem; margin-bottom: 0.5rem; }
</style>
""", unsafe_allow_html=True)

# Load environment variables (e.g. .env); registration codes must not be in source code
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Rerun compatibility for older Streamlit
if not hasattr(st, "rerun"):
    st.rerun = st.experimental_rerun

import database as db
import auth_utils as auth

# Cookie: store user_id for restore after reload (must init after set_page_config)
try:
    from streamlit_cookies_manager import EncryptedCookieManager
    _COOKIES = EncryptedCookieManager(
        prefix="leadmgmt/",
        password=os.environ.get("COOKIES_PASSWORD", "leadmgmt-session-secret"),
    )
    _USE_COOKIES = True
except Exception:
    _COOKIES = None
    _USE_COOKIES = False

COOKIE_USER_ID = "user_id"
QUERY_PARAM_SESSION = "session_id"


def _get_session_id_from_url():
    """Get session_id from URL query params. Supports st.query_params and experimental_get_query_params."""
    if hasattr(st, "query_params"):
        v = st.query_params.get(QUERY_PARAM_SESSION)
        if isinstance(v, list):
            v = v[0] if v else None
        return v
    if hasattr(st, "experimental_get_query_params"):
        q = st.experimental_get_query_params()
        v = q.get(QUERY_PARAM_SESSION, [])
        return (v[0] if v else None)
    return None


def _restore_session():
    """Restore user only from session_id in URL. No session_id in URL shows login screen."""
    if st.session_state.user is not None:
        return
    if st.session_state.get("_just_logged_out"):
        st.session_state._just_logged_out = False
        return
    # Restore only when URL has session_id; base URL in new tab shows login
    session_id = _get_session_id_from_url()
    if session_id:
        user = db.get_user_by_session(session_id)
        if user:
            st.session_state.user = dict(user)

# File for shared leads so all sessions (Admin + Sales) and processes read/write the same data
_SHARED_LEADS_FILE = Path(__file__).parent / ".shared_leads.json"


def _load_shared_leads():
    """Load leads from file (Admin assign visible to Sales on reload)."""
    if not _SHARED_LEADS_FILE.exists():
        return []
    try:
        with open(_SHARED_LEADS_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return []
    out = []
    for r in raw:
        try:
            if r.get("created_date"):
                r["created_date"] = datetime.fromisoformat(r["created_date"].replace("Z", "+00:00"))
            else:
                r["created_date"] = datetime.now()
            if r.get("assigned_at"):
                r["assigned_at"] = datetime.fromisoformat(r["assigned_at"].replace("Z", "+00:00"))
            out.append(r)
        except Exception:
            continue
    return out


def _save_shared_leads():
    """Persist _shared_leads to file after each change (upload, assign, mark active, note)."""
    try:
        copy = []
        for t in _shared_leads:
            c = dict(t)
            if isinstance(c.get("created_date"), datetime):
                c["created_date"] = c["created_date"].isoformat()
            if isinstance(c.get("assigned_at"), datetime):
                c["assigned_at"] = c["assigned_at"].isoformat()
            elif c.get("assigned_at") is None:
                c["assigned_at"] = None
            copy.append(c)
        with open(_SHARED_LEADS_FILE, "w", encoding="utf-8") as f:
            json.dump(copy, f, ensure_ascii=False, indent=0)
    except Exception:
        pass


# Shared lead storage: load from file each run so Admin/Sales/other processes see same data
_mod = sys.modules[__name__]
if not hasattr(_mod, "_shared_leads"):
    _mod._shared_leads = []
_shared_leads = _mod._shared_leads
# Sync from file so assignments from Admin are visible to Sales on reload
_shared_leads.clear()
_shared_leads.extend(_load_shared_leads())

# Initialize database and default admin
db.init_db()
auth.ensure_admin_user()

# Session state (per-user: auth and UI only)
if "user" not in st.session_state:
    st.session_state.user = None
if "page" not in st.session_state:
    st.session_state.page = "Dashboard"
if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "login"

# Cookie not ready on first load: rerun once so component can send cookie
if _USE_COOKIES and _COOKIES is not None and not _COOKIES.ready():
    if not st.session_state.get("_cookie_init_rerun"):
        st.session_state._cookie_init_rerun = True
        st.rerun()
else:
    if _USE_COOKIES:
        st.session_state._cookie_init_rerun = False
# Restore user from URL session_id (multi-tab) or cookie
_restore_session()


def _set_session_in_url(session_id: str):
    """Set session_id in URL so this tab has its own session."""
    if hasattr(st, "query_params"):
        st.query_params[QUERY_PARAM_SESSION] = session_id
        return
    if hasattr(st, "experimental_set_query_params"):
        st.experimental_set_query_params(**{QUERY_PARAM_SESSION: session_id})


def _clear_session_from_url():
    """Remove session_id from URL (after logout)."""
    if hasattr(st, "query_params"):
        params = dict(st.query_params)
        params.pop(QUERY_PARAM_SESSION, None)
        if params:
            st.query_params.from_dict(params)
        else:
            st.query_params.clear()
        return
    if hasattr(st, "experimental_set_query_params"):
        st.experimental_set_query_params()


def logout():
    current_user = st.session_state.user
    session_id = _get_session_id_from_url()
    if session_id:
        db.delete_session(session_id)
        _clear_session_from_url()
    st.session_state.user = None
    st.session_state.page = "Dashboard"
    if _USE_COOKIES and _COOKIES is not None and _COOKIES.ready():
        try:
            del _COOKIES[COOKIE_USER_ID]
            _COOKIES.save()
        except Exception:
            pass
    # Admin logout: clear all data; list empty on next login until upload
    if current_user and current_user.get("role") == "admin":
        _shared_leads.clear()
        _save_shared_leads()
    st.session_state._just_logged_out = True


def login_page():
    if _LOGO_BYTES:
        st.image(_LOGO_BYTES, use_column_width=True)
    st.title("Hệ thống Quản lý Lead")
    st.markdown("---")
    tab_login, tab_register = st.tabs(["Đăng nhập", "Đăng ký"])
    with tab_login:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.form("login_form"):
                email = st.text_input("Email", placeholder="email@vd.com")
                password = st.text_input("Mật khẩu", type="password", placeholder="••••••••")
                submitted = st.form_submit_button("Đăng nhập")
                if submitted:
                    if not email or not password:
                        st.error("Vui lòng nhập email và mật khẩu.")
                    else:
                        user = auth.authenticate(email, password)
                        if user:
                            if user.get("role") == "admin":
                                _shared_leads.clear()
                                _save_shared_leads()
                            st.session_state.user = user
                            sid = uuid.uuid4().hex
                            db.create_session(sid, user["id"])
                            _set_session_in_url(sid)
                            if _USE_COOKIES and _COOKIES is not None and _COOKIES.ready():
                                try:
                                    _COOKIES[COOKIE_USER_ID] = str(user["id"])
                                    _COOKIES.save()
                                except Exception:
                                    pass
                            st.rerun()
                        else:
                            st.error("Email hoặc mật khẩu không đúng.")
    with tab_register:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.form("register_form"):
                name = st.text_input("Họ tên", placeholder="Họ và tên đầy đủ")
                email_r = st.text_input("Email", placeholder="email@vd.com", key="reg_email")
                password_r = st.text_input("Mật khẩu", type="password", placeholder="••••••••", key="reg_password")
                role = st.selectbox("Vai trò", ["Admin", "Sales"], index=1)
                registration_code = st.text_input(
                    "Mã đăng ký",
                    type="password",
                    placeholder="Nhập mã theo vai trò",
                    help="Lấy mã từ quản trị viên (Admin hoặc Sales).",
                )
                submitted = st.form_submit_button("Đăng ký")
                if submitted:
                    ok, err = auth.register(
                        name, email_r, password_r, role.lower(), registration_code
                    )
                    if ok:
                        st.success("Tạo tài khoản thành công. Bạn có thể đăng nhập.")
                    else:
                        st.error(err or "Đăng ký thất bại.")


# Optional column name mappings (Vietnamese / other formats → standard)
# Required: name, phone, created_date. Optional: call_status, source, person_in_charge, notes.
COLUMN_MAPPING = {
    "name": ["name", "Tên Học Sinh", "Họ và tên phụ huynh", "Tên", "Họ tên", "Name"],
    "phone": ["phone", "Điện thoại phụ huynh", "Điện thoại", "Phone", "Số điện thoại"],
    "created_date": ["created_date", "Ngày tạo", "created", "Created Date", "Ngày"],
    "call_status": ["Tình trạng gọi điện", "status", "Status", "Call status", "Tình trạng"],
    "source": ["Nguồn khách hàng", "source", "Source", "Nguồn"],
    "person_in_charge": ["Người phụ trách", "person_in_charge", "Người phụ trách"],
    "notes": ["Ghi chú", "notes", "Notes", "Ghi chú"],
}

# Map Excel "Tình trạng gọi điện" (call status) to system lead status. Call status stays in Vietnamese in UI.
CALL_STATUS_TO_LEAD_STATUS = {
    "chưa liên hệ": "new",
    "chưa nghe máy lần 1": "new",
    "chưa nghe máy lần 2": "new",
    "chưa nghe máy": "new",
    "đã nghe máy": "active",
    "đăng ký lại": "active",
    "đã liên hệ": "active",
    "đã xử lý": "active",
}


def _find_column(df_columns, candidates):
    """Return first column in df that matches any of the candidate names (strip and case-insensitive)."""
    cols = [str(c).strip() for c in df_columns]
    for cand in candidates:
        for c in cols:
            if c and cand and c.lower() == cand.lower():
                return c
    return None


def _parse_created_date(value):
    """Parse created_date from various formats (Excel datetime, DD/MM/YYYY, YYYY-MM-DD, etc.)."""
    if value is None or (isinstance(value, float) and value != value):  # NaN
        return None
    if hasattr(value, "to_pydatetime"):
        return value.to_pydatetime()
    if isinstance(value, datetime):
        return value
    s = str(value).strip()
    if not s:
        return None
    # DD/MM/YYYY or DD/MM/YYYY HH:MM
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:19].strip() if len(s) > 19 else s, fmt)
        except ValueError:
            continue
    return None


def _normalize_status_key(s: str) -> str:
    """Normalize for status lookup: strip, lower, collapse spaces, optional unicode normalize."""
    if not s:
        return ""
    s = str(s).strip().lower()
    while "  " in s:
        s = s.replace("  ", " ")
    return s


def _excel_call_status_to_lead_status(value) -> str:
    """Map Excel 'Tình trạng gọi điện' value to system status 'new' or 'active'."""
    if value is None or (isinstance(value, float) and value != value):
        return "new"
    key = _normalize_status_key(str(value))
    if not key:
        return "new"
    # Exact match first
    if key in CALL_STATUS_TO_LEAD_STATUS:
        return CALL_STATUS_TO_LEAD_STATUS[key]
    # Partial: treat as active if text suggests contacted/answered
    if "đã nghe" in key or "nghe máy" in key or "đăng ký lại" in key or "đã liên hệ" in key or "đã xử lý" in key:
        return "active"
    return "new"


def _safe_str(v, default=""):
    """Get string from Excel cell; empty if NaN/None."""
    import pandas as pd
    if v is None or (isinstance(v, float) and (v != v or pd.isna(v))):
        return default
    return str(v).strip() or default


def _normalize_upload_df(df):
    """Map columns to system fields. Returns list of tuples (name, phone, created_date, status, call_status_raw, source, person_in_charge, notes_from_file)."""
    import pandas as pd
    cols = list(df.columns)
    name_col = _find_column(cols, COLUMN_MAPPING["name"])
    phone_col = _find_column(cols, COLUMN_MAPPING["phone"])
    date_col = _find_column(cols, COLUMN_MAPPING["created_date"])
    call_status_col = _find_column(cols, COLUMN_MAPPING["call_status"])
    source_col = _find_column(cols, COLUMN_MAPPING["source"])
    person_col = _find_column(cols, COLUMN_MAPPING["person_in_charge"])
    notes_col = _find_column(cols, COLUMN_MAPPING["notes"])
    if not name_col or not phone_col or not date_col:
        return None, (name_col, phone_col, date_col, call_status_col)
    rows = []
    for _, r in df.iterrows():
        try:
            name_str = _safe_str(r.get(name_col)) or "—"
            phone_val = r.get(phone_col)
            phone_str = (str(int(phone_val)) if isinstance(phone_val, (int, float)) and not (isinstance(phone_val, float) and (phone_val != phone_val)) else _safe_str(phone_val)).strip()
            if not phone_str:
                continue
            cd = _parse_created_date(r.get(date_col))
            if cd is None:
                cd = datetime.now()
            raw_call = r.get(call_status_col)
            status = _excel_call_status_to_lead_status(raw_call) if call_status_col else "new"
            call_status_raw = _safe_str(raw_call) if call_status_col else ""
            source = _safe_str(r.get(source_col)) if source_col else ""
            person_in_charge = _safe_str(r.get(person_col)) if person_col else ""
            notes_from_file = _safe_str(r.get(notes_col)) if notes_col else ""
            rows.append((name_str, phone_str, cd, status, call_status_raw, source, person_in_charge, notes_from_file))
        except Exception:
            continue
    return rows, (name_col, phone_col, date_col, call_status_col)


def is_overdue_16h(created_date_str: str) -> bool:
    """True if lead created_date is more than 16 hours ago (and used for non-active leads)."""
    try:
        if isinstance(created_date_str, datetime):
            created = created_date_str
        else:
            created = datetime.strptime(str(created_date_str)[:19], "%Y-%m-%d %H:%M:%S")
        return (datetime.now() - created).total_seconds() > 16 * 3600
    except Exception:
        return False


def row_color(lead: dict) -> str:
    if lead.get("status") == "active":
        return "green"
    if is_overdue_16h(lead.get("created_date", "")):
        return "red"
    return "white"


def _date_key(d) -> str:
    """Return YYYY-MM-DD or YYYY-MM-DD HH:MM:SS string from created_date for comparison."""
    if d is None:
        return ""
    if isinstance(d, datetime):
        return d.strftime("%Y-%m-%d %H:%M:%S")
    return str(d)[:19] if d else ""


def _metrics_from_temp_leads(temp_leads: list) -> tuple:
    """Compute dashboard metrics from uploaded (session) data only."""
    from datetime import date
    today_str = date.today().isoformat()
    total = len(temp_leads)
    today = sum(1 for l in temp_leads if _date_key(l.get("created_date"))[:10] == today_str)
    active = sum(1 for l in temp_leads if l.get("status") == "active")
    overdue = sum(1 for l in temp_leads if l.get("status") != "active" and is_overdue_16h(l.get("created_date", "")))
    return total, today, active, overdue


def render_dashboard():
    st.title("Bảng điều khiển")
    temp_leads = _shared_leads
    if not temp_leads:
        st.info("Chưa có dữ liệu. Hãy tải file Excel lên để xem thống kê.")
        return
    total, today, active, overdue = _metrics_from_temp_leads(temp_leads)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tổng lead", total)
    c2.metric("Lead hôm nay", today)
    c3.metric("Vượt quá 16h", overdue, delta="⚠️" if overdue else None)
    c4.metric("Lead đã active", active)
    st.markdown("---")
    st.info("Số liệu từ bộ dữ liệu đã tải lên. Lead chưa active sau 16h được tô đỏ trong danh sách.")


def render_lead_management():
    st.title("Quản lý Lead")
    user = st.session_state.user
    is_admin = user["role"] == "admin"

    if is_admin:
        with st.expander("Tải file lead (.xlsx)", expanded=False):
            st.caption(
                "Tải lên hoặc tải lại file Excel. Nếu sales đã cập nhật \"Tình trạng gọi điện\" trong file, "
                "tải lại tại đây để đồng bộ trạng thái; phần gán lead được giữ nguyên."
            )
            uploaded = st.file_uploader("Chọn file .xlsx", type=["xlsx"])
            if uploaded:
                import pandas as pd
                try:
                    df = pd.read_excel(uploaded)
                    rows, mapped = _normalize_upload_df(df)
                    if mapped[0] is None or mapped[1] is None or mapped[2] is None:
                        st.error(
                            f"Không tìm thấy cột bắt buộc. Cần: name, phone, created_date. "
                            f"Đã nhận: name→{mapped[0]!r}, phone→{mapped[1]!r}, date→{mapped[2]!r}. "
                            f"Cột tình trạng gọi (tùy chọn): {mapped[3]!r}. Cột trong file: {list(df.columns)}"
                        )
                    elif not rows:
                        st.warning("Không có dòng hợp lệ để nhập (kiểm tra name/phone/date).")
                    else:
                        # Build new leads from file. On re-upload, preserve assignments by matching phone number (per spec).
                        existing = _shared_leads
                        by_phone = {}
                        for t in existing:
                            p = str(t.get("phone", "")).strip()
                            if p and p not in by_phone:
                                by_phone[p] = t

                        temp_id = -1
                        new_temp = []
                        for row in rows:
                            name, phone, created_date, status = row[0], row[1], row[2], row[3]
                            call_status_raw = row[4] if len(row) > 4 else ""
                            source = row[5] if len(row) > 5 else ""
                            person_in_charge = row[6] if len(row) > 6 else ""
                            notes_from_file = row[7] if len(row) > 7 else ""
                            phone_s = str(phone).strip()
                            base = {
                                "name": name,
                                "phone": phone_s,
                                "created_date": created_date,
                                "status": status,
                                "call_status": call_status_raw,
                                "source": source or None,
                                "person_in_charge": person_in_charge or None,
                                "notes_from_file": notes_from_file or None,
                            }
                            prev = by_phone.pop(phone_s, None)
                            if prev is not None:
                                # Keep sales-marked active: do not overwrite status/call_status from Excel
                                if prev.get("status") == "active":
                                    base = {**base, "status": "active", "call_status": "Đã nghe máy"}
                                new_temp.append({
                                    "id": prev["id"],
                                    **base,
                                    "assigned_to": prev.get("assigned_to"),
                                    "assigned_name": prev.get("assigned_name"),
                                    "assigned_at": prev.get("assigned_at"),
                                    "notes": prev.get("notes") or [],
                                })
                            else:
                                new_temp.append({
                                    "id": temp_id,
                                    **base,
                                    "assigned_to": None,
                                    "assigned_name": None,
                                    "assigned_at": None,
                                    "notes": [],
                                })
                                temp_id -= 1
                        _shared_leads.clear()
                        _shared_leads.extend(new_temp)
                        _save_shared_leads()
                        st.success(
                            f"Đã tải {len(rows)} lead từ file. Cột Tình trạng gọi điện đã cập nhật từ file. "
                            f"Phân công giữ theo SĐT. Dữ liệu dùng chung—sales đăng xuất/đăng nhập lại vẫn thấy lead được giao."
                        )
                except Exception as e:
                    st.error(f"Lỗi đọc file: {e}")

        # Download updated Excel (call_status column reflects current data, e.g. "Đã nghe máy" for active)
        if _shared_leads:
            import pandas as pd
            export_rows = []
            for t in _shared_leads:
                cd = t.get("created_date")
                if isinstance(cd, datetime):
                    cd = cd.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    cd = str(cd)[:19] if cd else ""
                export_rows.append({
                    "Tên Học Sinh": t.get("name") or "",
                    "Điện thoại phụ huynh": t.get("phone") or "",
                    "Ngày tạo": cd,
                    "Tình trạng gọi điện": t.get("call_status") or "Chưa liên hệ",
                    "Nguồn khách hàng": t.get("source") or "",
                    "Người phụ trách": t.get("person_in_charge") or "",
                    "Assigned": t.get("assigned_name") or "",
                })
            export_df = pd.DataFrame(export_rows)
            buf = io.BytesIO()
            export_df.to_excel(buf, index=False, engine="openpyxl")
            buf.seek(0)
            st.download_button(
                "📥 Tải file Excel đã cập nhật (Tình trạng gọi điện theo data hiện tại)",
                data=buf,
                file_name="leads_updated.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_updated_excel",
            )

    # Filters
    consultants = db.list_users(role="sales")
    if is_admin:
        col1, col2 = st.columns(2)
        with col1:
            phone_search = st.text_input("Tìm theo SĐT", placeholder="Số điện thoại...")
        with col2:
            consultant_options = ["Tất cả"] + [f"{u['name']} (ID:{u['id']})" for u in consultants]
            consultant_filter = st.selectbox("Lọc theo tư vấn viên", consultant_options, index=0)
        status_val = None
        assigned_filter = None
        if consultant_filter != "All" and "(ID:" in consultant_filter:
            try:
                assigned_filter = int(consultant_filter.split("(ID:")[1].rstrip(")"))
            except ValueError:
                pass
    else:
        phone_search = st.text_input("Tìm theo SĐT", placeholder="Số điện thoại...")
        status_val = None
        assigned_filter = None

    # Lead data in _shared_leads so admin and sales see the same dataset
    temp_leads = _shared_leads
    if is_admin:
        if not temp_leads:
            st.info("Chưa có lead. Hãy tải file Excel lên để bắt đầu.")
            return
        leads = list(temp_leads)
        if phone_search:
            leads = [l for l in leads if phone_search in str(l.get("phone", ""))]
        if assigned_filter is not None:
            leads = [l for l in leads if l.get("assigned_to") == assigned_filter]
        consultants = db.list_users(role="sales")
        for l in leads:
            if l.get("assigned_name") is None and l.get("assigned_to"):
                u = next((c for c in consultants if c["id"] == l["assigned_to"]), None)
                l["assigned_name"] = u["name"] if u else None
    else:
        my_leads = [l for l in temp_leads if l.get("assigned_to") == user["id"] and l.get("status") != "active"]
        if not my_leads:
            has_any_assigned = any(l.get("assigned_to") == user["id"] for l in temp_leads)
            if has_any_assigned:
                st.info("Không còn lead chờ. Tất cả lead được giao cho bạn đã active.")
            else:
                st.info("Chưa có lead nào được giao cho bạn. Admin cần tải file Excel và phân công lead.")
            return
        leads = my_leads
        if phone_search:
            leads = [l for l in leads if phone_search in str(l.get("phone", ""))]
        consultants = db.list_users(role="sales")
        for l in leads:
            if l.get("assigned_name") is None and l.get("assigned_to"):
                u = next((c for c in consultants if c["id"] == l["assigned_to"]), None)
                l["assigned_name"] = u["name"] if u else None

    if not leads:
        st.info("No leads match the current filters.")
        return

    st.markdown("---")
    st.subheader("Lead list")
    st.caption("🟢 Đã liên hệ (active) — nền xanh  |  ⬜ Chưa quá hạn — nền trắng  |  🔴 Quá 16h chưa active — nền đỏ")

    for lead_idx, lead in enumerate(leads):
        _id = lead.get("id", 0)
        _key = f"{_id}_{lead_idx}"  # unique per row to avoid DuplicateWidgetID when multiple leads share id
        is_lead_temp = isinstance(_id, int) and _id < 0
        color = row_color(lead)
        created = lead.get("created_date", "")
        assigned_name = lead.get("assigned_name") or "—"
        status = lead.get("status", "new")
        call_status_vn = lead.get("call_status") or ""
        if call_status_vn:
            status_line = f"Tình trạng gọi điện: {call_status_vn} → Trạng thái: {status}"
        else:
            status_line = f"Trạng thái: {status}"
        warning = " ⚠️ Quá 16h" if (status != "active" and is_overdue_16h(created)) else ""

        with st.container():
            if color == "red":
                st.markdown(
                    f"<div style='background:#ffcccc; color:#222; padding:10px; border-radius:6px; margin:4px 0; border-left:4px solid #c00;'>"
                    f"<b>{lead['name']}</b> | {lead['phone']} | Ngày tạo: {created} | Đã giao: {assigned_name} | {status_line}{warning}"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            elif color == "green":
                st.markdown(
                    f"<div style='background:#ccffcc; color:#222; padding:10px; border-radius:6px; margin:4px 0; border-left:4px solid #0a0;'>"
                    f"<b>{lead['name']}</b> | {lead['phone']} | Ngày tạo: {created} | Đã giao: {assigned_name} | {status_line}"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<div style='background:#fff; color:#222; padding:10px; border-radius:6px; margin:4px 0; border:1px solid #eee;'>"
                    f"<b>{lead['name']}</b> | {lead['phone']} | Ngày tạo: {created} | Đã giao: {assigned_name} | {status_line}"
                    f"</div>",
                    unsafe_allow_html=True,
                )

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                if is_admin and consultants:
                    options_ids = [None] + [u["id"] for u in consultants]
                    def _fmt_assignee(x, c=consultants):
                        if x is None:
                            return "— Chọn tư vấn viên —"
                        return next((u["name"] for u in c if u["id"] == x), str(x))
                    current_id = lead.get("assigned_to")
                    idx = 0 if current_id is None else (1 + next((i for i, u in enumerate(consultants) if u["id"] == current_id), 0))
                    new_assignee = st.selectbox(
                        "Gán / Đổi giao",
                        options=options_ids,
                        format_func=_fmt_assignee,
                        key=f"assign_{_key}",
                        index=min(idx, len(options_ids) - 1),
                    )
                    if st.button("Lưu phân công", key=f"save_assign_{_key}"):
                        if new_assignee is None:
                            st.warning("Chọn tư vấn viên trước khi lưu.")
                        else:
                            if is_lead_temp:
                                for t in _shared_leads:
                                    if t["id"] == _id:
                                        t["assigned_to"] = new_assignee
                                        t["assigned_name"] = next((u["name"] for u in consultants if u["id"] == new_assignee), None)
                                        t["assigned_at"] = datetime.now()
                                        _save_shared_leads()
                                        break
                            else:
                                db.assign_lead(_id, new_assignee)
                            st.success("Đã cập nhật.")
                            st.rerun()
            with c2:
                if not is_admin and status != "active" and st.button("Đánh dấu đã liên hệ", key=f"active_{_key}"):
                    if is_lead_temp:
                        for t in _shared_leads:
                            if t["id"] == _id:
                                t["status"] = "active"
                                t["call_status"] = "Đã nghe máy"
                                _save_shared_leads()
                                break
                    else:
                        db.set_lead_status(_id, "active")
                    st.rerun()
            with c3:
                if is_admin:
                    if st.button("Xem ghi chú", key=f"note_btn_{_key}"):
                        st.session_state[f"show_view_note_{_id}"] = True
                else:
                    if st.button("Sửa ghi chú", key=f"note_btn_{_key}"):
                        st.session_state[f"show_note_{_id}"] = True
            with c4:
                pass

            # Admin: view note (read-only, from sales)
            if is_admin and st.session_state.get(f"show_view_note_{_id}"):
                notes_list = lead.get("notes") or []
                if notes_list:
                    for n in notes_list:
                        st.markdown(f"**{n.get('user', '—')}** ({n.get('timestamp', '')}): {n.get('text', '')}")
                else:
                    st.caption("Chưa có note từ sales.")
                if st.button("Đóng", key=f"close_view_note_{_key}"):
                    st.session_state[f"show_view_note_{_id}"] = False
                    st.rerun()
            # Sales: Edit note (gửi nội dung note)
            if not is_admin and st.session_state.get(f"show_note_{_id}"):
                note_text = st.text_area("Nội dung note (gửi cho admin xem)", key=f"note_text_{_key}")
                if st.button("Gửi note", key=f"save_note_{_key}"):
                    if note_text.strip():
                        if is_lead_temp:
                            for t in _shared_leads:
                                if t["id"] == _id:
                                    t.setdefault("notes", []).append({
                                        "text": note_text.strip(),
                                        "user": user["name"],
                                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                    })
                                    _save_shared_leads()
                                    break
                        else:
                            db.add_lead_note(_id, user["id"], note_text.strip())
                    st.session_state[f"show_note_{_id}"] = False
                    st.rerun()
                if st.button("Hủy", key=f"cancel_note_{_key}"):
                    st.session_state[f"show_note_{_id}"] = False
                    st.rerun()
            st.markdown("---")


def render_user_management():
    st.title("Quản lý người dùng")
    st.subheader("Tư vấn viên (Sales)")
    sales = db.list_users(role="sales")
    if not sales:
        st.info("Chưa có tư vấn viên. Đăng ký tài khoản mới qua tab **Đăng ký** trên trang đăng nhập.")
        return
    for u in sales:
        with st.container():
            st.markdown(
                f"<div style='padding: 0.75rem 1rem; margin: 0.35rem 0; border-radius: 8px; "
                f"background: rgba(255,255,255,0.05); border-left: 4px solid #4a9eff;'>"
                f"<strong>{u['name']}</strong> &nbsp;·&nbsp; <span style='opacity:0.9'>{u['email']}</span> &nbsp;·&nbsp; "
                f"<span style='color:#7dd3fc'>{u['role']}</span></div>",
                unsafe_allow_html=True,
            )
    st.markdown("---")
    st.caption("Admin chỉ xem danh sách. Tài khoản Sales được tạo qua đăng ký.")


def render_reports():
    st.title("Xuất báo cáo")
    temp_leads = _shared_leads
    if not temp_leads:
        st.info("Chưa có dữ liệu. Tải file Excel lên để tạo báo cáo.")
        return

    import pandas as pd
    consultants = db.list_users(role="sales")
    rows = []
    for l in temp_leads:
        an = l.get("assigned_name")
        if not an and l.get("assigned_to"):
            u = next((c for c in consultants if c["id"] == l["assigned_to"]), None)
            an = u["name"] if u else None
        rows.append({
            "id": l.get("id"),
            "name": l.get("name"),
            "phone": l.get("phone"),
            "created_date": l.get("created_date"),
            "status": l.get("status"),
            "assigned_to": l.get("assigned_to"),
            "assigned_name": an,
        })
    df = pd.DataFrame(rows)
    df["created_date"] = pd.to_datetime(df["created_date"], errors="coerce")
    df["date"] = df["created_date"].dt.date

    report_type = st.radio("Loại báo cáo", ["Lead theo ngày", "Lead theo tư vấn viên", "Tỷ lệ active"])
    if report_type == "Lead theo ngày":
        by_date = df.groupby("date").agg(count=("id", "count")).reset_index()
        by_date.columns = ["Ngày", "Số lead"]
        st.dataframe(by_date)
        buf = by_date.to_csv(index=False)
    elif report_type == "Lead theo tư vấn viên":
        by_consultant = df.groupby("assigned_name", dropna=False).agg(count=("id", "count")).reset_index()
        by_consultant.columns = ["Tư vấn viên", "Số lead"]
        st.dataframe(by_consultant)
        buf = by_consultant.to_csv(index=False)
    else:
        total = len(df)
        active = (df["status"] == "active").sum()
        rate = (active / total * 100) if total else 0
        st.metric("Tỷ lệ active", f"{rate:.1f}%")
        summary = pd.DataFrame([{"Tổng lead": total, "Đã active": active, "Tỷ lệ %": round(rate, 1)}])
        st.dataframe(summary)
        buf = summary.to_csv(index=False)

    st.download_button("Tải CSV", buf, file_name="lead_report.csv", mime="text/csv")


def main():
    if st.session_state.user is None:
        login_page()
        return

    user = st.session_state.user
    if _LOGO_BYTES_SMALL:
        st.sidebar.image(_LOGO_BYTES_SMALL, use_column_width=False, width=140)
    st.sidebar.title("Quản lý Lead")
    st.sidebar.markdown(f"**{user['name']}** ({user['role']})")
    st.sidebar.markdown("")
    if st.sidebar.button("🔄 Làm mới dữ liệu", help="Cập nhật Dashboard, Lead, Báo cáo theo dữ liệu mới nhất"):
        st.rerun()

    pages = ["Bảng điều khiển", "Quản lý Lead", "Báo cáo"]
    if user["role"] == "admin":
        pages.append("Quản lý người dùng")
    _page_map = {"Bảng điều khiển": "Dashboard", "Quản lý Lead": "Lead Management", "Báo cáo": "Reports", "Quản lý người dùng": "User Management"}

    st.sidebar.markdown("**Điều hướng**")
    st.sidebar.markdown("")
    for p in pages:
        label = f"► {p}" if st.session_state.page == _page_map[p] else p
        if st.sidebar.button(label, key=f"nav_{p}"):
            st.session_state.page = _page_map[p]
            st.rerun()

    st.sidebar.markdown("---")
    if st.sidebar.button("Đăng xuất", key="sidebar_logout"):
        logout()
        st.rerun()

    if st.session_state.page == "Dashboard":
        render_dashboard()
    elif st.session_state.page == "Lead Management":
        render_lead_management()
    elif st.session_state.page == "User Management":
        render_user_management()
    else:
        render_reports()

    # Auto-refresh so sales see admin assign/upload after a few seconds
    _refresh_sec = int(os.environ.get("REFRESH_INTERVAL_SECONDS", "10"))
    if hasattr(st, "fragment") and _refresh_sec > 0:
        try:
            @st.fragment(run_every=timedelta(seconds=_refresh_sec))
            def _auto_refresh_shared_data():
                st.rerun()
            _auto_refresh_shared_data()
            st.sidebar.caption(f"🔄 Tự làm mới mỗi {_refresh_sec}s")
        except Exception:
            pass


if __name__ == "__main__":
    main()
