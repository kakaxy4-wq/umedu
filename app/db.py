import sqlite3

from . import config

# Схема v2: несколько учеников. Всё личное (трофеи, задачи, домашки, проверки…) принадлежит ученику —
# колонка student_id. Общие только аккаунты, сессии, настройки и каталог наград.
SCHEMA_VERSION = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('student', 'teacher')),
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    full_name TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    last_seen_at TEXT,
    parent_token TEXT,
    unlocked INTEGER NOT NULL DEFAULT 1,
    next_lesson_at TEXT,
    current_student_id INTEGER,
    subjects TEXT NOT NULL DEFAULT 'python'
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    csrf TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS rewards (
    id INTEGER PRIMARY KEY,
    emoji TEXT NOT NULL,
    title TEXT NOT NULL,
    cost INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);
""" + """
CREATE TABLE IF NOT EXISTS lesson_state (
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    num INTEGER NOT NULL,
    opened_at TEXT,
    done_at TEXT,
    teacher_note TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (student_id, num)
);
CREATE TABLE IF NOT EXISTS xp_events (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount INTEGER NOT NULL,
    reason TEXT NOT NULL,
    kind TEXT NOT NULL,
    ref TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS task_attempts (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task_id TEXT NOT NULL,
    code TEXT NOT NULL,
    passed INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lesson INTEGER NOT NULL,
    code TEXT NOT NULL DEFAULT '',
    comment TEXT NOT NULL DEFAULT '',
    file_name TEXT,
    file_path TEXT,
    star INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    teacher_comment TEXT NOT NULL DEFAULT '',
    xp_awarded INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    reviewed_at TEXT
);
CREATE TABLE IF NOT EXISTS achievements (
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    unlocked_at TEXT NOT NULL,
    PRIMARY KEY (student_id, code)
);
CREATE TABLE IF NOT EXISTS notices (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    emoji TEXT NOT NULL,
    text TEXT NOT NULL,
    big INTEGER NOT NULL DEFAULT 0,
    seen INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS purchases (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reward_id INTEGER NOT NULL REFERENCES rewards(id),
    title TEXT NOT NULL,
    cost INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'requested',
    created_at TEXT NOT NULL,
    resolved_at TEXT
);
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    slug TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    code TEXT NOT NULL DEFAULT '',
    image_path TEXT,
    file_name TEXT,
    file_path TEXT,
    public INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS snippets (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    code TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS daily (
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    day TEXT NOT NULL,
    kind TEXT NOT NULL,
    ref TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    solved INTEGER NOT NULL DEFAULT 0,
    finished_at TEXT,
    PRIMARY KEY (student_id, day)
);
CREATE TABLE IF NOT EXISTS trainer_runs (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    mode TEXT NOT NULL,
    correct INTEGER NOT NULL,
    wrong INTEGER NOT NULL,
    xp INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS counters (
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    value INTEGER NOT NULL,
    PRIMARY KEY (student_id, key)
);
CREATE TABLE IF NOT EXISTS check_state (
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    id TEXT NOT NULL,
    opened_at TEXT,
    started_at TEXT,
    PRIMARY KEY (student_id, id)
);
CREATE TABLE IF NOT EXISTS check_results (
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    check_id TEXT NOT NULL,
    answers TEXT NOT NULL,
    right_count INTEGER NOT NULL,
    total INTEGER NOT NULL,
    skipped INTEGER NOT NULL,
    started_at TEXT,
    finished_at TEXT NOT NULL,
    PRIMARY KEY (student_id, check_id)
);
CREATE TABLE IF NOT EXISTS certificates (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    emoji TEXT NOT NULL,
    title TEXT NOT NULL,
    reason TEXT NOT NULL,
    issued_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ru_attempts (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL,
    rule TEXT NOT NULL,
    ok INTEGER NOT NULL,
    answer TEXT NOT NULL DEFAULT '',
    mode TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ru_review (
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL,
    box INTEGER NOT NULL DEFAULT 0,
    due TEXT NOT NULL,
    PRIMARY KEY (student_id, item_id)
);
CREATE TABLE IF NOT EXISTS season_state (
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    season TEXT NOT NULL,
    premium INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (student_id, season)
);
CREATE TABLE IF NOT EXISTS season_claims (
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    season TEXT NOT NULL,
    tier INTEGER NOT NULL,
    track TEXT NOT NULL,
    kind TEXT NOT NULL,
    value TEXT NOT NULL DEFAULT '',
    claimed_at TEXT NOT NULL,
    PRIMARY KEY (student_id, season, tier, track)
);
CREATE TABLE IF NOT EXISTS chem_lessons (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    starts_at TEXT NOT NULL,
    minutes INTEGER NOT NULL DEFAULT 60,
    status TEXT NOT NULL DEFAULT 'planned',
    charged INTEGER NOT NULL DEFAULT 0,
    price INTEGER NOT NULL DEFAULT 0,
    topic TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chem_lessons ON chem_lessons(student_id, starts_at);
CREATE TABLE IF NOT EXISTS chem_payments (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount INTEGER NOT NULL,
    paid_at TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chem_payments ON chem_payments(student_id, paid_at);
CREATE TABLE IF NOT EXISTS chem_hw (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    text TEXT NOT NULL DEFAULT '',
    task_ids TEXT NOT NULL DEFAULT '',
    due_at TEXT,
    status TEXT NOT NULL DEFAULT 'given',
    answer TEXT NOT NULL DEFAULT '',
    file_name TEXT,
    file_path TEXT,
    submitted_at TEXT,
    score INTEGER,
    max_score INTEGER,
    comment TEXT NOT NULL DEFAULT '',
    checked_at TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chem_hw ON chem_hw(student_id, status);
CREATE TABLE IF NOT EXISTS chem_lesson_files (
    id INTEGER PRIMARY KEY,
    lesson_id INTEGER NOT NULL REFERENCES chem_lessons(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chem_lesson_files ON chem_lesson_files(student_id, lesson_id);
CREATE TABLE IF NOT EXISTS chem_hw_files (
    id INTEGER PRIMARY KEY,
    hw_id INTEGER NOT NULL REFERENCES chem_hw(id) ON DELETE CASCADE,
    author TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chem_hw_files ON chem_hw_files(hw_id);
CREATE TABLE IF NOT EXISTS chem_attempts (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task_id TEXT NOT NULL,
    answer TEXT NOT NULL,
    points INTEGER NOT NULL,
    max_points INTEGER NOT NULL,
    hw_id INTEGER,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chem_attempts ON chem_attempts(student_id, task_id);
CREATE TABLE IF NOT EXISTS chem_mocks (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    exam TEXT NOT NULL,
    tasks TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'given',
    answers TEXT NOT NULL DEFAULT '{}',
    points TEXT NOT NULL DEFAULT '{}',
    long_points TEXT NOT NULL DEFAULT '{}',
    score INTEGER,
    comment TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT 'student',
    due_at TEXT,
    started_at TEXT,
    deadline_at TEXT,
    finished_at TEXT,
    checked_at TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chem_mocks ON chem_mocks(student_id, status);
CREATE TABLE IF NOT EXISTS chem_mock_files (
    id INTEGER PRIMARY KEY,
    mock_id INTEGER NOT NULL REFERENCES chem_mocks(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chem_mock_files ON chem_mock_files(mock_id);
CREATE TABLE IF NOT EXISTS chem_lesson_plans (
    lesson_id INTEGER PRIMARY KEY REFERENCES chem_lessons(id) ON DELETE CASCADE,
    topic_ids TEXT NOT NULL DEFAULT '[]',
    plan TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chem_reviews (
    item TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    comment TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bot_fights (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    boss TEXT NOT NULL,
    code TEXT NOT NULL,
    won INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bot_fights ON bot_fights(student_id, boss);
CREATE TABLE IF NOT EXISTS robot_attempts (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task_id TEXT NOT NULL,
    code TEXT NOT NULL,
    passed INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_robot_attempts ON robot_attempts(student_id, task_id);
CREATE TABLE IF NOT EXISTS oge_drill (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    num INTEGER NOT NULL,
    seed INTEGER NOT NULL,
    ok INTEGER NOT NULL,
    answer TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_oge_drill ON oge_drill(student_id, num, seed);
CREATE INDEX IF NOT EXISTS idx_ru_attempts ON ru_attempts(student_id, rule, created_at);
CREATE INDEX IF NOT EXISTS idx_xp_student ON xp_events(student_id, created_at);
CREATE INDEX IF NOT EXISTS idx_attempts_student ON task_attempts(student_id, task_id);
CREATE INDEX IF NOT EXISTS idx_submissions_student ON submissions(student_id, lesson);
CREATE INDEX IF NOT EXISTS idx_notices_student ON notices(student_id, seen);
CREATE INDEX IF NOT EXISTS idx_purchases_student ON purchases(student_id);
CREATE INDEX IF NOT EXISTS idx_projects_student ON projects(student_id);
CREATE INDEX IF NOT EXISTS idx_snippets_student ON snippets(student_id);
CREATE INDEX IF NOT EXISTS idx_trainer_student ON trainer_runs(student_id, created_at);
CREATE INDEX IF NOT EXISTS idx_certificates_student ON certificates(student_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_parent ON users(parent_token) WHERE parent_token IS NOT NULL;

-- Кабинет родителя (app/family.py): отдельно от users, чтобы роли не смешивались.
CREATE TABLE IF NOT EXISTS parents (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    consent_at TEXT NOT NULL,
    consent_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS parent_sessions (
    token_hash TEXT PRIMARY KEY,
    parent_id INTEGER NOT NULL REFERENCES parents(id) ON DELETE CASCADE,
    csrf TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS parent_children (
    parent_id INTEGER NOT NULL REFERENCES parents(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    PRIMARY KEY (parent_id, student_id)
);
CREATE INDEX IF NOT EXISTS idx_parent_children_student ON parent_children(student_id);

-- Продуктовые события (app/events.py): что открывали и делали на сайте. Хранятся KEEP_DAYS дней.
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    kind TEXT NOT NULL,
    route TEXT NOT NULL,
    ref TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_time ON events(created_at);
CREATE INDEX IF NOT EXISTS idx_events_user ON events(user_id, created_at);

-- umedu 2.0: экзамены ученика и знания по номерам (app/knowledge.py, app/exam_model.py)
CREATE TABLE IF NOT EXISTS exam_enroll (
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    exam_id TEXT NOT NULL,
    goal INTEGER,                      -- отметка (ОГЭ, база) или тестовый балл (ЕГЭ)
    exam_date TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (student_id, exam_id)
);
CREATE TABLE IF NOT EXISTS forecast_log (      -- прогноз на конец дня: история для вкладки «Прогресс»
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    exam_id TEXT NOT NULL,
    day TEXT NOT NULL,
    primary_mean REAL NOT NULL,
    low INTEGER NOT NULL,
    high INTEGER NOT NULL,
    result INTEGER NOT NULL,           -- отметка или тестовый балл по середине вилки
    PRIMARY KEY (student_id, exam_id, day)
);
CREATE TABLE IF NOT EXISTS u2_prefs (
    student_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    daily_minutes INTEGER NOT NULL DEFAULT 30   -- сколько минут в день ученик готов заниматься
);
CREATE TABLE IF NOT EXISTS skill_state (
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    exam_id TEXT NOT NULL,
    task_key TEXT NOT NULL,            -- номер задания или критерий («ГК»)
    p REAL NOT NULL,
    n INTEGER NOT NULL,
    last TEXT,
    PRIMARY KEY (student_id, exam_id, task_key)
);
CREATE TABLE IF NOT EXISTS skill_attempt (     -- каждая попытка: серии «3 верно подряд», «Мои ошибки», дни занятий
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    exam_id TEXT NOT NULL,
    task_key TEXT NOT NULL,
    score REAL NOT NULL,               -- доля баллов 0…1
    seed INTEGER,                      -- вариант генератора, если номер генерируется
    given TEXT,                        -- ответ ученика (до 100 символов)
    day TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_skill_attempt ON skill_attempt(student_id, exam_id, id);
CREATE INDEX IF NOT EXISTS idx_skill_attempt_day ON skill_attempt(student_id, day);
CREATE TABLE IF NOT EXISTS lab_offer (          -- когда «Сегодня» уже предлагало опыт: не чаще раза в 3 дня
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lab_id TEXT NOT NULL,
    day TEXT NOT NULL,
    PRIMARY KEY (student_id, lab_id)
);
-- организации и классы: экраны учителя позже, таблицы сразу, чтобы потом не переделывать
CREATE TABLE IF NOT EXISTS org (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS class (
    id INTEGER PRIMARY KEY,
    org_id INTEGER REFERENCES org(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    teacher_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS class_member (
    class_id INTEGER NOT NULL REFERENCES class(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    joined_at TEXT NOT NULL,
    PRIMARY KEY (class_id, student_id)
);
"""

# Таблицы, которые в v1 были «общими на одного ученика» и в v2 получили student_id.
# (таблица, колонки v1 в порядке копирования)
PERSONAL_TABLES = [
    ("lesson_state", "num, opened_at, done_at, teacher_note"),
    ("xp_events", "id, amount, reason, kind, ref, created_at"),
    ("task_attempts", "id, task_id, code, passed, created_at"),
    ("submissions", "id, lesson, code, comment, file_name, file_path, star, status, teacher_comment, xp_awarded, "
                    "created_at, reviewed_at"),
    ("achievements", "code, unlocked_at"),
    ("notices", "id, emoji, text, big, seen, created_at"),
    ("purchases", "id, reward_id, title, cost, status, created_at, resolved_at"),
    ("projects", "id, slug, title, description, code, image_path, file_name, file_path, public, created_at, updated_at"),
    ("snippets", "id, title, code, updated_at"),
    ("daily", "day, kind, ref, attempts, solved, finished_at"),
    ("trainer_runs", "id, mode, correct, wrong, xp, created_at"),
    ("counters", "key, value"),
    ("check_state", "id, opened_at, started_at"),
    ("check_results", "check_id, answers, right_count, total, skipped, started_at, finished_at"),
    ("certificates", "id, emoji, title, reason, issued_at"),
]

USER_COLUMNS = [
    ("full_name", "TEXT NOT NULL DEFAULT ''"),
    ("notes", "TEXT NOT NULL DEFAULT ''"),
    ("active", "INTEGER NOT NULL DEFAULT 1"),
    ("last_seen_at", "TEXT"),
    ("parent_token", "TEXT"),
    ("unlocked", "INTEGER NOT NULL DEFAULT 1"),
    ("next_lesson_at", "TEXT"),
    ("current_student_id", "INTEGER"),
    ("subjects", "TEXT NOT NULL DEFAULT 'python'"),
    ("level", "TEXT NOT NULL DEFAULT 'base'"),
    ("age", "INTEGER"),
    ("calm", "INTEGER NOT NULL DEFAULT 0"),
    ("self_paced", "INTEGER NOT NULL DEFAULT 0"),
    ("badge", "TEXT NOT NULL DEFAULT ''"),
    ("title", "TEXT NOT NULL DEFAULT ''"),
    ("grade", "INTEGER"),
    ("price", "INTEGER NOT NULL DEFAULT 0"),
    ("consent", "TEXT NOT NULL DEFAULT ''"),  # «редакция политики · когда» — при открытой регистрации
    ("minor", "INTEGER NOT NULL DEFAULT 0"),  # 1 — аккаунт завёл родитель, ученику меньше 14 лет
    ("gallery_ok", "INTEGER NOT NULL DEFAULT 0"),
    ("gallery_consent_at", "TEXT"),           # когда поставили галочку «ник в галерее»; пусто — согласия нет
    ("gallery_consent_version", "TEXT NOT NULL DEFAULT ''"),
    ("gallery_consent_by", "TEXT NOT NULL DEFAULT ''"),  # «ученик» или «родитель»
]

# Цены — в гемах 💎 (10 за занятие, 10 за домашку): пицца ≈ месяц занятий, новая игра ≈ четверть.
DEFAULT_REWARDS = [
    ("🍰", "Десерт на выбор", 40),
    ("🎬", "Выбрать фильм на семейный вечер", 60),
    ("🌙", "Лечь на час позже в выходной", 70),
    ("🎮", "Час дополнительной игры", 80),
    ("🍕", "Пицца на ужин", 160),
    ("📚", "Книга или комикс на выбор", 200),
    ("🎳", "Боулинг, картинг или батуты", 300),
    ("🎟️", "Поход в кино или квест-комнату", 300),
    ("🧩", "Лего или настольная игра", 400),
    ("🕹️", "Новая игра", 500),
]
_OLD_COSTS = {"Выбрать фильм на семейный вечер": 150, "Час дополнительной игры": 200, "Пицца на ужин": 300,
              "Поход в кино или квест-комнату": 600, "Новая игра": 1000}


def _economy_v2(conn):
    """10.10.2026: магазин переведён с трофеев на гемы. Старые цены по умолчанию пересчитываем (свои цены
    преподавателя не трогаем), добавляем новые подарки. Один раз — по отметке в settings."""
    if conn.execute("SELECT 1 FROM settings WHERE key = 'economy_v2'").fetchone():
        return
    new = {t: (e, c) for e, t, c in DEFAULT_REWARDS}
    for r in conn.execute("SELECT id, title, cost FROM rewards").fetchall():
        if _OLD_COSTS.get(r[1]) == r[2]:
            conn.execute("UPDATE rewards SET cost = ? WHERE id = ?", (new[r[1]][1], r[0]))
    have = {r[0] for r in conn.execute("SELECT title FROM rewards")}
    conn.executemany("INSERT INTO rewards (emoji, title, cost) VALUES (?, ?, ?)",
                     [(e, t, c) for e, t, c in DEFAULT_REWARDS if t not in have])
    conn.execute("INSERT INTO settings (key, value) VALUES ('economy_v2', '1')")


def connect():
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _columns(conn, table):
    return [r[1] for r in conn.execute("PRAGMA table_info(%s)" % table)]


def _migrate_v1_to_v2(conn):
    """База с одним учеником → несколько учеников. Все данные v1 отдаются первому ученику.

    Выполняется одной транзакцией: либо всё перенесено, либо база не тронута.
    """
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    if "users" not in tables or "xp_events" not in tables or "student_id" in _columns(conn, "xp_events"):
        return False  # свежая база или уже v2
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.execute("BEGIN")
        user_cols = _columns(conn, "users")
        for name, ddl in USER_COLUMNS:
            if name not in user_cols:
                conn.execute("ALTER TABLE users ADD COLUMN %s %s" % (name, ddl))
        student = conn.execute("SELECT id FROM users WHERE role = 'student' ORDER BY id LIMIT 1").fetchone()
        sid = student[0] if student else None
        settings = {r[0]: r[1] for r in conn.execute("SELECT key, value FROM settings")}
        if sid:
            conn.execute("UPDATE users SET unlocked = ?, next_lesson_at = ?, full_name = ? WHERE id = ?",
                         (int(settings.get("unlocked") or 1), settings.get("next_lesson_at"),
                          settings.get("cert_name") or "", sid))
            if settings.get("student_name"):
                conn.execute("UPDATE users SET display_name = ? WHERE id = ?", (settings["student_name"], sid))
        for table, cols in PERSONAL_TABLES:
            if table not in {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}:
                continue
            conn.execute("ALTER TABLE %s RENAME TO %s_v1" % (table, table))
        for stmt in SCHEMA.split(";"):
            if stmt.strip():
                conn.execute(stmt)
        for table, cols in PERSONAL_TABLES:
            old = table + "_v1"
            if old not in {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}:
                continue
            if sid:
                conn.execute("INSERT INTO %s (student_id, %s) SELECT ?, %s FROM %s" % (table, cols, cols, old), (sid,))
            conn.execute("DROP TABLE %s" % old)
        conn.execute("DROP INDEX IF EXISTS idx_attempts_task")
        for key in ("unlocked", "next_lesson_at", "student_name", "cert_name"):
            conn.execute("DELETE FROM settings WHERE key = ?", (key,))
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
    problems = conn.execute("PRAGMA foreign_key_check").fetchall()
    if problems:
        raise RuntimeError("После переноса нарушены связи: %r" % (problems[:5],))
    return True


PARENT_COLUMNS = [
    ("tg_chat_id", "TEXT"),          # чат родителя с ботом — для еженедельного отчёта
    ("tg_code", "TEXT"),             # одноразовый код ссылки t.me/<бот>?start=<код>
    ("tg_code_at", "TEXT"),
    ("last_seen_at", "TEXT"),        # последний вход в кабинет — для удаления через год
]


def _ensure_parent_columns(conn):
    have = _columns(conn, "parents")
    for name, ddl in PARENT_COLUMNS:
        if name not in have:
            conn.execute("ALTER TABLE parents ADD COLUMN %s %s" % (name, ddl))


def _ensure_user_columns(conn):
    """Новые колонки users добавляются к уже существующей базе (CREATE TABLE IF NOT EXISTS их не добавит)."""
    if "users" not in {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}:
        return
    have = _columns(conn, "users")
    for name, ddl in USER_COLUMNS:
        if name not in have:
            conn.execute("ALTER TABLE users ADD COLUMN %s %s" % (name, ddl))


def _backfill_minor(conn):
    """Ученик, которого завёл родитель, — младше 14. Старые строки помечаем один раз по тексту согласия."""
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    if "users" not in tables or "settings" not in tables:
        return
    cols = _columns(conn, "users")
    if "minor" not in cols or "consent" not in cols:
        return
    if conn.execute("SELECT 1 FROM settings WHERE key = 'minor_backfill'").fetchone():
        return
    conn.execute("UPDATE users SET minor = 1 WHERE role = 'student' AND consent LIKE '%родитель #%' AND minor = 0")
    conn.execute("INSERT INTO settings (key, value) VALUES ('minor_backfill', '1')")


def init_db():
    conn = connect()
    conn.isolation_level = None  # транзакциями миграции управляем сами
    _migrate_v1_to_v2(conn)
    _ensure_user_columns(conn)
    conn.isolation_level = ""
    with conn:
        conn.executescript(SCHEMA)
        _ensure_user_columns(conn)   # на новой базе users только что создана по SCHEMA — без поздних колонок
        _ensure_parent_columns(conn)
        if conn.execute("SELECT COUNT(*) FROM rewards").fetchone()[0] == 0:
            conn.executemany("INSERT INTO rewards (emoji, title, cost) VALUES (?, ?, ?)", DEFAULT_REWARDS)
            conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('economy_v2', '1')")
        _economy_v2(conn)
        _backfill_minor(conn)
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
    conn.close()


def get_db():
    """Зависимость FastAPI: соединение на время запроса."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def get_setting(conn, key, default=None):
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row and row["value"] is not None else default


def set_setting(conn, key, value):
    conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) "
                 "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))


def bump_counter(conn, sid, key, by=1):
    conn.execute("INSERT INTO counters (student_id, key, value) VALUES (?, ?, ?) "
                 "ON CONFLICT(student_id, key) DO UPDATE SET value = value + excluded.value", (sid, key, by))
    return conn.execute("SELECT value FROM counters WHERE student_id = ? AND key = ?", (sid, key)).fetchone()[0]


def counter(conn, sid, key):
    row = conn.execute("SELECT value FROM counters WHERE student_id = ? AND key = ?", (sid, key)).fetchone()
    return row[0] if row else 0
