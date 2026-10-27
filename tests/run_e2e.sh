#!/usr/bin/env bash
# Поднимает сервер с чистой базой (student/teacher, пароль secret123) и прогоняет браузерный тест.
set -euo pipefail
cd "$(dirname "$0")/.."
DATA="${CQ_E2E_DATA:-/tmp/cq-e2e-data}"
PORT="${CQ_E2E_PORT:-8097}"
SHOTS="${1:-/tmp/cq-shots}"
rm -rf "$DATA"
export CQ_DATA_DIR="$DATA" CQ_COOKIE_SECURE=0
python3 -c "
from app.db import init_db, connect, set_setting
import manage
init_db(); c = connect()
manage.create_user(c, 'teacher', 'teacher', 'Папа', 'secret123')
manage.create_user(c, 'student', 'student', 'Миша', 'secret123')
with c: set_setting(c, 'student_name', 'Миша')
"
python3 -m uvicorn app.main:app --port "$PORT" > "$DATA/server.log" 2>&1 &
SERVER=$!
trap 'kill $SERVER 2>/dev/null' EXIT
for _ in $(seq 30); do curl -sf "localhost:$PORT/healthz" >/dev/null && break; sleep 0.3; done
NODE_PATH="${NODE_PATH:-$(npm root -g)}" node tests/e2e.js "http://localhost:$PORT" "$SHOTS"
