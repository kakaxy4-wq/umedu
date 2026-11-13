"""Загрузчик контент-пакетов (Content as Data).

Контент (правила, уроки, номера) описывается в YAML-файлах в content/packs/,
а не хардкодится в Python. Это основа масштабирования: новая тема = новый файл,
без правки маршрутов и кода (учи.ru / LogicLike уровень).

Пока загрузчик только читает пакеты; миграция ru.RULES на пакеты — следующий шаг.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

BASE = Path(__file__).resolve().parent.parent.parent / "content" / "packs"


def load_pack(name: str) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML не установлен")
    path = BASE / name
    if not path.exists():
        raise FileNotFoundError(str(path))
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def list_packs() -> list[str]:
    if not BASE.exists():
        return []
    return sorted(p.name for p in BASE.glob("*.yaml"))


def load_ru_rules() -> dict[str, tuple[str, str]]:
    """Загрузить правила русского из пакета ru_rules.yaml. Возвращает {id: (title, text)}."""
    pack = load_pack("ru_rules.yaml")
    out = {}
    for item in pack.get("rules", []):
        out[item["id"]] = (item["title"], item["text"])
    return out
