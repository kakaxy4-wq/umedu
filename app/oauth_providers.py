"""Внешний вход: код авторизации забирает сервер, в браузер токен не попадает.

Сейчас подключён Яндекс ID. VK ID сюда же: класс с теми же тремя методами
(enabled, authorize_url, fetch_identity) и строка в PROVIDERS. Пока VK не делаем.

Почта для привязки — только default_email. Яндекс отдаёт её как почту по умолчанию
при праве login:email; список emails для входа не используем.
"""
import json
import re
import urllib.error
import urllib.parse
import urllib.request

from . import config

AUTHORIZE_URL = "https://oauth.yandex.ru/authorize"
TOKEN_URL = "https://oauth.yandex.ru/token"
INFO_URL = "https://login.yandex.ru/info?format=json"
SCOPES = "login:info login:email"          # только то, что разрешено приложению; даты рождения нет
_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_SUBJECT_RE = re.compile(r"[A-Za-z0-9._:-]{1,128}")
_TIMEOUT = 10


class ProviderError(Exception):
    """Провайдер не ответил. Текст исключения наружу не показываем — там могут быть подробности Яндекса."""


class Identity:
    def __init__(self, provider, subject, email, display_name):
        self.provider = provider
        self.subject = subject          # стабильный id у провайдера
        self.email = email              # подтверждённая почта или None
        self.display_name = display_name


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Код и секрет не должны уехать на другой хост вслед за редиректом."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def _cfg(name):
    return (getattr(config, name, "") or "").strip()


def _read_json(req):
    try:
        with _OPENER.open(req, timeout=_TIMEOUT) as resp:
            raw = resp.read(65536)
    except urllib.error.HTTPError as exc:
        exc.close()
        raise ProviderError("http") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ProviderError("network") from exc
    try:
        data = json.loads(raw.decode())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderError("json") from exc
    if not isinstance(data, dict):
        raise ProviderError("shape")
    return data


def exchange_code(code, client_id, client_secret):
    """POST https://oauth.yandex.ru/token — код на access_token. Тело уходит только на сервер Яндекса."""
    body = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=body, method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"})
    data = _read_json(req)
    token = data.get("access_token")
    if data.get("error") or not isinstance(token, str) or not token:
        raise ProviderError("token")
    return token


def fetch_userinfo(token):
    """GET https://login.yandex.ru/info — токен в заголовке, не в query."""
    req = urllib.request.Request(INFO_URL, headers={"Authorization": "OAuth " + token, "Accept": "application/json"})
    return _read_json(req)


def verified_email(info):
    """default_email — почта по умолчанию, которую Яндекс отдаёт при login:email. Другие адреса не берём."""
    raw = info.get("default_email") if isinstance(info, dict) else None
    if not isinstance(raw, str):
        return None
    email = raw.strip().lower()
    if not email or len(email) > 254 or not _EMAIL_RE.fullmatch(email):
        return None
    return email


def _display_name(info, email):
    for key in ("real_name", "display_name", "first_name"):
        val = info.get(key)
        if isinstance(val, str):
            text = " ".join(val.split())[:40]
            if text:
                return text
    if email:
        local = email.split("@", 1)[0][:30]
        if local:
            return local
    return "Ученик"


class YandexProvider:
    id = "yandex"
    button = "Войти с Яндекс ID"

    def enabled(self):
        return bool(_cfg("YANDEX_CLIENT_ID") and _cfg("YANDEX_CLIENT_SECRET"))

    def authorize_url(self, state, redirect_uri):
        query = urllib.parse.urlencode({
            "response_type": "code",
            "client_id": _cfg("YANDEX_CLIENT_ID"),
            "redirect_uri": redirect_uri,
            "scope": SCOPES,
            "state": state,
        }, quote_via=urllib.parse.quote)
        return AUTHORIZE_URL + "?" + query

    def fetch_identity(self, code, redirect_uri):
        del redirect_uri  # обмен кода у Яндекса идёт без redirect_uri; аргумент оставлен для следующего провайдера
        if not isinstance(code, str) or not code or len(code) > 512:
            raise ProviderError("code")
        token = exchange_code(code, _cfg("YANDEX_CLIENT_ID"), _cfg("YANDEX_CLIENT_SECRET"))
        info = fetch_userinfo(token)
        subject = str(info.get("id") or "").strip()
        if not _SUBJECT_RE.fullmatch(subject):
            raise ProviderError("id")
        return Identity(self.id, subject, verified_email(info), _display_name(info, verified_email(info)))


# VK ID: добавить класс и строку здесь. Пока реестр — только Яндекс, и только когда заданы оба секрета.
PROVIDERS = {"yandex": YandexProvider()}


def get(name):
    return PROVIDERS.get(name)


def enabled():
    return [{"id": p.id, "button": p.button} for p in PROVIDERS.values() if p.enabled()]
