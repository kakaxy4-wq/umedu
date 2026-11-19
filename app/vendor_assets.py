"""Файлы, которые fetch_vendor.sh кладёт в app/static/vendor.

Их нет в git. Если после выкладки папка пустая, страница открывается, а запуск кода — нет.
Список один и для /healthz, и для scripts/check_static.py.
"""
from pathlib import Path

# Относительно app/static.
VENDOR_FILES = (
    "vendor/pyodide/pyodide.js",
    "vendor/pyodide/pyodide.asm.js",
    "vendor/pyodide/pyodide.asm.wasm",
    "vendor/pyodide/python_stdlib.zip",
    "vendor/pyodide/pyodide-lock.json",
    "vendor/codemirror/codemirror.js",
    "vendor/codemirror/codemirror.css",
    "vendor/codemirror/python.js",
    "vendor/codemirror/matchbrackets.js",
    "vendor/codemirror/closebrackets.js",
    "vendor/fonts/golos-text-cyrillic-wght-normal.woff2",
    "vendor/fonts/golos-text-latin-wght-normal.woff2",
    "vendor/fonts/jetbrains-mono-cyrillic-wght-normal.woff2",
    "vendor/fonts/jetbrains-mono-latin-wght-normal.woff2",
    "vendor/fonts/unbounded-cyrillic-wght-normal.woff2",
    "vendor/fonts/unbounded-latin-wght-normal.woff2",
)

# Страницы, с которых скрипт проверки собирает ссылки на /static.
# / и /login обязаны открыться. Остальные на КодКвесте или ХимЛабе могут ответить 404 —
# это не поломка статики, такие страницы просто пропускаем.
KEY_PAGES = ("/", "/login", "/task/hello", "/u2/lab", "/chem/lab")
REQUIRED_PAGES = ("/", "/login")


def static_root():
    return Path(__file__).resolve().parent / "static"


def missing():
    """Имена файлов из списка, которых нет на диске."""
    root = static_root()
    return [name for name in VENDOR_FILES if not (root / name).is_file()]
