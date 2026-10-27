"""Уведомления преподавателю в Telegram (необязательно: нужны CQ_TELEGRAM_TOKEN и CQ_TELEGRAM_CHAT_ID)."""
import json
import logging
import threading
import urllib.request

from . import config

log = logging.getLogger("codequest.notify")


def _send(text):
    """Отправка в Telegram; True — если ушло."""
    url = "https://api.telegram.org/bot%s/sendMessage" % config.TELEGRAM_TOKEN
    data = json.dumps({"chat_id": config.TELEGRAM_CHAT_ID, "text": text,
                       "disable_web_page_preview": True}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10).read()
        return True
    except Exception as e:  # уведомление не должно ломать сайт
        log.warning("telegram notify failed: %s", e)
        return False


def send_now(text):
    """Синхронная отправка (для сводки и кнопки «Отправить»). Без настроек Telegram — False."""
    if not (config.TELEGRAM_TOKEN and config.TELEGRAM_CHAT_ID):
        return False
    return _send(text)


def teacher(text, path=""):
    if not (config.TELEGRAM_TOKEN and config.TELEGRAM_CHAT_ID):
        return
    if path and config.BASE_URL:
        text += "\n" + config.BASE_URL + path
    threading.Thread(target=_send, args=(text,), daemon=True).start()
