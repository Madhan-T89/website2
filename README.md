# Praveena Website + Clinic Management

This repo contains:
- The original static site (`index.html`, `style.css`)
- A new **Clinic Management** web app (FastAPI + SQLite) under `clinic_app/`

## Run the Clinic Management app (Windows)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn clinic_app.main:app --port 8000
```

Then open:
- `http://127.0.0.1:8000/` (redirects to login)

## Default login (created on first run)

- **Username**: `admin`
- **Password**: `admin123`
- **Role**: Admin

You can change these in `clinic_app/seed.py`.

## Environment

Optional env vars:
- `APP_ENV=demo|prod` (default: `demo`) — keeps demo and production isolated
- `JWT_SECRET=...` (recommended) — set a real value for production

You can copy `.env.example` to `.env`.
