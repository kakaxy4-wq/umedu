# Свой сайт: для школы, кружка или репетитора

Один экземпляр — один преподаватель и его ученики (до 30). Данные хранятся в одном файле SQLite на вашем сервере.

## Docker (проще всего)

Нужен сервер с Docker и домен, направленный на него.

```bash
git clone <адрес репозитория> umedu && cd umedu
cp .env.example .env            # впишите CQ_BASE_URL и CQ_SITE_NAME
docker compose up -d --build
docker compose run --rm web python manage.py init     # учётка преподавателя: пароль вводите сами
```

Сайт слушает порт 8000. HTTPS включите в своём обратном прокси (Caddy, nginx, Traefik) — без HTTPS вход не работает,
пока не поставить `CQ_COOKIE_SECURE=0` (только для проверки на своём компьютере).

Обновление: `git pull && docker compose up -d --build`. База — в томе `umedu-data`, переживает обновления.
Резервная копия: `docker compose exec web python manage.py backup` — копия ляжет в `/data/backups/` внутри тома.

## Без Docker

Python 3.12:

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
bash scripts/fetch_vendor.sh
CQ_DATA_DIR=/var/lib/umedu python manage.py init
CQ_DATA_DIR=/var/lib/umedu uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Запуск как службы — любой менеджер процессов (systemd, supervisor).

## Настройки (`.env`)

| Переменная | Что делает |
|---|---|
| `CQ_SITE_NAME`, `CQ_BRAND_EMOJI` | название и значок |
| `CQ_BASE_URL` | адрес сайта, для ссылок родителям |
| `CQ_SUBJECTS` | предметы: `python`, `russian`, `chemistry` (через запятую) |
| `CQ_THEME` | `public` — нейтральные игровые слова и лендинг `/welcome` |
| `CQ_SIGNUP` | `1` — ученики регистрируются сами по коду приглашения |
| `CQ_OPERATOR` | кто оператор персональных данных — для страницы `/privacy` |
| `CQ_CONTACT` | ссылка «связаться» на лендинге |
| `CQ_SOURCE_URL` | ссылка на исходный код вашей версии — по AGPL-3.0 её нужно показывать, если вы меняли код |
| `CQ_TIMEZONE` | часовой пояс, по умолчанию `Europe/Moscow` |

## Персональные данные

Вы — оператор данных своих учеников. Страница `/privacy` — шаблон: проверьте его и укажите себя в `CQ_OPERATOR`.
Кабинет родителя спрашивает согласие и хранит его дату и редакцию.
