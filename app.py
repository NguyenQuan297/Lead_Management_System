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
_LOGO_BYTES_SMALL = None
_LOGO_FAVICON_BYTES = None
_page_icon = "📋"
if _LOGO_PATH.exists():
    try:
        from PIL import Image
        resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
        with open(_LOGO_PATH, "rb") as f:
            img = Image.open(f).convert("RGBA")
        w, h = img.size
        data = img.getdata()
        threshold = 248
        new_data = []
        for item in data:
            r, g, b, a = item
            if r >= threshold and g >= threshold and b >= threshold:
                new_data.append((255, 255, 255, 0))
            else:
                new_data.append(item)
        img.putdata(new_data)
        w_full = min(w, 180)
        h_full = int(h * w_full / w)
        img_full = img.resize((w_full, h_full), resample)
        buf = io.BytesIO()
        img_full.save(buf, format="PNG")
        buf.seek(0)
        _LOGO_BYTES = buf.getvalue()
        w_small = min(w, 140)
        h_small = int(h * w_small / w)
        img_small = img.resize((w_small, h_small), resample)
        buf_s = io.BytesIO()
        img_small.save(buf_s, format="PNG")
        buf_s.seek(0)
        _LOGO_BYTES_SMALL = buf_s.getvalue()
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

st.set_page_config(page_title="Hệ thống Quản lý Lead", page_icon=_page_icon, layout="wide")

st.markdown("""
<style>
    [data-testid="stSidebar"] .stButton > button { width: 100%%; min-height: 2.75rem; padding: 0.5rem 1rem; font-size: 0.95rem; border-radius: 8px; justify-content: center; }
    [data-testid="stSidebar"] .stButton { width: 100%%; }
    [data-testid="stSidebar"] h1 { font-size: 1.35rem; margin-bottom: 0.5rem; }
    [data-testid="stSidebar"] .stMarkdown { margin-bottom: 0.25rem; }
    [data-testid="stSidebar"] hr { margin: 1rem 0; }
    [data-testid="stSidebar"] .stImage:first-child { margin-top: 0; margin-bottom: 0.25rem; }
    [data-testid="stSidebar"] .stImage:first-child img { max-width: 140px; }
    .main .block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1100px; margin-left: auto; margin-right: auto; }
    .main .block-container [data-testid="column"] { text-align: center; }
    .main .block-container [data-testid="column"] .stImage { display: flex; justify-content: center; }
    .main .block-container [data-testid="column"] .stImage img { display: block; margin-left: auto; margin-right: auto; }
    .main .block-container [data-testid="column"] h1 { text-align: center; }
    .main .block-container [data-testid="column"] hr { margin-left: auto; margin-right: auto; }
    h1 { font-size: 1.75rem; margin-bottom: 0.5rem; }
    h2 { font-size: 1.25rem; margin-top: 1rem; margin-bottom: 0.5rem; }
</style>
""", unsafe_allow_html=True)

try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent / ".env"
    load_dotenv(_env_path)
except ImportError:
    pass

if not hasattr(st, "rerun"):
    st.rerun = st.experimental_rerun

import database as db
import auth_utils as auth

try:
    from streamlit_cookies_manager import EncryptedCookieManager
    _COOKIES = EncryptedCookieManager(prefix="leadmgmt/", password=os.environ.get("COOKIES_PASSWORD", "leadmgmt-session-secret"))
    _USE_COOKIES = True
except Exception:
    _COOKIES = None
    _USE_COOKIES = False

COOKIE_USER_ID = "user_id"
QUERY_PARAM_SESSION = "session_id"

def _get_session_id_from_url():
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
    if st.session_state.user is not None:
        return
    if st.session_state.get("_just_logged_out"):
        st.session_state._just_logged_out = False
        return
    session_id = _get_session_id_from_url()
    if session_id:
        user = db.get_user_by_session(session_id)
        if user:
            st.session_state.user = dict(user)

_SHARED_LEADS_FILE = Path(__file__).resolve().parent / ".shared_leads.json"

def _load_shared_leads():
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

_mod = sys.modules[__name__]
if not hasattr(_mod, "_shared_leads"):
    _mod._shared_leads = []
_shared_leads = _mod._shared_leads
_shared_leads.clear()
_shared_leads.extend(_load_shared_leads())

db.init_db()
auth.ensure_admin_user()

if "user" not in st.session_state:
    st.session_state.user = None
if "page" not in st.session_state:
    st.session_state.page = "Dashboard"
if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "login"

if _USE_COOKIES and _COOKIES is not None and not _COOKIES.ready():
    if not st.session_state.get("_cookie_init_rerun"):
        st.session_state._cookie_init_rerun = True
        st.rerun()
else:
    if _USE_COOKIES:
        st.session_state._cookie_init_rerun = False
_restore_session()

