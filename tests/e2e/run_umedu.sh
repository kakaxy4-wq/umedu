#!/usr/bin/env bash
# Поднимает uvicorn с настройками стенда и прогоняет tests/e2e/umedu.js.
# В обычный pytest не входит. Нужен Chrome (переменная CHROME, иначе /usr/local/bin/google-chrome).
set -euo pipefail
cd "$(dirname "$0")/../.."
DATA="${CQ_E2E_DATA:-/tmp/umedu-e2e-data}"
PORT="${CQ_E2E_PORT:-8098}"
SHOTS="${1:-/tmp/umedu-e2e-shots}"
rm -rf "$DATA"
mkdir -p "$DATA" "$SHOTS"

if [[ ! -f app/static/vendor/codemirror/codemirror.js || ! -f app/static/vendor/fonts/golos-text-cyrillic-wght-normal.woff2 ]]; then
  bash scripts/fetch_vendor.sh
fi

PW="${CQ_E2E_NODE:-/tmp/umedu-pw}"
if [[ ! -d "$PW/node_modules/playwright-core" ]]; then
  npm install --prefix "$PW" playwright-core
fi

export CQ_DATA_DIR="$DATA" CQ_COOKIE_SECURE=0 CQ_STAGE=1 CQ_THEME=public CQ_UMEDU2=1 \
  CQ_SIGNUP=open CQ_PARENT_BOT=0 CQ_PURGE_INACTIVE=0 CQ_ENV_FILE="$DATA/no.env" \
  CQ_SITE_NAME="umedu · стенд"
python3 -m uvicorn app.main:app --host localhost --port "$PORT" > "$DATA/server.log" 2>&1 &
SERVER=$!
cleanup() { kill "$SERVER" 2>/dev/null || true; }
trap cleanup EXIT
for _ in $(seq 1 50); do
  curl -sf "http://localhost:${PORT}/healthz" >/dev/null && break
  sleep 0.3
done
curl -sf "http://localhost:${PORT}/healthz" >/dev/null

NODE_PATH="${PW}/node_modules${NODE_PATH:+:$NODE_PATH}" node tests/e2e/umedu.js "http://localhost:${PORT}" "$SHOTS"
