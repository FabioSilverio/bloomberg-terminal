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

Deterministic provider matrix:
- **indices:** `stooq` → `stooq_proxy` (ETF mappings) → `yahoo` (optional augment) → `LKG` → `bootstrap`
- **fx:** `stooq` → `frankfurter` → `exchangerate.host` → `yahoo` (optional augment) → `LKG` → `bootstrap`
- **commodities:** `stooq` → `stooq_proxy` (ETF mappings) → `yahoo` (optional augment) → `LKG` → `bootstrap`
- **rates:** `FRED public CSV` → `FRED API` (optional) → `LKG` → `defaults` → `bootstrap`
- **crypto:** `CoinGecko` → `yahoo` (optional augment) → `LKG` → `bootstrap`

Resilience features:
- Yahoo is no longer a hard dependency for core sections (indices/fx/commodities/rates)
- Per-provider async rate limiters + retry with exponential backoff
- Provider circuit-breaker/cooldown (especially for repeated Yahoo failures)
- Per-section Last-Known-Good (`LKG`) persistence (`market:overview:lkg:{section}`)
- Bootstrap snapshot for first-run baseline even during total provider outage
- Fresh cache + stale cache keys for fast serving and recovery
- Backend payload includes row source + section source attribution + freshness (`sectionMeta`)
- Degraded banner text is explicit (e.g. `Yahoo down, serving from Stooq/FRED Public/CoinGecko`)

---

## Health / diagnostics endpoints

- Basic health: `GET /api/v1/health`
- Provider diagnostics: `GET /api/v1/health/providers`

Provider diagnostics includes status for providers (`yahoo`, `stooq`, `stooq_proxy`, `frankfurter`, `exchangerate_host`, `fred_api`, `fred_public`, `coingecko`, plus internal fallbacks) and tracks:
- `status` (`ok`, `degraded`, `cooldown`, `disabled`, `internal`)
- `last_attempt_at`
- `last_success_at`
- `last_error`
- `success_count`
- `failure_count`
- `consecutive_failures`
- `cooldown_until`

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
- `FX_TIMEOUT_SECONDS` (default: `8.0`)
- `FX_RATE_LIMIT_PER_MINUTE` (default: `30`)
- `COINGECKO_TIMEOUT_SECONDS` (default: `8.0`)
- `COINGECKO_RATE_LIMIT_PER_MINUTE` (default: `20`)
- `FRED_API_KEY` (optional)
- `FRED_TIMEOUT_SECONDS` (default: `8.0`)
- `FRED_PUBLIC_TIMEOUT_SECONDS` (default: `8.0`)
- `FRED_RATE_LIMIT_PER_MINUTE` (default: `30`)
- `MARKET_CACHE_TTL_SECONDS` (default: `20`)
- `MARKET_STALE_TTL_SECONDS` (default: `300`)
- `MARKET_LKG_TTL_SECONDS` (default: `604800`)
- `MARKET_BOOTSTRAP_ENABLED` (default: `true`)
- `MARKET_RATES_DEFAULTS_ENABLED` (default: `true`)
- `MARKET_WS_INTERVAL_SECONDS` (default: `10`)
- `PROVIDER_FAILURE_THRESHOLD` (default: `3`)
- `PROVIDER_COOLDOWN_SECONDS` (default: `180`)
- `YAHOO_FAILURE_THRESHOLD` (default: `2`)
- `YAHOO_COOLDOWN_SECONDS` (default: `300`)

---

## Troubleshooting MMAP degraded mode

If MMAP shows **DEGRADED** with banner like **"Yahoo down, serving from X/Y"**:

1. Check provider diagnostics:
   - `GET /api/v1/health/providers`
2. Confirm Yahoo cooldown state (`status=cooldown`) and `cooldown_until`
3. Tune pressure and cache behavior:
   - increase `MARKET_CACHE_TTL_SECONDS`
   - increase `MARKET_WS_INTERVAL_SECONDS`
   - increase `YAHOO_COOLDOWN_SECONDS`
4. Verify non-Yahoo fallbacks are reachable (`stooq`, `frankfurter`, `fred_public`, `coingecko`)
5. Keep `MARKET_BOOTSTRAP_ENABLED=true` for first-run baseline snapshots
6. For strict outage simulation (expect empty degraded 200), set both `MARKET_BOOTSTRAP_ENABLED=false` and `MARKET_RATES_DEFAULTS_ENABLED=false`

Core sections should remain populated even when Yahoo is unavailable.

---

## Backend tests

```bash
cd apps/backend
pip install -r requirements-dev.txt
pytest
```

Fallback behavior coverage includes:
- Yahoo hard fail + other providers OK => sections populated
- Yahoo + primary provider fail + fallback providers OK => sections populated
- All live providers fail + LKG available => sections populated from cache
- All providers fail + no LKG + bootstrap disabled => graceful empty degraded `200`
- `/api/v1/market/overview` remains populated in simulated Yahoo outage

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
