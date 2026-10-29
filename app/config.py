import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv():
    # второй экземпляр (например, химия) указывает свой файл, чтобы не подхватить настройки основного
    env_file = Path(os.environ.get("CQ_ENV_FILE") or BASE_DIR / ".env")
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

DATA_DIR = Path(os.environ.get("CQ_DATA_DIR", BASE_DIR / "data"))
DB_PATH = Path(os.environ.get("CQ_DB_PATH", DATA_DIR / "codequest.db"))
UPLOAD_DIR = Path(os.environ.get("CQ_UPLOAD_DIR", DATA_DIR / "uploads"))
BASE_URL = os.environ.get("CQ_BASE_URL", "").rstrip("/")
COOKIE_SECURE = os.environ.get("CQ_COOKIE_SECURE", "1") == "1"
TELEGRAM_TOKEN = os.environ.get("CQ_TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("CQ_TELEGRAM_CHAT_ID", "")
# бот читает сообщения родителей и шлёт им отчёт по воскресеньям (app/parent_bot.py); нужен CQ_TELEGRAM_TOKEN
PARENT_BOT = os.environ.get("CQ_PARENT_BOT", "0") == "1"
MAX_UPLOAD_MB = int(os.environ.get("CQ_MAX_UPLOAD_MB", "25"))

# ---- экземпляр сайта: один код — несколько сайтов (КодКвест, ХимЛаб) со своими базами
# предметы экземпляра: «python,russian» — КодКвест; «chemistry» — сайт подготовки по химии
SUBJECTS = [s.strip() for s in os.environ.get("CQ_SUBJECTS", "python,russian").split(",") if s.strip()]
CHEM_SITE = SUBJECTS == ["chemistry"]
OPERATOR = os.environ.get("CQ_OPERATOR", "")            # кто оператор ПДн — для /privacy (ФИО/ИП); пусто — «владелец сайта»
SOURCE_URL = os.environ.get("CQ_SOURCE_URL", "")       # ссылка на исходный код (AGPL-3.0, раздел 13); пусто — не показывать
CONTACT = os.environ.get("CQ_CONTACT", "")              # ссылка «Попасть в пилот» на лендинге (Telegram/почта)
THEME = os.environ.get("CQ_THEME", "family")          # family | public — см. app/theme.py
SITE_NAME = os.environ.get("CQ_SITE_NAME", "ХимЛаб" if CHEM_SITE else "КодКвест")
# игра: full — ранги с бойцами, магазин, пасс, арены; light — уровень, серия и достижения без бойцов
GAME = os.environ.get("CQ_GAME", "light" if CHEM_SITE else "full")
BRAND_EMOJI = os.environ.get("CQ_BRAND_EMOJI", "🧪" if CHEM_SITE else "🐍")
MAX_STUDENTS = int(os.environ.get("CQ_MAX_STUDENTS", "60" if CHEM_SITE else "30"))
# самостоятельная регистрация учеников: 0 — нет; 1 — по коду-приглашению преподавателя (ХимЛаб);
# open — без кода, ученик занимается сам (публичный сайт с Python и русским)
SIGNUP_MODE = os.environ.get("CQ_SIGNUP", "1" if CHEM_SITE else "0").strip().lower()
SIGNUP = SIGNUP_MODE in ("1", "open")
OPEN_SIGNUP = SIGNUP_MODE == "open" and not CHEM_SITE
# umedu 2.0 (ОГЭ/ЕГЭ с прогнозом) — раздел /u2; пока за флагом, на действующий сайт не влияет
UMEDU2 = os.environ.get("CQ_UMEDU2", "0") == "1"
TRAINER_DAILY_XP_CAP = int(os.environ.get("CQ_TRAINER_DAILY_XP_CAP", "30"))

try:
    from zoneinfo import ZoneInfo

    TZ = ZoneInfo(os.environ.get("CQ_TIMEZONE", "Europe/Moscow"))
except Exception:  # нет базы часовых поясов
    TZ = timezone(timedelta(hours=3))


def now():
    return datetime.now(TZ)


def today():
    return now().date()
