#!/usr/bin/env bash
# Отдельный стенд: своя копия кода, своя база, свой порт.
#
#   sudo deploy/add_stage.sh [--dry-run] <имя> <домен> <порт> <ветка>
#
# Пример одобренного стенда:
#   sudo deploy/add_stage.sh stage stage.umedu.ru 8091 main
# Код ляжет в /opt/codequest-stage, база — в /var/lib/codequest-stage.
#
# До запуска на сервере нужны DNS, deploy key только на чтение и свободный порт.
# Что именно проверить — docs/STAGE.md. Повторный запуск ничего не затирает:
# env с паролями не переписывается, git и systemd приводятся к тем же настройкам.
set -euo pipefail

# shellcheck source=deploy/stage_lib.sh
source "$(dirname "$0")/stage_lib.sh"

DRY=0
ARGS=()
for arg in "$@"; do
  if [[ "$arg" == "--dry-run" ]]; then
    DRY=1
  else
    ARGS+=("$arg")
  fi
done

if [[ ${#ARGS[@]} -ne 4 ]]; then
  echo "Использование: deploy/add_stage.sh [--dry-run] <имя> <домен> <порт> <ветка>" >&2
  echo "Что нужно до запуска (DNS, ключ, порт) — в docs/STAGE.md" >&2
  exit 2
fi

NAME=${ARGS[0]}
DOMAIN=${ARGS[1]}
PORT=${ARGS[2]}
BRANCH=${ARGS[3]}
stage_validate "$NAME" "$DOMAIN" "$PORT" "$BRANCH"
stage_paths "$NAME"

NETWORK=$(stage_traefik_network)
ENTRY=$(stage_traefik_entry)
RESOLVER=$(stage_traefik_resolver)
ENV_TEXT=$(stage_render_env "$NAME" "$DOMAIN")
UNIT_TEXT=$(stage_render_unit "$NAME" "$PORT")
NGINX_TEXT=$(stage_render_nginx "$DOMAIN" "$PORT")
COMPOSE_TEXT=$(stage_render_compose "$NAME" "$DOMAIN" "$NETWORK" "$ENTRY" "$RESOLVER")
INSTANCE_TEXT=$(stage_render_instance "$NAME" "$DOMAIN" "$PORT" "$BRANCH")
REPO=$(stage_repo)

stage_print_plan() {
  cat <<EOF
# dry-run: на диск ничего не пишу и службы не трогаю.

Что нужно до запуска без --dry-run:
- DNS: запись ${DOMAIN} указывает на этот сервер (её заводит администратор, не скрипт).
- Deploy key только на чтение: ${DEPLOY_KEY} (GitHub → Deploy keys, Allow write access выключен), права 600.
- Порт ${PORT} свободен. Слушать его будет uvicorn на всех интерфейсах, снаружи его закрывает ufw:
  пускаем только сеть Docker Traefik (${NETWORK}).
- Сеть Docker «${NETWORK}» уже есть, у Traefik entrypoint «${ENTRY}» и certresolver «${RESOLVER}».
  Другие имена: CQ_TRAEFIK_NETWORK, CQ_TRAEFIK_ENTRYPOINT, CQ_TRAEFIK_CERTRESOLVER.

Куда что кладётся:
- код (clone по ключу, только чтение): ${CODE}
- env (повторный запуск не перезаписывает): ${ENV_FILE}
- база: ${DATA_DIR}
- служба ${SERVICE}, каталог работы — копия кода
- прокси nginx с метками Traefik: ${COMPOSE_FILE}

----- ${ENV_FILE} -----
${ENV_TEXT}
----- ${UNIT_FILE} -----
${UNIT_TEXT}
----- ${NGINX_FILE} -----
${NGINX_TEXT}
----- ${COMPOSE_FILE} -----
${COMPOSE_TEXT}
----- ${INSTANCE_FILE} -----
${INSTANCE_TEXT}

Команды, которые выполнились бы:
- пользователь codequest, если его ещё нет
- GIT_SSH_COMMAND с ключом ${DEPLOY_KEY}: clone или fetch ${REPO}, ветка ${BRANCH}
- venv и pip install -r requirements.txt, scripts/fetch_vendor.sh
- systemd enable и restart ${SERVICE}
- python manage.py migrate и seed_demo (повторно база демо не меняется)
- ufw allow из подсети сети ${NETWORK} на порт ${PORT}, если такого правила ещё нет
- docker compose -p ${SERVICE} -f ${COMPOSE_FILE} up -d
- проверка http://localhost:${PORT}/healthz
EOF
}

if [[ "$DRY" -eq 1 ]]; then
  stage_print_plan
  exit 0
fi

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Нужен root: скрипт создаёт пользователя, systemd, каталоги в /opt и /etc." >&2
  echo "Посмотреть план без изменений: deploy/add_stage.sh --dry-run ${NAME} ${DOMAIN} ${PORT} ${BRANCH}" >&2
  exit 1
fi

stage_need_key() {
  if [[ ! -f "$DEPLOY_KEY" ]]; then
    echo "Нет ключа ${DEPLOY_KEY}. Это deploy key репозитория только на чтение. Подробности: docs/STAGE.md" >&2
    exit 1
  fi
  local mode
  mode=$(stat -c '%a' "$DEPLOY_KEY")
  if [[ "$mode" != "600" && "$mode" != "400" ]]; then
    echo "Ключ ${DEPLOY_KEY} должен быть 600 или 400, сейчас ${mode}." >&2
    exit 1
  fi
}

stage_need_dns() {
  if ! getent hosts "$DOMAIN" >/dev/null; then
    echo "Домен ${DOMAIN} не резолвится. Сначала DNS, потом этот скрипт. Базу и код не трогаю." >&2
    exit 1
  fi
}

stage_need_port() {
  if ! command -v ss >/dev/null; then
    echo "Нет команды ss (пакет iproute2). Без неё не проверить, свободен ли порт ${PORT}." >&2
    exit 1
  fi
  if ss -ltn | awk '{print $4}' | grep -Eq "(^|:)${PORT}$"; then
    if systemctl is-active --quiet "$SERVICE"; then
      echo "Порт ${PORT} занят службой ${SERVICE} — так и задумано, перезапущу её."
      return 0
    fi
    echo "Порт ${PORT} уже занят не службой ${SERVICE}. Выберите другой." >&2
    exit 1
  fi
}

stage_need_key
stage_need_dns
stage_need_port

if ! id codequest >/dev/null 2>&1; then
  useradd --system --home-dir /var/lib/codequest --create-home --shell /usr/sbin/nologin codequest
fi
install -d -m 755 /etc/codequest
install -d -o codequest -g codequest -m 750 "$DATA_DIR"
install -d -o codequest -g codequest -m 755 /var/lib/codequest

export GIT_SSH_COMMAND="ssh -i ${DEPLOY_KEY} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
export GIT_TERMINAL_PROMPT=0
if ! git config --global --get-all safe.directory 2>/dev/null | grep -qx "$CODE"; then
  git config --global --add safe.directory "$CODE"
fi

if [[ ! -d "$CODE/.git" ]]; then
  if [[ -e "$CODE" ]]; then
    echo "Каталог ${CODE} уже есть, но это не git. Сам его не удаляю." >&2
    exit 1
  fi
  git ls-remote --exit-code --heads "$REPO" "$BRANCH" >/dev/null
  git clone --branch "$BRANCH" "$REPO" "$CODE"
else
  origin=$(git -C "$CODE" remote get-url origin)
  if [[ "$origin" != "$REPO" ]]; then
    echo "В ${CODE} другой origin: ${origin}. Ожидался ${REPO}." >&2
    exit 1
  fi
  git -C "$CODE" fetch origin
  git -C "$CODE" checkout -B "$BRANCH" "origin/${BRANCH}"
fi

if [[ ! -x "$CODE/.venv/bin/python" ]]; then
  runuser -u codequest -- python3 -m venv "$CODE/.venv"
fi
runuser -u codequest -- "$CODE/.venv/bin/pip" install -q -r "$CODE/requirements.txt"
if [[ -f "$CODE/scripts/fetch_vendor.sh" ]]; then
  bash "$CODE/scripts/fetch_vendor.sh"
fi
chmod -R a+rX "$CODE"

if [[ -f "$ENV_FILE" ]]; then
  echo "Env уже есть, не перезаписываю: ${ENV_FILE}"
else
  umask 027
  printf '%s\n' "$ENV_TEXT" > "$ENV_FILE"
  chown root:codequest "$ENV_FILE"
  chmod 640 "$ENV_FILE"
fi
printf '%s\n' "$UNIT_TEXT" > "$UNIT_FILE"
printf '%s\n' "$NGINX_TEXT" > "$NGINX_FILE"
printf '%s\n' "$COMPOSE_TEXT" > "$COMPOSE_FILE"
printf '%s\n' "$INSTANCE_TEXT" > "$INSTANCE_FILE"
chmod 644 "$UNIT_FILE" "$NGINX_FILE" "$COMPOSE_FILE" "$INSTANCE_FILE"

runuser -u codequest -- bash -c "set -a; . '$ENV_FILE'; set +a; exec '$CODE/.venv/bin/python' '$CODE/manage.py' migrate"
runuser -u codequest -- bash -c "set -a; . '$ENV_FILE'; set +a; exec '$CODE/.venv/bin/python' '$CODE/manage.py' seed_demo"

systemctl daemon-reload
systemctl enable "$SERVICE"
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
  echo "Служба ${SERVICE} не ответила на http://localhost:${PORT}/healthz. Журнал: journalctl -u ${SERVICE}" >&2
  exit 1
fi

if ! command -v ufw >/dev/null; then
  echo "Нет ufw. Служба уже работает на localhost:${PORT}, но правило для сети Traefik не добавлено." >&2
  exit 1
fi
if ! docker network inspect "$NETWORK" >/dev/null 2>&1; then
  echo "Нет сети Docker «${NETWORK}». Сайт на localhost:${PORT} уже отвечает. Создайте сеть и запустите скрипт ещё раз." >&2
  exit 1
fi
SUBNET=$(docker network inspect "$NETWORK" --format '{{(index .IPAM.Config 0).Subnet}}')
if [[ -z "$SUBNET" ]]; then
  echo "У сети ${NETWORK} не вижу подсеть, правило ufw не добавил." >&2
  exit 1
fi
if ufw status | grep -F "codequest-${NAME}" >/dev/null; then
  echo "ufw: правило codequest-${NAME} уже есть."
else
  ufw allow from "$SUBNET" to any port "$PORT" proto tcp comment "codequest-${NAME}"
fi
if ! ufw status | grep -q "Status: active"; then
  echo "ufw выключен: правило сохранено, но порт ${PORT} пока открыт на всех интерфейсах. Включать ufw скрипт не станет."
fi

if ! command -v docker >/dev/null; then
  echo "Нет docker. Прокси с меткой Traefik не поднял." >&2
  exit 1
fi
docker compose -p "$SERVICE" -f "$COMPOSE_FILE" up -d

echo "Стенд ${DOMAIN} запущен: служба ${SERVICE}, порт ${PORT}, код ${CODE}."
echo "Демо-вход и повторный seed — в выводе выше. Регистрация на стенде открытая."
