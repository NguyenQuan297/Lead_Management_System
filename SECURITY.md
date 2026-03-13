# Security

Before deploying or uploading this project to GitHub:

## 1. Secrets and environment variables

- **Never commit** `.env` or any file containing real passwords, API keys, or registration codes.
- Copy `.env.example` to `.env` and set values locally. `.env` is in `.gitignore`.
- Set strong values for:
  - `ADMIN_REGISTRATION_CODE` – required for creating admin accounts
  - `SALES_REGISTRATION_CODE` – required for creating sales accounts
  - `COOKIES_PASSWORD` – used to encrypt session cookies; use a long random string

## 2. Default admin account

- On first run, if no users exist, a default admin is created:
  - Email: `adminFPT@gmail.com`
  - Password: `adminFPT2026`
- **Change this password** in production or when sharing the system.

## 3. Database and session data

- `lead_management.db` and `.shared_leads.json` are ignored by git so they are not committed.
- Do not commit these files; they may contain user and lead data.

## 4. Deployment

- Run behind HTTPS in production.
- Restrict access to the app (e.g. VPN, IP allowlist, or auth proxy) if needed.
- Keep dependencies up to date (`pip install -r requirements.txt` and review security advisories).
