# OpenBloom Terminal (Bloomberg-style)

Production-oriented Bloomberg Terminal-like web app built incrementally.

## Current milestone
- ✅ Core terminal shell (theme, command bar, hotkeys, tiling panel layout, status bar clocks)
- ✅ MMAP module with resilient multi-provider backend
- ✅ INTRA/EQRT intraday realtime panel (1D chart + stats + stream)
- ✅ Persistent watchlist for equities/FX (DB model + API + UI + commands)
- ✅ Alerts v2 end-to-end: advanced conditions (above/below/crosses/% move), cooldown + one-shot/repeating, trigger history, ALRT panel, toast/sound notifications, and command flows

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
- lightweight-charts

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
docker compose up --build -d
```

Open: `http://localhost`

Backend now auto-runs `alembic upgrade head` on startup (with retries), then starts API.

Useful checks:

```bash
docker compose logs -f backend
curl http://localhost/api/v1/health
curl http://localhost/api/v1/health/ready
```

---

## Modo fácil (PT-BR) 🚀

Se você só quer abrir e usar, sem complicar:

```bash
cp .env.example .env
docker compose up --build -d
```

Depois:

```bash
# App principal
start http://localhost

# Saúde geral
curl http://localhost/api/v1/health

# Pronto para uso (DB + migrações)
curl http://localhost/api/v1/health/ready
```

Fluxo simples de uso:

- Abra **WL** (watchlist)
- Use **Quick add**: `USD/BRL`, `EUR/BRL`, `^BVSP`, `^GSPC`, `BTCUSD`
- Clique no símbolo para abrir **INTRA**
- Também aceita entrada manual: `USD/BRL`, `USDBRL`, `BRLUSD`, `AAPL`, `BTC-USD`

---

## Local development (without Docker)

### Backend
```bash
cd apps/backend
py -3.11 -m venv .venv
.venv\Scripts\activate  # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd apps/frontend
npm install
npm run dev
```

---

## Terminal commands (keyboard-first)

- `MMAP` → open Market Overview panel
- `MMAP REFRESH <seconds|ms>` → set MMAP UI refresh interval (example: `MMAP REFRESH 2`, `MMAP REFRESH 1500MS`)
- `INTRA <SYMBOL>` or `EQRT <SYMBOL>` → open intraday realtime panel (examples: `INTRA USD/BRL`, `INTRA BRLUSD`, `EQRT AAPL`)
- `WL` → open watchlist panel
- `WL ADD <SYMBOL>` → persist symbol in watchlist (examples: `WL ADD USD/BRL`, `WL ADD ^BVSP`, `WL ADD BTCUSD`)
- `WL RM <SYMBOL>` → remove symbol from watchlist
- `ALRT` → open alerts manager panel
- `ALRT ADD <SYMBOL> <CONDITION> <VALUE>` → create alert (examples: `ALRT ADD AAPL ABOVE 210`, `ALRT ADD EURUSD XBELOW 1.08`, `ALRT ADD AAPL PCTUP 2`)
- `ALRT RM <ID>` → remove alert by id

Hotkeys:
- `Ctrl/Cmd + K` → focus command bar
- `Ctrl/Cmd + Shift + M` → open MMAP
- `Ctrl/Cmd + Shift + I` → open INTRA AAPL
- `Ctrl/Cmd + Shift + W` → open WL
- `Ctrl/Cmd + Shift + A` → open ALRT
- `Ctrl/Cmd + Shift + ← / →` → cycle active panel
- `Ctrl/Cmd + Shift + X` → close active panel
- `Ctrl/Cmd + Shift + D` → toggle panel density mode
- `↑ / ↓` in command bar → command history

---

## MMAP and intraday refresh model

MMAP and INTRA refresh every 2 seconds by default, but backend protection prevents provider hammering:

