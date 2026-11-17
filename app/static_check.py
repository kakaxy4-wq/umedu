"""Сбор ссылок /static со страниц и проверка, что каждая отвечает 200.

Скрипт выкладки вызывает scripts/check_static.py. Здесь только разбор HTML/CSS/JS
и решение, что считать поломкой: так это можно проверить без живого сервера.
"""
import re
from urllib.parse import urljoin, urlparse

from .vendor_assets import KEY_PAGES, REQUIRED_PAGES, VENDOR_FILES

_ATTR = re.compile(r"""(?:href|src)\s*=\s*["']([^"']+)["']""", re.I)
_URL = re.compile(r"""url\(\s*["']?([^"')]+)["']?\s*\)""", re.I)
_JS = re.compile(r"""["'](/static/[^"']+)["']""")


def static_url(raw, page_url):
    """Абсолютный путь /static/... без ?v= или None, если это не наш файл."""
    if not raw or raw.startswith(("data:", "mailto:", "#")):
        return None
    abs_url = urljoin(page_url, raw.strip())
    parsed = urlparse(abs_url)
    page = urlparse(page_url)
    if parsed.netloc and page.netloc and parsed.netloc != page.netloc:
        return None
    path = parsed.path
    if not path.startswith("/static/"):
        return None
    return path


def assets_in(text, page_url, js=False):
    found = set()
    if not text:
        return found
    if js:
        for raw in _JS.findall(text):
            path = static_url(raw, page_url)
            if path:
                found.add(path)
        return found
    for raw in _ATTR.findall(text) + _URL.findall(text):
        path = static_url(raw, page_url)
        if path:
            found.add(path)
    return found


def _ctype(headers):
    raw = ""
    if headers:
        raw = headers.get("content-type") or headers.get("Content-Type") or ""
    return raw.split(";", 1)[0].strip().lower()


def problems(base, fetch):
    """fetch(url) -> объект с status, headers, text, url (адрес после редиректа).

    Возвращает список строк. Пустой список — всё на месте.
    """
    base = base.rstrip("/")
    bad = []
    found = {"/static/" + name for name in VENDOR_FILES}
    seen_pages = set()
    extra = []

    for page in KEY_PAGES:
        url = base + page
        try:
            resp = fetch(url)
        except Exception as exc:  # сеть до самого сайта
            bad.append("%s не открылась: %s" % (url, exc))
            continue
        status = getattr(resp, "status", 0)
        final = getattr(resp, "url", url) or url
        if status != 200:
            if page in REQUIRED_PAGES:
                bad.append("%s → %s" % (url, status))
            continue
        if final in seen_pages:
            continue
        seen_pages.add(final)
        body = getattr(resp, "text", "") or ""
        paths = assets_in(body, final)
        found |= paths
        for path in paths:
            if path.endswith((".css", ".js")):
                extra.append(path)

    for path in extra:
        url = base + path
        try:
            resp = fetch(url)
        except Exception as exc:
            bad.append("%s не открылся: %s" % (path, exc))
            continue
        if getattr(resp, "status", 0) != 200:
            continue  # сам файл попадёт в общий проход ниже
        kind = "js" if path.endswith(".js") else ""
        found |= assets_in(getattr(resp, "text", "") or "", url, js=(kind == "js"))

    for path in sorted(found):
        url = base + path
        try:
            resp = fetch(url)
        except Exception as exc:
            bad.append("%s не открылся: %s" % (path, exc))
            continue
        status = getattr(resp, "status", 0)
        if status != 200:
            bad.append("%s → %s" % (path, status))
            continue
        if path.endswith(".wasm") and _ctype(getattr(resp, "headers", {}) or {}) != "application/wasm":
            got = _ctype(getattr(resp, "headers", {}) or {}) or "пустой"
            bad.append("%s → 200, но тип %s, нужен application/wasm" % (path, got))
    return bad
