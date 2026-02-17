# OpenBloom Terminal (Bloomberg-style)

Production-oriented Bloomberg Terminal-like web app built incrementally.

## Current milestone
- ✅ Core shell (theme, command bar, hotkeys, tiling panel layout, status bar clocks)
- ✅ MMAP module (Market Overview) with resilient multi-provider backend
- ⏳ Next: EQ module (equities + charting)

See:
- Implementation plan: `docs/implementation-plan.md`
- Module status board: `docs/module-status.md`

---

## Tech stack

### Frontend
- Next.js 15 + TypeScript
- Tailwind CSS
- Zustand
- TanStack Query
- react-grid-layout
- lightweight-charts (for upcoming EQ)

### Backend
- FastAPI (async)
- SQLAlchemy + Alembic
- Redis cache with in-memory fallback
- WebSocket streaming for market updates

### Infra
- PostgreSQL
- Redis
- Docker Compose
- Nginx reverse proxy

---

## Quick start (Docker)

```bash
cp .env.example .env
docker compose up --build
```

Open: `http://localhost`

Services:
- Frontend (Next.js): internal `frontend:3000`
- Backend (FastAPI): internal `backend:8000`
- Postgres: `localhost:5432`
- Redis: `localhost:6379`

---

## Local development (without Docker)

### Backend
```bash
cd apps/backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd apps/frontend
npm install
npm run dev
```

Set env vars if needed:
- `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`
- `NEXT_PUBLIC_WS_BASE_URL=ws://localhost:8000/ws/market/overview`

---

## MMAP data integrations (current)

Primary + fallback chain:
1. Yahoo Finance quotes (`query1.finance.yahoo.com`)
2. FRED rates (if `FRED_API_KEY` provided)
3. CoinGecko fallback for crypto
4. Stale cache fallback if providers fail

Resilience features:
- Per-provider async rate limiters
- Retry with exponential backoff for transient HTTP failures
- Fresh cache + stale cache keys
- Degraded-mode warnings surfaced to UI

---

## Keyboard shortcuts
- `Ctrl/Cmd + K` → focus command bar
- `Ctrl/Cmd + Shift + M` → open MMAP panel

---

## Next milestone
Implement `EQ` module with:
- Symbol search
- Historical OHLC charting
- Quote stats and fundamentals summary
- Shared command workflow (`EQ AAPL US`, etc)
