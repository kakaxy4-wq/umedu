#!/usr/bin/env bash
# Обновить стенд: fetch → тесты на кандидате → переключение копии → рестарт → healthz.
#
#   sudo deploy/update_stage.sh [--dry-run] [--name имя] [ветка]
#
# Имя по умолчанию — stage (файл /etc/codequest/stage.instance пишет add_stage.sh).
# Ветка по умолчанию — та, что записана в этом файле. Тесты идут в отдельном worktree
# и со своей временной базой. Живой каталог переключается только если pytest прошёл.
set -euo pipefail

# shellcheck source=deploy/stage_lib.sh
source "$(dirname "$0")/stage_lib.sh"

DRY=0
NAME="stage"
BRANCH=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY=1; shift ;;
    --name)
      [[ $# -ge 2 ]] || { echo "После --name нужно имя стенда" >&2; exit 2; }
      NAME=$2
      shift 2
      ;;
    -*)
      echo "Неизвестный аргумент: $1" >&2
      exit 2
      ;;
    *)
      if [[ -n "$BRANCH" ]]; then
        echo "Ветка уже задана ($BRANCH), лишнее: $1" >&2
        exit 2
      fi
      BRANCH=$1
      shift
      ;;
  esac
done

stage_valid_name "$NAME" || { echo "Неверное имя стенда: $NAME" >&2; exit 2; }
if [[ -n "$BRANCH" ]]; then
  stage_valid_branch "$BRANCH" || { echo "Неверная ветка: $BRANCH" >&2; exit 2; }
fi
stage_paths "$NAME"

INST_NAME="" INST_DOMAIN="" INST_PORT="" INST_BRANCH="" INST_CODE=""
if [[ -f "$INSTANCE_FILE" ]]; then
  stage_load_instance "$INSTANCE_FILE"
fi
: "$INST_NAME"
if [[ -z "$BRANCH" ]]; then
  BRANCH=$INST_BRANCH
fi
if [[ -n "$INST_PORT" ]]; then
  PORT=$INST_PORT
else
  PORT=""
fi
if [[ -n "$INST_CODE" ]]; then
  CODE=$INST_CODE
fi

if [[ "$DRY" -eq 1 ]]; then
  cat <<EOF
# dry-run: fetch, тесты, переключение и рестарт не запускаю.

Стенд: ${NAME}
Код: ${CODE}
Файл экземпляра: ${INSTANCE_FILE}
Ветка: ${BRANCH:-не задана — укажите аргументом или полем BRANCH в файле экземпляра}
Порт healthz: ${PORT:-неизвестен, пока нет файла экземпляра}

Порядок без --dry-run:
1. git fetch origin (ключ ${DEPLOY_KEY}, только чтение)
2. worktree на origin/<ветка>, pytest -q со временной базой — живой каталог ещё старый
3. если тесты зелёные: checkout этой ветки в ${CODE}, pip install, fetch_vendor.sh
4. systemctl restart ${SERVICE}
5. curl http://localhost:<порт>/healthz

Если pytest падает, копия стенда и служба остаются как были.
EOF
  exit 0
fi

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Нужен root. План: deploy/update_stage.sh --dry-run ${BRANCH:+$BRANCH}" >&2
  exit 1
fi
if [[ ! -f "$INSTANCE_FILE" ]]; then
  echo "Нет ${INSTANCE_FILE}. Сначала deploy/add_stage.sh." >&2
  exit 1
fi
if [[ -z "$BRANCH" || -z "$PORT" ]]; then
  echo "В ${INSTANCE_FILE} нет ветки или порта." >&2
  exit 1
fi
stage_valid_branch "$BRANCH"
stage_valid_port "$PORT"
if [[ ! -d "$CODE/.git" ]]; then
  echo "Нет копии кода: ${CODE}" >&2
  exit 1
fi
if [[ ! -f "$DEPLOY_KEY" ]]; then
  echo "Нет ключа ${DEPLOY_KEY}." >&2
  exit 1
fi

export GIT_SSH_COMMAND="ssh -i ${DEPLOY_KEY} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
export GIT_TERMINAL_PROMPT=0
if ! git config --global --get-all safe.directory 2>/dev/null | grep -qx "$CODE"; then
  git config --global --add safe.directory "$CODE"
fi

git -C "$CODE" fetch origin
git -C "$CODE" rev-parse --verify "origin/${BRANCH}^{commit}" >/dev/null

CANDIDATE=$(mktemp -d)
rmdir "$CANDIDATE"
DATA_TMP=$(mktemp -d)
cleanup() {
  git -C "$CODE" worktree remove --force "$CANDIDATE" >/dev/null 2>&1 || rm -rf "$CANDIDATE"
  rm -rf "$DATA_TMP"
}
trap cleanup EXIT

git -C "$CODE" worktree add --detach "$CANDIDATE" "origin/${BRANCH}"
if [[ ! -x "$CODE/.venv/bin/pip" ]]; then
  echo "Нет venv в ${CODE}. Сначала add_stage.sh." >&2
  exit 1
fi
"$CODE/.venv/bin/pip" install -q -r "$CANDIDATE/requirements.txt" -r "$CANDIDATE/requirements-dev.txt"
echo "Тесты кандидата ${BRANCH} (живая копия пока не переключена)…"
if ! (
  cd "$CANDIDATE"
  env -i PATH="$PATH" HOME="${HOME:-/root}" LANG="${LANG:-C.UTF-8}" \
    CQ_ENV_FILE="${CANDIDATE}/.env.missing" \
    CQ_DATA_DIR="$DATA_TMP" \
    CQ_COOKIE_SECURE=0 \
    "$CODE/.venv/bin/python" -m pytest -q --tb=line
); then
  echo "Тесты не прошли. Стенд не переключал." >&2
  exit 1
fi

git -C "$CODE" checkout -B "$BRANCH" "origin/${BRANCH}"
"$CODE/.venv/bin/pip" install -q -r "$CODE/requirements.txt"
if [[ -f "$CODE/scripts/fetch_vendor.sh" ]]; then
  bash "$CODE/scripts/fetch_vendor.sh"
fi
chmod -R a+rX "$CODE"

# ветка в файле экземпляра — чтобы следующий запуск без аргумента взял её же
stage_render_instance "$NAME" "${INST_DOMAIN}" "$PORT" "$BRANCH" > "$INSTANCE_FILE"

systemctl restart "$SERVICE"
ready=0
for _ in $(seq 1 30); do
  if curl -fsS --max-time 2 "http://localhost:${PORT}/healthz" >/dev/null; then
    ready=1
    break
  fi
  sleep 0.5
done
if [[ "$ready" -ne 1 ]]; then
  echo "После рестарта healthz не ответил на порту ${PORT}." >&2
  exit 1
fi
echo "Стенд ${NAME} на ветке ${BRANCH}, healthz отвечает."
