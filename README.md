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

Default admin: **admin@example.com** / **admin123**. Create sales users via **User Management** (Admin only).

## XLSX Format

| name        | phone      | created_date        |
|------------|------------|----------------------|
| Nguyen Van A | 0988888888 | 2026-03-13 09:30   |
| Tran Thi B   | 0977777777 | 2026-03-13 10:15   |

- `name`: text  
- `phone`: text  
- `created_date`: datetime (e.g. `YYYY-MM-DD HH:MM` or Excel datetime)

## Pages

- **Dashboard** – Metrics
- **Lead Management** – Upload (Admin), table with assign / mark active / notes
- **User Management** – Admin only: create/edit users, assign roles
- **Reports** – Export leads by date, by consultant, or activation rate
