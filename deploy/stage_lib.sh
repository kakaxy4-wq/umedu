# Общие функции стенда. Подключают deploy/add_stage.sh и deploy/update_stage.sh.
# Сами по себе ничего не делают: только проверки и текст файлов.
# shellcheck shell=bash

stage_repo() {
  printf '%s\n' "git@github.com:kakaxy4-wq/umedu.git"
}

stage_valid_name() {
  local name=$1
  [[ "$name" =~ ^[a-z][a-z0-9-]{0,20}$ ]] || return 1
  [[ "$name" != *- ]] || return 1
}

stage_valid_domain() {
  local domain=$1
  [[ "$domain" =~ ^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$ ]] || return 1
}

stage_valid_port() {
  local port=$1
  [[ "$port" =~ ^[0-9]+$ ]] || return 1
  [[ "$port" -ge 1024 && "$port" -le 65535 ]] || return 1
}

stage_valid_branch() {
  local branch=$1
  [[ "$branch" =~ ^[A-Za-z0-9._/-]+$ ]] || return 1
  [[ "$branch" != *..* && "$branch" != -* && "$branch" != */ && "$branch" != /* ]] || return 1
}

stage_validate() {
  local name=$1 domain=$2 port=$3 branch=$4
  stage_valid_name "$name" || { echo "Имя — латиница в нижнем регистре, цифры и дефис, не длиннее 21: $name" >&2; return 1; }
  stage_valid_domain "$domain" || { echo "Домен выглядит неверно: $domain" >&2; return 1; }
  stage_valid_port "$port" || { echo "Порт — число от 1024 до 65535: $port" >&2; return 1; }
  stage_valid_branch "$branch" || { echo "Ветка содержит недопустимые символы: $branch" >&2; return 1; }
}

# Каталоги одного стенда. Имя stage даёт код в /opt/codequest-stage.
stage_paths() {
  local name=$1
  CODE="/opt/codequest-${name}"
  ENV_FILE="/etc/codequest/${name}.env"
  UNIT_FILE="/etc/systemd/system/codequest-${name}.service"
  DATA_DIR="/var/lib/codequest-${name}"
  NGINX_FILE="/etc/codequest/${name}.nginx.conf"
  COMPOSE_FILE="/etc/codequest/${name}.proxy.yml"
  INSTANCE_FILE="/etc/codequest/${name}.instance"
  SERVICE="codequest-${name}"
  DEPLOY_KEY="/etc/codequest/deploy_key"
  : "$CODE" "$ENV_FILE" "$UNIT_FILE" "$DATA_DIR" "$NGINX_FILE" "$COMPOSE_FILE" "$INSTANCE_FILE" "$SERVICE" "$DEPLOY_KEY"
}

stage_render_env() {
  local name=$1 domain=$2
  cat <<EOF
# Стенд ${domain}. Создаёт deploy/add_stage.sh и больше не перезаписывает.
CQ_STAGE=1
CQ_THEME=public
CQ_UMEDU2=1
CQ_SIGNUP=open
CQ_PARENT_BOT=0
CQ_PURGE_INACTIVE=0
CQ_SITE_NAME="umedu · стенд"
CQ_BASE_URL=https://${domain}
CQ_DATA_DIR=/var/lib/codequest-${name}
CQ_SUBJECTS=python,russian
CQ_COOKIE_SECURE=1
CQ_TIMEZONE=Europe/Moscow
CQ_ENV_FILE=/etc/codequest/${name}.env
EOF
}

stage_render_unit() {
  local name=$1 port=$2
  cat <<EOF
[Unit]
Description=umedu стенд codequest-${name}
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=codequest
Group=codequest
WorkingDirectory=/opt/codequest-${name}
EnvironmentFile=/etc/codequest/${name}.env
ExecStart=/opt/codequest-${name}/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${port}
Restart=on-failure
RestartSec=2
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF
}

stage_render_nginx() {
  local domain=$1 port=$2
  cat <<EOF
server {
    listen 80;
    server_name ${domain};
    location / {
        proxy_pass http://host.docker.internal:${port};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
EOF
}

stage_render_compose() {
  local name=$1 domain=$2 network=$3 entry=$4 resolver=$5
  cat <<EOF
# Прокси стенда: Traefik (сеть ${network}) отдаёт HTTPS, nginx ходит на uvicorn на хосте.
services:
  proxy:
    image: nginx:1.27-alpine
    restart: unless-stopped
    extra_hosts:
      - "host.docker.internal:host-gateway"
    volumes:
      - /etc/codequest/${name}.nginx.conf:/etc/nginx/conf.d/default.conf:ro
    networks:
      - traefik
    labels:
      - traefik.enable=true
      - traefik.docker.network=${network}
      - traefik.http.routers.codequest-${name}.rule=Host(\`${domain}\`)
      - traefik.http.routers.codequest-${name}.entrypoints=${entry}
      - traefik.http.routers.codequest-${name}.tls=true
      - traefik.http.routers.codequest-${name}.tls.certresolver=${resolver}
      - traefik.http.services.codequest-${name}.loadbalancer.server.port=80

networks:
  traefik:
    external: true
    name: ${network}
EOF
}

stage_render_instance() {
  local name=$1 domain=$2 port=$3 branch=$4
  cat <<EOF
NAME=${name}
DOMAIN=${domain}
PORT=${port}
BRANCH=${branch}
CODE=/opt/codequest-${name}
EOF
}

stage_load_instance() {
  local file=$1 line key val
  [[ -f "$file" ]] || return 1
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ "$line" == *=* ]] || continue
    key=${line%%=*}
    val=${line#*=}
    # shellcheck disable=SC2034
    case "$key" in
      NAME) INST_NAME=$val ;;
      DOMAIN) INST_DOMAIN=$val ;;
      PORT) INST_PORT=$val ;;
      BRANCH) INST_BRANCH=$val ;;
      CODE) INST_CODE=$val ;;
    esac
  done < "$file"
}

stage_traefik_network() { printf '%s\n' "${CQ_TRAEFIK_NETWORK:-traefik}"; }
stage_traefik_entry() { printf '%s\n' "${CQ_TRAEFIK_ENTRYPOINT:-websecure}"; }
stage_traefik_resolver() { printf '%s\n' "${CQ_TRAEFIK_CERTRESOLVER:-letsencrypt}"; }
