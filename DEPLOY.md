# Deploy (Render + Neon + Upstash, free tier)

This repo is ready for Blueprint deploy via `render.yaml` (frontend + backend).

## 0) Pre-deploy smoke check (one command)

From repo root:

### macOS/Linux
```bash
bash scripts/smoke-prod.sh
```

### Windows (PowerShell)
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\smoke-prod.ps1
```

> Add `KEEP_UP=1` (bash) or `-KeepUp` (PowerShell) if you want to leave containers running.

---

## 1) Unavoidable account auth (1–2 clicks each)

1. **Neon**: Sign in with GitHub/Google -> create project.
2. **Upstash**: Sign in with GitHub/Google -> create Redis database.
3. **Render**: Sign in with GitHub -> connect this repository.

---

## 2) Create Neon + Upstash connection strings

### Neon (Postgres)
- In Neon project -> **Connection Details** -> copy pooled connection string.
- Use it as `DATABASE_URL` in Render.
- `postgres://` / `postgresql://` URLs are accepted (backend auto-normalizes to `postgresql+asyncpg://...`).

### Upstash (Redis)
- In Upstash Redis DB -> **Details** -> copy **TLS Redis URL** (`rediss://...`).
- Use it as `REDIS_URL` in Render.

---

## 3) Deploy on Render using Blueprint

1. Render Dashboard -> **New +** -> **Blueprint**.
2. Select this repo/branch (`main`). Render auto-detects `render.yaml`.
3. Fill prompted `sync: false` variables:
   - `openbloom-backend`
     - `DATABASE_URL` = Neon URL
     - `REDIS_URL` = Upstash TLS URL
     - `FRED_API_KEY` = optional (can stay empty)
   - `openbloom-frontend`
     - `NEXT_PUBLIC_API_BASE_URL` = backend public URL (e.g. `https://<your-backend>.onrender.com`)
4. Click **Apply**.

If you don't know backend URL yet on first run:
- Deploy once, copy backend URL from service page,
- set `NEXT_PUBLIC_API_BASE_URL` on frontend,
- click **Manual Deploy -> Deploy latest commit**.

---

## 4) Post-deploy checks

After both services are live:

- Frontend: `https://<your-frontend>.onrender.com`
- Backend health: `https://<your-backend>.onrender.com/api/v1/health`
- Backend readiness: `https://<your-backend>.onrender.com/api/v1/health/ready`

Expected readiness response includes:
- `status: "ok"`
- `database: "ok"`
- `migrations: "ok"`

---

## Notes

- Backend start command runs migrations automatically before API start (`sh start.sh`).
- CORS defaults allow localhost plus hosted Render domains (`https://*.onrender.com`) and can be tightened with `FRONTEND_PUBLIC_URL` if needed.
- Frontend websocket URLs auto-derive from `NEXT_PUBLIC_API_BASE_URL` (optional WS env overrides are still supported).
