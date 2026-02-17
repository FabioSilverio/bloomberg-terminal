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
py -3.11 -m venv .venv
.venv\Scripts\activate  # macOS/Linux: source .venv/bin/activate
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

Provider strategy:
1. Yahoo Finance quotes (`query1/query2.finance.yahoo.com`) as primary
2. Stooq fallback for indices, FX, commodities (`stooq.com`) 
3. FRED API rates (optional, if `FRED_API_KEY` provided)
4. FRED public CSV fallback for treasury rates (no API key required)
5. CoinGecko fallback for crypto
6. Stale cache fallback if all live providers fail

Resilience features:
- Per-provider async rate limiters
- Retry with exponential backoff for transient failures/rate limits
- Yahoo endpoint failover (`query1` -> `query2`)
- Fresh cache + stale cache keys
- Degraded-mode warnings surfaced to UI
- Provider diagnostics endpoint with last error and last success timestamp

---

## Health / diagnostics endpoints

- Basic health: `GET /api/v1/health`
- Provider diagnostics: `GET /api/v1/health/providers`

Provider diagnostics includes status for each provider (`yahoo`, `stooq`, `fred_api`, `fred_public`, `coingecko`) and tracks:
- `status`
- `last_attempt_at`
- `last_success_at`
- `last_error`
- `success_count`
- `failure_count`

---

## Environment variables (MMAP/provider tuning)

- `YAHOO_TIMEOUT_SECONDS` (default: `8.0`)
- `YAHOO_MAX_RETRIES` (default: `2`)
- `YAHOO_RATE_LIMIT_PER_MINUTE` (default: `40`)
- `YAHOO_USER_AGENT` (default: modern browser UA)
- `YAHOO_ACCEPT_LANGUAGE` (default: `en-US,en;q=0.9`)
- `YAHOO_ENDPOINTS` (JSON array of quote endpoints)
- `STOOQ_TIMEOUT_SECONDS` (default: `8.0`)
- `STOOQ_RATE_LIMIT_PER_MINUTE` (default: `30`)
- `COINGECKO_TIMEOUT_SECONDS` (default: `8.0`)
- `COINGECKO_RATE_LIMIT_PER_MINUTE` (default: `20`)
- `FRED_API_KEY` (optional)
- `FRED_TIMEOUT_SECONDS` (default: `8.0`)
- `FRED_PUBLIC_TIMEOUT_SECONDS` (default: `8.0`)
- `FRED_RATE_LIMIT_PER_MINUTE` (default: `30`)
- `MARKET_CACHE_TTL_SECONDS` (default: `20`)
- `MARKET_STALE_TTL_SECONDS` (default: `300`)
- `MARKET_WS_INTERVAL_SECONDS` (default: `10`)

---

## Troubleshooting MMAP degraded mode

If MMAP shows **DEGRADED MODE**:

1. Check provider diagnostics:
   - `GET /api/v1/health/providers`
2. Look for Yahoo `HTTP 429` / rate-limit issues
3. Reduce provider pressure:
   - increase `MARKET_CACHE_TTL_SECONDS`
   - increase `MARKET_WS_INTERVAL_SECONDS`
4. Ensure a valid `YAHOO_USER_AGENT` is configured
5. Verify outbound internet access from backend container/host

Even if Yahoo is unavailable, indices/FX/commodities/rates should continue via fallback providers.

---

## Backend tests

```bash
cd apps/backend
pip install -r requirements-dev.txt
pytest
```

Fallback behavior coverage includes:
- Yahoo failure -> Stooq + FRED public + CoinGecko fallback population
- Stale cache serving when all live providers fail

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
