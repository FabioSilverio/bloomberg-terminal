#!/bin/sh
set -eu

MAX_RETRIES="${DB_MIGRATION_MAX_RETRIES:-30}"
RETRY_DELAY_SECONDS="${DB_MIGRATION_RETRY_DELAY_SECONDS:-2}"

attempt=1
while [ "$attempt" -le "$MAX_RETRIES" ]; do
  echo "[backend] running migrations (attempt ${attempt}/${MAX_RETRIES})..."
  if alembic upgrade head; then
    echo "[backend] migrations up to date"
    break
  fi

  if [ "$attempt" -ge "$MAX_RETRIES" ]; then
    echo "[backend] migrations failed after ${MAX_RETRIES} attempts"
    exit 1
  fi

  echo "[backend] migration attempt failed, retrying in ${RETRY_DELAY_SECONDS}s"
  sleep "$RETRY_DELAY_SECONDS"
  attempt=$((attempt + 1))
done

echo "[backend] starting API"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
