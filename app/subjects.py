"""Предметы сайта. Общий каркас (ученики, трофеи, ранги, бойцы, магазин, проверки, сертификаты, родительская
ссылка) один на всех; у каждого предмета — свои страницы и задания. У ученика — список предметов (users.subjects).

Чтобы добавить предмет: запись сюда, страницы в main.py, задания в app/content/<предмет>.py,
проверки — с полем "subject" в app/content/checks.py.
"""
from . import config

SUBJECTS = {
    "python": {"title": "Python", "emoji": "🐍"},
    "russian": {"title": "Русский язык", "emoji": "📖"},
    "chemistry": {"title": "Химия", "emoji": "🧪"},
}


def of(student):
    raw = (student or {}).get("subjects") or config.SUBJECTS[0]
    return [s for s in raw.split(",") if s in SUBJECTS]


def serialize(names):
    return ",".join(s for s in SUBJECTS if s in names) or config.SUBJECTS[0]
