#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "[smoke] docker is required"
  exit 1
fi

if [ ! -f .env ] && [ -f .env.example ]; then
  cp .env.example .env
  echo "[smoke] .env created from .env.example"
fi

cleanup() {
  if [ "${KEEP_UP:-0}" != "1" ]; then
    echo "[smoke] stopping stack"
    docker compose down --remove-orphans >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

echo "[smoke] building and starting stack"
docker compose up --build -d

wait_for_http() {
  local name="$1"
  local url="$2"
  local timeout_seconds="${3:-180}"
  local elapsed=0

  while [ "$elapsed" -lt "$timeout_seconds" ]; do
    if curl -fsS "$url" >/dev/null 2>&1; then
      echo "[smoke] ok: $name ($url)"
      return 0
    fi
    sleep 3
    elapsed=$((elapsed + 3))
  done

  echo "[smoke] timeout waiting for $name ($url)"
  return 1
}

wait_for_http "backend readiness" "http://localhost/api/v1/health/ready" 240
wait_for_http "frontend" "http://localhost" 180
wait_for_http "market overview API" "http://localhost/api/v1/market/overview" 180

echo "[smoke] ✅ production-like local smoke check passed"
if [ "${KEEP_UP:-0}" = "1" ]; then
  echo "[smoke] stack kept running (KEEP_UP=1)"
fi