- **UI cache** (`MARKET_CACHE_TTL_SECONDS`, default `2s`)
- **Upstream refresh cadence** (`MARKET_UPSTREAM_REFRESH_SECONDS`, default `8s`)
- **Single-flight refresh locks** for overview and per-symbol intraday fetches
- **Stale/LKG fallbacks** when upstream providers fail

Result: frequent terminal updates without unsafe upstream burst traffic.

INTRA chart rendering follows TradingView Lightweight Charts usage patterns (single chart instance + guarded incremental updates + deduped timestamps) for stability.

---

## API endpoints

### Market
- `GET /api/v1/market/overview`
- `GET /api/v1/market/intraday/{symbol}`
- `WS  /ws/market/overview`
- `WS  /ws/market/intraday/{symbol}`

### Watchlist
- `GET    /api/v1/watchlist`
- `POST   /api/v1/watchlist` body: `{ "symbol": "AAPL" }`
- `DELETE /api/v1/watchlist/{item_id}`
- `DELETE /api/v1/watchlist/by-symbol/{symbol}`
- `POST   /api/v1/watchlist/reorder`

### Alerts
- `GET    /api/v1/alerts?symbol=<optional>&status=<active|inactive>`
- `POST   /api/v1/alerts` body: `{ "symbol": "AAPL", "condition": "price_above", "threshold": 210, "enabled": true, "oneShot": false, "cooldownSeconds": 60 }`
- `GET    /api/v1/alerts/{alert_id}`
- `PATCH  /api/v1/alerts/{alert_id}`
- `DELETE /api/v1/alerts/{alert_id}`
- `GET    /api/v1/alerts/events?afterId=<optional>&limit=<optional>`
- (compat) `PUT    /api/v1/alerts/watchlist/{item_id}`
- (compat) `DELETE /api/v1/alerts/watchlist/{item_id}`

### Health
- `GET /api/v1/health`
- `GET /api/v1/health/ready` (readiness: DB + migration tables + alembic version)
- `GET /api/v1/health/providers`

---

## Environment variables (key additions)

Frontend:
- `NEXT_PUBLIC_MMAP_REFRESH_INTERVAL_MS` (default `2000`)
- `NEXT_PUBLIC_INTRADAY_REFRESH_INTERVAL_MS` (default `2000`)
- `NEXT_PUBLIC_WATCHLIST_REFRESH_INTERVAL_MS` (default `2000`)
- `NEXT_PUBLIC_ALERTS_POLL_INTERVAL_MS` (default `2000`)
- `NEXT_PUBLIC_API_TIMEOUT_MS` (default `10000`) — prevents UI hanging on pending requests
- `NEXT_PUBLIC_INTRADAY_WS_BASE_URL` (optional override)

Backend:
- `MARKET_CACHE_TTL_SECONDS` (default `2`)
- `MARKET_UPSTREAM_REFRESH_SECONDS` (default `8`)
- `MARKET_WS_INTERVAL_SECONDS` (default `2`)
- `INTRADAY_RATE_LIMIT_PER_MINUTE` (default `40`)
- `WATCHLIST_MAX_ITEMS` (default `40`)
- `ALERTS_DEFAULT_COOLDOWN_SECONDS` (default `60`)
- `ALERTS_TRIGGER_DISPLAY_SECONDS` (default `120`)

Full list in `.env.example`.

---

## Backend tests

```bash
cd apps/backend
pip install -r requirements-dev.txt
pytest
```

Coverage now includes:
- market fallback matrix behavior
- coalesced concurrent MMAP refresh requests
- intraday symbol normalization (including Bloomberg-style FX aliases), caching, and stale fallback
- coalesced concurrent intraday requests
- watchlist add/reorder/remove + quote enrichment + alert state badges
- alert API CRUD and events feed
- alert evaluator crossing logic, cooldown suppression, and one-shot auto-disable

Frontend smoke tests:
```bash
cd apps/frontend
npm run test:run
```
Includes ALRT panel rendering and watchlist trigger indicator checks.
