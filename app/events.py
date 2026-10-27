"""Продуктовые события: что ученик открывал и делал на сайте — чтобы видеть, где бросают.

Пишет middleware в main.py: один ряд на успешный запрос вошедшего ученика или преподавателя.
Маршрут хранится шаблоном («/lesson/{num}»), конкретные значения — в ref. Ничего не уходит наружу,
счётчиков и cookies нет. Старше KEEP_DAYS — удаляются.
"""
import re
from datetime import timedelta

from . import config
from .db import connect

KEEP_DAYS = 180
SKIP = ("/static/", "/healthz", "/favicon")
_purged_on = None

# Подписи разделов для страницы аналитики: шаблон маршрута → (раздел, что это)
LABELS = {
    "/": ("Главная", "главная ученика"),
    "/today": ("План дня", "план на сегодня"),
    "/today/claim": ("План дня", "забрал сундук плана"),
    "/map": ("Python", "карта уроков"),
    "/lesson/{num}": ("Python", "урок"),
    "/lesson/{num}/submit": ("Python", "сдал домашку"),
    "/lesson/{num}/self-done": ("Python", "«урок изучен»"),
    "/homework": ("Python", "домашки"),
    "/task/{task_id}": ("Python", "задача"),
    "/api/task/{task_id}/attempt": ("Python", "проверка задачи"),
    "/api/run": ("Python", "запуск кода"),
    "/daily": ("Задача дня", "задача дня"),
    "/api/daily/answer": ("Задача дня", "ответ на задачу дня"),
    "/checks": ("Проверки", "список проверок"),
    "/check/{cid}": ("Проверки", "проверка"),
    "/check/{cid}/submit": ("Проверки", "сдал проверку"),
    "/oge": ("ОГЭ", "раздел ОГЭ"),
    "/oge/drill/{num}": ("ОГЭ", "тренажёр номера"),
    "/oge/mock": ("ОГЭ", "пробник"),
    "/oge/robot": ("ОГЭ", "Робот: список"),
    "/oge/robot/{task_id}": ("ОГЭ", "Робот: задача"),
    "/api/robot/{task_id}/attempt": ("ОГЭ", "Робот: попытка"),
    "/ru": ("Русский", "раздел русского"),
    "/ru/commas": ("Русский", "запятые"),
    "/ru/spell": ("Русский", "орфограммы"),
    "/ru/basis": ("Русский", "грамматическая основа"),
    "/ru/dict": ("Русский", "диктанты"),
    "/ru/review": ("Русский", "повторение ошибок"),
    "/ru/rules": ("Русский", "правила"),
    "/ru/practice/{rule}": ("Русский", "практика правила"),
    "/api/ru/answer": ("Русский", "ответ"),
    "/api/ru/dict": ("Русский", "диктант: ответ"),
    "/season": ("Игра", "сезон"),
    "/season/claim": ("Игра", "забрал награду сезона"),
    "/shop": ("Игра", "магазин"),
    "/shop/{rid}/buy": ("Игра", "покупка"),
    "/achievements": ("Игра", "достижения"),
    "/bots": ("Игра", "битва ботов"),
    "/trainer": ("Python", "тренажёр"),
    "/playground": ("Python", "песочница"),
    "/cheatsheet": ("Python", "шпаргалка"),
    "/portfolio": ("Портфолио", "портфолио"),
    "/certificates": ("Игра", "сертификаты"),
    "/login": ("Вход", "вход"),
}


def section(route):
    return LABELS.get(route, (_guess_section(route), route))


def _guess_section(route):
    if route.startswith("/teacher"):
        return "Преподаватель"
    if route.startswith(("/ru", "/api/ru")):
        return "Русский"
    if route.startswith("/oge"):
        return "ОГЭ"
    return "Другое"


def _route_of(request):
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if path:
        return path
    return re.sub(r"/\d+", "/{n}", request.url.path)


def should_record(request, status):
    path = request.url.path
    if status >= 400 or path.startswith(SKIP):
        return False
    user = getattr(request.state, "user", None)
    return bool(user and user.get("role") in ("student", "teacher"))


def record(request, status):
    """Записать событие. Никогда не роняет ответ: аналитика не важнее урока."""
    try:
        if config.CHEM_SITE or not should_record(request, status):
            return
        user = request.state.user
        params = request.scope.get("path_params") or {}
        ref = ",".join(str(v) for v in params.values())[:80]
        kind = "view" if request.method == "GET" and not request.url.path.startswith("/api/") else "action"
        conn = connect()
        try:
            with conn:
                conn.execute("INSERT INTO events (user_id, role, kind, route, ref, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                             (user["id"], user["role"], kind, _route_of(request), ref, config.now().isoformat()))
                _purge(conn)
        finally:
            conn.close()
    except Exception:          # noqa: BLE001 — база занята, таблицы нет и т. п.: просто пропускаем событие
        pass


def _purge(conn):
    global _purged_on
    today = config.today()
    if _purged_on == today:
        return
    _purged_on = today
    conn.execute("DELETE FROM events WHERE created_at < ?", ((today - timedelta(days=KEEP_DAYS)).isoformat(),))
