# Lead Management System

Internal web application for Marketing/Admissions to upload leads from `.xlsx` files, track activation, and assign leads to sales consultants.

## Features

- **Upload** `.xlsx` files with columns: `name`, `phone`, `created_date`
- **Dashboard**: Total leads, leads today, leads exceeding 16 hours, active leads
- **Lead list**: Search by phone, filter by status and sales consultant; assign/reassign, mark active, add notes
- **16-hour rule**: Leads not activated after 16 hours are highlighted in **red**; active leads in **green**
- **User roles**: Admin (upload, view all, assign, reassign, manage users) and Sales (view own leads, update status, notes)
- **Reports**: Export by date, by consultant, or activation rate (CSV)

## Tech Stack

- Python 3.10+
- Streamlit
- Pandas + OpenPyXL (Excel)
- SQLite
- bcrypt (passwords)

## Setup

```bash
cd "c:\Users\Admin\OneDrive - Troy University\Lead_Management_System"
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Copy `.env.example` to `.env` and set `DEFAULT_ADMIN_EMAIL`, `DEFAULT_ADMIN_PASSWORD`, and registration codes. On first run (empty DB), one admin is created from those env vars. Create sales users via **Register** tab (with the right registration code).

## XLSX Format

| name        | phone      | created_date        |
|------------|------------|----------------------|
| Nguyen Van A | 0988888888 | 2026-03-13 09:30   |
| Tran Thi B   | 0977777777 | 2026-03-13 10:15   |

- `name`: text  
- `phone`: text  
- `created_date`: datetime (e.g. `YYYY-MM-DD HH:MM` or Excel datetime)

## Deploy (Streamlit Cloud, Railway, etc.)

**Quan trọng:** Trên server **không có file `.env`** (file này không được đẩy lên Git). Bạn phải cấu hình **Environment variables / Secrets** trên nền tảng deploy:

| Biến | Bắt buộc | Ghi chú |
|------|----------|--------|
| `DEFAULT_ADMIN_EMAIL` | Có | Email đăng nhập admin (tạo khi DB trống) |
| `DEFAULT_ADMIN_PASSWORD` | Có | Mật khẩu admin |
| `ADMIN_REGISTRATION_CODE` | Có | Mã để đăng ký tài khoản Admin |
| `SALES_REGISTRATION_CODE` | Có | Mã để đăng ký tài khoản Sales |
| `COOKIES_PASSWORD` | Tùy chọn | Mã hóa cookie (đặt chuỗi bí mật) |

- **Streamlit Cloud:** Settings → Secrets (hoặc Secrets trong repo) → thêm từng dòng `TÊN_BIẾN=giá_trị`.
- Sau khi thêm xong, **redeploy** (hoặc restart app) để app đọc biến môi trường và tạo admin lần đầu.

Nếu không set các biến trên, app deploy sẽ **không tạo admin** → không đăng nhập được.

## Pages

- **Dashboard** – Metrics
- **Lead Management** – Upload (Admin), table with assign / mark active / notes
- **User Management** – Admin only: create/edit users, assign roles
- **Reports** – Export leads by date, by consultant, or activation rate
