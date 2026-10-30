"""Снимок меню и ключевых ссылок до правок стенда.

КодКвест (семейная тема, без CQ_UMEDU2 и без CQ_STAGE) и главная ХимЛаба должны отдавать те же
пункты меню и те же опорные ссылки. Плашка стенда и раздел /u2 сюда не попадают.
"""
import re

from test_app import client, login  # noqa: F401


def _nav(html):
    nav = re.search(r'<nav class="sidenav">(.*?)</nav>', html, re.S).group(1)
    out = []
    for href, text in re.findall(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', nav, re.S):
        label = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text)).strip()
        out.append((href, label))
    return out


def _hrefs(html):
    main = re.search(r"<main[^>]*>(.*?)</main>", html, re.S).group(1)
    return re.findall(r'href="([^"]+)"', main)


CQ_NAV = [
    ("/", "🏠 Главная"),
    ("/today", "📅 План на сегодня"),
    ("/map", "🗺️ Карта курса"),
    ("/homework", "📬 Домашка"),
    ("/daily", "☀️ Задача дня"),
    ("/oge", "🎯 ОГЭ"),
    ("/trainer", "🏀 Арена"),
    ("/bots", "⚔️ Битва ботов"),
    ("/playground", "🧪 Песочница"),
    ("/cheatsheet", "📒 Шпаргалка"),
    ("/achievements", "🏅 Бойцы и награды"),
    ("/season", "🎟️ Пасс сезона"),
    ("/shop", "💎 Магазин подарков"),
    ("/certificates", "🎓 Сертификаты"),
    ("/checks", "📝 Проверки"),
    ("/portfolio", "🗂️ Портфолио"),
    ("/account", "👤 Аккаунт и данные"),
]

CHEM_NAV = [
    ("/chem", "🏠 Главная"),
    ("/chem/map", "🗺️ Карта экзамена"),
    ("/chem/hw", "📚 Домашние задания"),
    ("/chem/mock", "⏱️ Пробник"),
    ("/checks", "📝 Тесты"),
    ("/chem/lab", "🔬 Лаборатория"),
    ("/chem/table", "⚛️ Таблица Менделеева"),
    ("/chem/me", "👤 Мой профиль"),
    ("/account", "👤 Аккаунт и данные"),
]


def test_codequest_home_menu_and_links(client):
    login(client, "student")
    html = client.get("/").text
    assert _nav(html) == CQ_NAV
    hrefs = _hrefs(html)
    for link in ("/check/entry", "/today", "/lesson/1", "/season", "/trainer", "/achievements"):
        assert link in hrefs
    assert all(f"/lesson/{n}" in hrefs for n in range(1, 35))
    assert "/u2" not in html and "Тестовый стенд" not in html and 'data-qa="exam-prep"' not in html
    assert "x-robots-tag" not in {k.lower() for k in client.get("/").headers}


def test_chemlab_home_menu_and_links(client, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "CHEM_SITE", True)
    monkeypatch.setattr(config, "SUBJECTS", ["chemistry"])
    monkeypatch.setattr(config, "GAME", "light")
    monkeypatch.setattr(config, "SIGNUP", True)
    monkeypatch.setattr(config, "BRAND_EMOJI", "🧪")
    login(client, "student")
    html = client.get("/chem").text
    assert _nav(html) == CHEM_NAV
    hrefs = _hrefs(html)
    assert "/chem/map" in hrefs and "/chem/hw" in hrefs
    assert "Входное тестирование" in html and "Карта экзамена" in html
    assert "/u2" not in html and "Тестовый стенд" not in html
    assert "x-robots-tag" not in {k.lower() for k in client.get("/chem").headers}
