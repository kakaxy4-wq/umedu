"""Отчёт родителю в Telegram раз в неделю.

Включается двумя настройками: CQ_TELEGRAM_TOKEN (бот из @BotFather) и CQ_PARENT_BOT=1. Флаг отдельный, потому что
бот читает входящие сообщения (getUpdates): если тот же токен ещё где-то читает обновления, они начнут их отнимать
друг у друга.

Подключение: в кабинете родителя кнопка «Подключить Telegram» выдаёт одноразовую ссылку t.me/<бот>?start=<код>
(живёт час). Родитель жмёт «Start» — бот запоминает его чат. /stop или кнопка в кабинете — отключить.
Отчёт уходит по воскресеньям в 19:00 вместе со сводкой преподавателю (weekly.scheduler); отправка отмечается в
settings, чтобы не повторяться после перезапуска.
"""
import asyncio
import json
import logging
import secrets
import time
import urllib.request
from datetime import datetime, timedelta

from . import config, game, weekly
from .db import connect, get_setting, set_setting

log = logging.getLogger("codequest.parent_bot")

CODE_TTL = timedelta(hours=1)
POLL_TIMEOUT = 25
_me = {}


def enabled():
    return config.PARENT_BOT and bool(config.TELEGRAM_TOKEN)


def call(method, **params):
    """Запрос к Bot API. None — если не получилось (ошибка не должна ронять сайт; токен в лог не пишем)."""
    url = "https://api.telegram.org/bot%s/%s" % (config.TELEGRAM_TOKEN, method)
    req = urllib.request.Request(url, data=json.dumps(params).encode(), headers={"Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=params.get("timeout", 0) + 15).read())
    except Exception as e:
        log.warning("telegram %s failed: %s %s", method, type(e).__name__, getattr(e, "code", ""))
        return None


def send(chat_id, text):
    r = call("sendMessage", chat_id=chat_id, text=text, disable_web_page_preview=True)
    return bool(r and r.get("ok"))


def bot_username():
    if "username" not in _me:
        r = call("getMe")
        if r and r.get("ok"):
            _me["username"] = r["result"]["username"]
    return _me.get("username")


# ------------------------------------------------------------------ подключение
def new_link(conn, pid):
    """Одноразовая ссылка на бота для родителя pid или None, если бот недоступен. Вызывать внутри `with conn:`."""
    username = bot_username()
    if not username:
        return None
    code = secrets.token_urlsafe(12)
    conn.execute("UPDATE parents SET tg_code = ?, tg_code_at = ? WHERE id = ?", (code, game.now_iso(), pid))
    return "https://t.me/%s?start=%s" % (username, code)


def disconnect(conn, pid):
    conn.execute("UPDATE parents SET tg_chat_id = NULL, tg_code = NULL WHERE id = ?", (pid,))


def handle(conn, update):
    """Одно обновление от Telegram → (chat_id, ответ) или None. Отвечаем только в личных чатах."""
    msg = update.get("message") or {}
    chat = msg.get("chat") or {}
    if chat.get("type") != "private" or "id" not in chat:
        return None
    cid, text = str(chat["id"]), (msg.get("text") or "").strip()
    if text.startswith("/start ") and text[7:].strip():
        row = conn.execute("SELECT id, display_name, tg_code_at FROM parents WHERE tg_code = ? AND active = 1",
                           (text[7:].strip(),)).fetchone()
        if not row or datetime.fromisoformat(row["tg_code_at"]) < config.now() - CODE_TTL:
            return cid, ("Ссылка устарела. Откройте кабинет родителя и нажмите «Подключить Telegram» ещё раз: "
                         "%s/family" % config.BASE_URL)
        with conn:
            conn.execute("UPDATE parents SET tg_chat_id = NULL WHERE tg_chat_id = ?", (cid,))
            conn.execute("UPDATE parents SET tg_chat_id = ?, tg_code = NULL WHERE id = ?", (cid, row["id"]))
        return cid, ("Готово, %s! По воскресеньям вечером пришлю короткий отчёт: сколько дней ребёнок занимался, "
                     "что решил и какой прогноз ОГЭ. Отключить — команда /stop или кнопка в кабинете." % row["display_name"])
    if text == "/stop":
        with conn:
            n = conn.execute("UPDATE parents SET tg_chat_id = NULL WHERE tg_chat_id = ?", (cid,)).rowcount
        return cid, "Отчёты отключены." if n else "Отчёты и так не подключены."
    return cid, ("Я присылаю родителям еженедельный отчёт о занятиях на сайте «%s». Подключиться можно в кабинете "
                 "родителя: %s/family" % (config.SITE_NAME, config.BASE_URL))


def poll_once(conn):
    """Забрать новые сообщения и ответить. Номер последнего обновления — в settings."""
    offset = int(get_setting(conn, "tg_offset") or 0)
    r = call("getUpdates", offset=offset, timeout=POLL_TIMEOUT, allowed_updates=["message"])
    if not r or not r.get("ok"):
        return False
    for u in r["result"]:
        with conn:
            set_setting(conn, "tg_offset", str(u["update_id"] + 1))
        try:
            reply = handle(conn, u)
            if reply:
                send(*reply)
        except Exception:
            log.exception("telegram update failed")
    return True


async def poller():
    while True:
        conn = connect()
        try:
            ok = await asyncio.to_thread(poll_once, conn)
        except Exception:
            log.exception("telegram poll failed")
            ok = False
        finally:
            conn.close()
        if not ok:
            await asyncio.sleep(30)        # сеть или токен — не долбим API


# ------------------------------------------------------------------ отчёт
def _plural(n, one, few, many):
    return weekly._plural(n, one, few, many)


def child_text(w):
    st = w["student"]
    lines = ["👤 %s" % st["display_name"]]
    if not w["days"]:
        lines.append("😴 На этой неделе занятий не было. Хватит 10–15 минут в день — «План на сегодня» в кабинете ученика.")
    else:
        lines.append("• Дней с занятиями: %d из 7" % w["days"])
        if w["tasks"]:
            lines.append("• Решено задач по программированию: %d" % w["tasks"])
        if w["oge"]:
            lines.append("• Тренажёр ОГЭ: %s" % _plural(w["oge"], "вариант", "варианта", "вариантов"))
        if w["ru"][0]:
            lines.append("• Русский: %s, верно %d%%" % (_plural(w["ru"][0], "ответ", "ответа", "ответов"), w["ru"][1]))
        if w["lessons"]:
            lines.append("• Пройдены уроки: " + ", ".join(map(str, w["lessons"])))
        for cid, right, total in w["checks"]:
            lines.append("• Проверка: %d из %d" % (right, total))
    if w["fc"]:
        lines.append("🎯 Прогноз ОГЭ по информатике: %d из %d баллов — «%d»" % (w["fc"]["points"], w["fc"]["max"], w["fc"]["grade"]))
    if config.BASE_URL:
        lines.append("Подробнее: %s/family/child/%d" % (config.BASE_URL, st["id"]))
    return "\n".join(lines)


def report(conn, pid, today=None):
    """Текст отчёта для родителя или None, если детей нет."""
    from . import family
    today = today or config.today()
    since = (today - timedelta(days=6)).isoformat()
    kids = family.children(conn, pid)
    if not kids:
        return None
    head = "📬 %s: неделя %s — %s" % (config.SITE_NAME, (today - timedelta(days=6)).strftime("%d.%m"), today.strftime("%d.%m"))
    out = "\n\n".join([head] + [child_text(weekly.student_week(conn, st, since)) for st in kids])
    return out if len(out) <= 4000 else out[:3990] + "\n…"


def send_reports(conn):
    """Разослать отчёты всем подключённым родителям. Возвращает число отправленных."""
    sent = 0
    for p in conn.execute("SELECT id, tg_chat_id FROM parents WHERE tg_chat_id IS NOT NULL AND active = 1").fetchall():
        text = report(conn, p["id"])
        if text and send(p["tg_chat_id"], text):
            sent += 1
        time.sleep(0.05)                   # лимит Telegram — 30 сообщений в секунду
    return sent


def send_if_due():
    if not enabled():
        return False
    conn = connect()
    try:
        now = config.now()
        if not weekly.due(now, get_setting(conn, "parent_weekly_sent")):
            return False
        with conn:
            set_setting(conn, "parent_weekly_sent", weekly.week_key(now.date()))
        send_reports(conn)
        return True
    finally:
        conn.close()
