# deploy/ — systemd-юниты для экземпляров на одном сервере

## Удаление неактивных аккаунтов: `codequest-purge@.service` + `codequest-purge@.timer`

Политика (/privacy) обещает удалять аккаунт через год после последнего занятия. Это делает
`python manage.py purge-inactive --apply`: удаляет учеников без занятий больше года и кабинеты родителей,
у которых не осталось детей. Без `--apply` команда только печатает список и базу не меняет.

### Важно: сайт уже делает это сам

Процесс сайта (`app/main.py` → `account.scheduler`) раз в сутки запускает ту же чистку, если в окружении
**не** задано `CQ_PURGE_INACTIVE=0`. По умолчанию она **включена на каждом экземпляре**, который запущен из этого кода.
Таймер нужен, если чистку хочется видеть отдельной задачей: время после бэкапа, сухой прогон и итог в журнале,
`systemctl list-timers`. Включайте **что-то одно**: таймер и `CQ_PURGE_INACTIVE=0` в env экземпляра — или ничего не ставить.

### Влияние на другие экземпляры (код общий: umedu, КодКвест, ХимЛаб)

- Юнит — шаблон, ставится **поимённо**: `codequest-purge@umedu.timer` трогает только `/etc/codequest/umedu.env`
  и его базу. На КодКвест и ХимЛаб таймер сам не попадёт.
- Но встроенная чистка в процессе сайта работает на **всех** экземплярах, где нет `CQ_PURGE_INACTIVE=0`.
  Для КодКвеста и ХимЛаба (репетиторские ученики, на ХимЛабе — оплаты и расписание) годовой срок может не подходить:
  ученик, который вернулся через год, потеряет историю. Решите для каждого экземпляра и, если не нужно,
  задайте там `CQ_PURGE_INACTIVE=0`.
- Удаление необратимо, восстановить можно только из бэкапа (их хранится 30).

### Установка (на сервере, от root; пример для umedu)

```bash
cd /opt/codequest
# 1. Сухой прогон — кого удалило бы сейчас (база не меняется):
systemd-run --pipe --wait --uid=codequest --working-directory=/opt/codequest \
  -p EnvironmentFile=/etc/codequest/umedu.env .venv/bin/python manage.py purge-inactive

# 2. Юниты:
install -m 644 deploy/codequest-purge@.service deploy/codequest-purge@.timer /etc/systemd/system/
systemctl daemon-reload

# 3. Выключить встроенную чистку у этого экземпляра, чтобы не было двух механизмов:
echo 'CQ_PURGE_INACTIVE=0' >> /etc/codequest/umedu.env
systemctl restart codequest-umedu

# 4. Включить таймер и проверить:
systemctl enable --now codequest-purge@umedu.timer
systemctl list-timers 'codequest-purge@*'
```

Разовый запуск вручную: `systemctl start codequest-purge@umedu.service`, итог — `journalctl -u codequest-purge@umedu`.
Сначала в журнале будет список (сухой прогон), затем строка «Удалено: учеников N, родителей M» или «Некого удалять».

Откат: `systemctl disable --now codequest-purge@umedu.timer`, убрать `CQ_PURGE_INACTIVE=0` из env
и перезапустить сервис — чистка снова пойдёт внутри сайта.

Пути по умолчанию (`/opt/codequest` — каталог с кодом и `.venv`, `/etc/codequest/%i.env`, `/var/lib/codequest-%i`) — поправьте под свою установку;
в `codequest-purge@.service` они заданы явно. Для Docker-установки (SELF-HOSTING.md) эти юниты
не нужны — там работает встроенная чистка.
