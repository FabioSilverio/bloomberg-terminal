# Bloomberg Builder Implementation Plan

## Product goal
Build a production-grade Bloomberg Terminal-like web application with a dark, dense keyboard-first UI and modular financial workspaces. Stack: Next.js + FastAPI + PostgreSQL + Redis + WebSockets + Docker.

## Delivery sequence (strict)
1. **Core shell** (theme, command bar, panel tiling, hotkeys, status bar)
2. **MMAP** (Market Overview with real market feeds + graceful degradation)
3. **EQ** (equity analytics with charting and quote details)
4. Remaining modules in order: ECOF → NEWS → PORT → EQS → FI → FA → GP → FX → CMDT → CRYPTO → MSG

## Architecture

### Frontend (`apps/frontend`)
- Next.js App Router + TypeScript + Tailwind CSS
- Zustand store for workspace/panel state and command routing
- TanStack Query for API fetching, retries, and cache coherence
- `react-grid-layout` for tiling and drag/resize panel behavior
- `lightweight-charts` and D3 for chart modules
- Keyboard-first command workflow with global command parser

### Backend (`apps/backend`)
- FastAPI async API and WebSocket endpoints
- SQLAlchemy async + Alembic migrations (PostgreSQL)
- Redis cache with local fallback TTL cache
- Provider layer for Yahoo Finance, Alpha Vantage, Finnhub, Polygon, FRED, CoinGecko, News API, SEC
- API response envelopes include metadata about degraded/fallback data paths

### Infra (`infra`)
- Docker Compose services: frontend, backend, postgres, redis, nginx
- Nginx reverse proxy for `/` (frontend) and `/api`, `/ws` (backend)
- Environment-driven config (`.env.example`)

## Reliability and resilience rules
- Outbound API calls guarded by per-provider async rate limiters
- Retry with exponential backoff for transient errors
- Cache TTL by data class (short TTL for quotes, longer for macro)
- Serve stale cache on provider errors where possible
- Return partial payloads instead of hard failure when single provider fails

## Initial milestone (this iteration)
- Scaffold monorepo structure
- Implement production-grade shell + MMAP end-to-end
- Wire market overview endpoint + WebSocket stream
- Document setup and module status board

## Validation checklist
- `docker compose up --build` starts all services
- Frontend renders terminal shell with panel grid and command bar
- MMAP panel loads market snapshots from backend
- System remains functional when one or more external APIs fail
- Status board and setup documentation are updated