def _set_session_in_url(session_id: str):
    if hasattr(st, "query_params"):
        st.query_params[QUERY_PARAM_SESSION] = session_id
        return
    if hasattr(st, "experimental_set_query_params"):
        st.experimental_set_query_params(**{QUERY_PARAM_SESSION: session_id})

def _clear_session_from_url():
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
    if current_user and current_user.get("role") == "admin":
        _shared_leads.clear()
        _save_shared_leads()
    st.session_state._just_logged_out = True

def login_page():
    logo_b64 = base64.b64encode(_LOGO_BYTES).decode("utf-8") if _LOGO_BYTES else None
    st.markdown(
        "<div style='margin-top: 1.5rem; text-align: center;'>"
        + ("<img src='data:image/png;base64," + logo_b64 + "' width='180' style='display: block; margin: 0 auto;'/>" if logo_b64 else "")
        + "<hr style='margin: 0.75rem auto; max-width: 400px;'/>"
        + "<h1 style='font-size: 1.75rem; margin: 0.5rem 0;'>Hệ thống Quản lý Lead</h1>"
        + "</div>",
        unsafe_allow_html=True,
    )
    tab_login, tab_register = st.tabs(["Đăng nhập", "Đăng ký"])
    with tab_login:
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
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
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            with st.form("register_form"):
                name = st.text_input("Họ tên", placeholder="Họ và tên đầy đủ")
                email_r = st.text_input("Email", placeholder="email@vd.com", key="reg_email")
                password_r = st.text_input("Mật khẩu", type="password", placeholder="••••••••", key="reg_password")
                role = st.selectbox("Vai trò", ["Admin", "Sales"], index=1)
                registration_code = st.text_input("Mã đăng ký", type="password", placeholder="Nhập mã theo vai trò", help="Lấy mã từ quản trị viên (Admin hoặc Sales).")
                submitted = st.form_submit_button("Đăng ký")
                if submitted:
                    ok, err = auth.register(name, email_r, password_r, role.lower(), registration_code)
                    if ok:
                        st.success("Tạo tài khoản thành công. Bạn có thể đăng nhập.")
                    else:
                        st.error(err or "Đăng ký thất bại.")

COLUMN_MAPPING = {
    "name": ["name", "Tên Học Sinh", "Họ và tên phụ huynh", "Tên", "Họ tên", "Name"],
    "phone": ["phone", "Điện thoại phụ huynh", "Điện thoại", "Phone", "Số điện thoại"],
    "created_date": ["created_date", "Ngày tạo", "created", "Created Date", "Ngày"],
    "call_status": ["Tình trạng gọi điện", "status", "Status", "Call status", "Tình trạng"],
    "source": ["Nguồn khách hàng", "source", "Source", "Nguồn"],
    "person_in_charge": ["Người phụ trách", "person_in_charge", "Người phụ trách"],
    "notes": ["Ghi chú", "notes", "Notes", "Ghi chú"],
}
CALL_STATUS_TO_LEAD_STATUS = {
    "chưa liên hệ": "new", "chưa nghe máy lần 1": "new", "chưa nghe máy lần 2": "new", "chưa nghe máy": "new",
    "đã nghe máy": "active", "đăng ký lại": "active", "đã liên hệ": "active", "đã xử lý": "active",
}

def _find_column(df_columns, candidates):
    cols = [str(c).strip() for c in df_columns]
    for cand in candidates:
        for c in cols:
            if c and cand and c.lower() == cand.lower():
                return c
    return None

def _parse_created_date(value):
    if value is None or (isinstance(value, float) and value != value):
        return None
    if hasattr(value, "to_pydatetime"):
        return value.to_pydatetime()
    if isinstance(value, datetime):
        return value
    s = str(value).strip()
    if not s:
        return None
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:19].strip() if len(s) > 19 else s, fmt)
        except ValueError:
            continue
    return None

def _normalize_status_key(s: str) -> str:
    if not s:
        return ""
    s = str(s).strip().lower()
    while "  " in s:
        s = s.replace("  ", " ")
    return s

def _excel_call_status_to_lead_status(value) -> str:
    if value is None or (isinstance(value, float) and value != value):
        return "new"
    key = _normalize_status_key(str(value))
    if not key:
        return "new"
    if key in CALL_STATUS_TO_LEAD_STATUS:
        return CALL_STATUS_TO_LEAD_STATUS[key]
    if "đã nghe" in key or "nghe máy" in key or "đăng ký lại" in key or "đã liên hệ" in key or "đã xử lý" in key:
        return "active"
    return "new"

def _safe_str(v, default=""):
    import pandas as pd
    if v is None or (isinstance(v, float) and (v != v or pd.isna(v))):
        return default
    return str(v).strip() or default

def _normalize_upload_df(df):
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

def is_overdue_16h(created_date_str) -> bool:
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
    if d is None:
        return ""
    if isinstance(d, datetime):
        return d.strftime("%Y-%m-%d %H:%M:%S")
    return str(d)[:19] if d else ""

def _metrics_from_temp_leads(temp_leads: list) -> tuple:
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
