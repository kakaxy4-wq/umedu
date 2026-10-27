"""Пасс сезона: цель на месяц поверх обычных трофеев.

Сезон = календарный месяц. Ступени открываются трофеями, заработанными в этом сезоне (из xp_events; награды самого
пасса и дропы не считаются — иначе пасс крутил бы сам себя). Две дорожки:
  • бесплатная — всем;
  • «премиум» — не за деньги: открывается испытаниями сезона (4 из 5) или преподавателем вручную.
Награды: трофеи (идут и в магазин), дропы (случайный приз), значки у имени, титулы.
Дропы ещё и выпадают за первое решение задачи — не больше DROPS_PER_DAY в день.
"""
import random
from calendar import monthrange
from datetime import date, timedelta

from . import art, config, game
from .theme import T

TIERS = 20
PER_TIER = 40          # 20 ступеней = 800 трофеев за месяц: пасс — цель на месяц, а не на вечер
DROPS_PER_DAY = 3
DROP_CHANCE = 0.35
NOT_COUNTED = ("pass", "drop")

MONTHS = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь",
          "Ноябрь", "Декабрь"]

# редкость: (название, вероятность, трофеи, эмодзи)
RARITIES = [
    ("Редкий", 50, 3, "🟢"),
    ("Сверхредкий", 28, 5, "🔵"),
    ("Эпический", 15, 10, "🟣"),
    ("Мифический", 5, 20, "🔴"),
    ("Легендарный", 2, 40, "🟡"),
]


def _t(n):
    return {"kind": "trophies", "value": n, "label": "+%d 🏆" % n}


def _d():
    return {"kind": "drop", "value": None, "label": "⭐ " + T["drop"]}


def _b(emoji):
    return {"kind": "badge", "value": emoji, "label": "значок %s" % emoji}


def _title(text):
    return {"kind": "title", "value": text, "label": "титул «%s»" % text}


FREE = [_d(), _b("🐣"), _t(10), _title("Новичок сезона"), _d(), _t(15), _b("🔥"), _d(), _t(20),
        _title("Охотник за багами"), _d(), _b("⚡"), _t(25), _d(), _title("Мастер циклов"), _t(30), _b("💎"), _d(),
        _t(40), _title("Легенда сезона")]
PREMIUM = [_b("🎧"), _t(15), _d(), _title("Кодер-ниндзя"), _t(20), _d(), _b("🚀"), _t(25), _d(),
           _title("Повелитель Python"), _t(30), _b("🐉"), _d(), _t(35), _title("Хакер добра"), _d(), _t(40), _b("🌌"),
           _d(), _title("Чемпион сезона")]
assert len(FREE) == len(PREMIUM) == TIERS

CHALLENGES = [
    ("tasks", "🧩", "Реши 10 задач", 10),
    ("daily", "📅", "Задача дня — 8 раз", 8),
    ("days", "🔥", "Занимайся 10 разных дней", 10),
    ("homework", "📬", "Сдай 2 домашки", 2),
    ("check", "📝", "Пройди проверку или 3 задачи Робота", 1),
]
PREMIUM_NEED = 4


# ------------------------------------------------------------------ сезон и прогресс
def season_of(day=None):
    day = day or config.today()
    first = day.replace(day=1)
    last = day.replace(day=monthrange(day.year, day.month)[1])
    return {"id": first.strftime("%Y-%m"), "title": "%s %d" % (MONTHS[day.month - 1], day.year),
            "start": first, "end": last, "days_left": (last - day).days + 1}


def _since(s):
    return s["start"].isoformat()


def _until(s):
    return (s["end"] + timedelta(days=1)).isoformat()


def points(conn, sid, s):
    return conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM xp_events WHERE student_id = ? AND created_at >= ? AND created_at < ? "
        "AND kind NOT IN (%s)" % ",".join("?" * len(NOT_COUNTED)),
        (sid, _since(s), _until(s), *NOT_COUNTED)).fetchone()[0]


def challenges(conn, sid, s):
    a, b = _since(s), _until(s)

    def n(sql, *args):
        return conn.execute(sql, (sid, a, b, *args)).fetchone()[0]

    have = {
        "tasks": n("SELECT COUNT(*) FROM xp_events WHERE student_id = ? AND created_at >= ? AND created_at < ? AND kind = 'task'"),
        "daily": n("SELECT COUNT(*) FROM daily WHERE student_id = ? AND finished_at >= ? AND finished_at < ?"),
        "days": n("SELECT COUNT(DISTINCT substr(created_at, 1, 10)) FROM xp_events WHERE student_id = ? "
                  "AND created_at >= ? AND created_at < ? AND kind NOT IN ('pass', 'drop', 'manual')"),
        "homework": n("SELECT COUNT(*) FROM submissions WHERE student_id = ? AND created_at >= ? AND created_at < ?"),
        "check": max(n("SELECT COUNT(*) FROM check_results WHERE student_id = ? AND finished_at >= ? AND finished_at < ?"),
                     n("SELECT COUNT(*) FROM xp_events WHERE student_id = ? AND created_at >= ? AND created_at < ? "
                       "AND kind = 'robot'") // 3),
    }
    return [{"id": cid, "emoji": e, "title": t, "need": need, "have": min(have[cid], need), "done": have[cid] >= need}
            for cid, e, t, need in CHALLENGES]


def _state(conn, sid, s):
    return conn.execute("SELECT * FROM season_state WHERE student_id = ? AND season = ?", (sid, s["id"])).fetchone()


def premium(conn, sid, s, ch=None):
    st = _state(conn, sid, s)
    if st and st["premium"]:
        return True
    ch = ch if ch is not None else challenges(conn, sid, s)
    return sum(c["done"] for c in ch) >= PREMIUM_NEED


def claimed(conn, sid, s):
    return {(r["tier"], r["track"]) for r in conn.execute(
        "SELECT tier, track FROM season_claims WHERE student_id = ? AND season = ?", (sid, s["id"]))}


def overview(conn, sid, day=None):
    s = season_of(day)
    pts = points(conn, sid, s)
    tier = min(TIERS, pts // PER_TIER)
    ch = challenges(conn, sid, s)
    prem = premium(conn, sid, s, ch)
    got = claimed(conn, sid, s)
    rows = []
    for i in range(TIERS):
        n = i + 1
        rows.append({"n": n, "open": n <= tier,
                     "free": dict(FREE[i], claimed=(n, "free") in got),
                     "premium": dict(PREMIUM[i], claimed=(n, "premium") in got)})
    ready = sum(1 for r in rows if r["open"] and (not r["free"]["claimed"] or (prem and not r["premium"]["claimed"])))
    return {"season": s, "points": pts, "tier": tier, "to_next": 0 if tier >= TIERS else PER_TIER - pts % PER_TIER,
            "progress": 100 if tier >= TIERS else round(100 * (pts % PER_TIER) / PER_TIER),
            "challenges": ch, "premium": prem, "premium_need": PREMIUM_NEED, "rows": rows, "ready": ready,
            "manual_premium": bool((_state(conn, sid, s) or {"premium": 0})["premium"])}


# ------------------------------------------------------------------ награды
# Значки из дропов — виртуальные подарки: часто и приятно, в отличие от редких настоящих из магазина.
# Не пересекаются со значками пасса. Когда значки своей редкости собраны — дроп даёт только трофеи.
DROP_BADGES = {
    "Редкий": ["🍀", "🎈", "🍩", "🐱", "🦊", "🌻"],
    "Сверхредкий": ["🛸", "🎸", "🦄", "🐙", "🌈"],
    "Эпический": ["🔮", "🦅", "⚔️", "🧊"],
    "Мифический": ["🐲", "🌋", "🪐"],
    "Легендарный": ["👾", "🏯"],
}


def _give_drop_badge(conn, sid, rarity, rng):
    have = set(collection(conn, sid)["badges"])
    left = [b for b in DROP_BADGES[rarity] if b not in have]
    if not left:
        return None
    badge = rng.choice(left)
    n = conn.execute("SELECT COUNT(*) FROM season_claims WHERE student_id = ? AND season = 'drops'", (sid,)).fetchone()[0]
    conn.execute("INSERT INTO season_claims (student_id, season, tier, track, kind, value, claimed_at) "
                 "VALUES (?, 'drops', ?, 'drop', 'badge', ?, ?)", (sid, n + 1, badge, game.now_iso()))
    return badge


def roll_drop(conn, sid, why, rng=random, ref=None):
    """Открывает дроп: случайная редкость → немного трофеев и значок в коллекцию. Вызывать внутри `with conn:`."""
    roll = rng.uniform(0, 100)
    acc = 0
    for name, chance, amount, emoji in RARITIES:
        acc += chance
        if roll <= acc:
            break
    game.award(conn, sid, amount, "%s %s (%s)" % (T["drop"], name, why), "drop", ref, quiet=True)
    badge = _give_drop_badge(conn, sid, name, rng)
    game.add_notice(conn, sid, art.chest_img(name) or "⭐", "%s — %s %s! +%d 🏆%s" % (
        T["drop"], emoji, name, amount, " и значок %s в коллекцию" % badge if badge else ""),
        big=bool(badge) or name in ("Мифический", "Легендарный"))
    return {"rarity": name, "emoji": emoji, "amount": amount, "badge": badge}


def maybe_drop(conn, sid, why, rng=random):
    """Шанс дропа за первое решение задачи. Вызывать внутри `with conn:`."""
    today = config.today().isoformat()
    n = conn.execute("SELECT COUNT(*) FROM xp_events WHERE student_id = ? AND kind = 'drop' AND ref = 'solve' "
                     "AND created_at >= ?", (sid, today)).fetchone()[0]
    if n >= DROPS_PER_DAY or rng.random() >= DROP_CHANCE:
        return None
    return roll_drop(conn, sid, why, rng, ref="solve")


def claim(conn, sid, tier, track, rng=random):
    """Забрать награду ступени. Возвращает текст результата или None, если нельзя. Вызывать внутри `with conn:`."""
    ov = overview(conn, sid)
    if track not in ("free", "premium") or not 1 <= tier <= TIERS:
        return None
    row = ov["rows"][tier - 1]
    if not row["open"] or row[track]["claimed"] or (track == "premium" and not ov["premium"]):
        return None
    r = row[track]
    conn.execute("INSERT INTO season_claims (student_id, season, tier, track, kind, value, claimed_at) "
                 "VALUES (?, ?, ?, ?, ?, ?, ?)", (sid, ov["season"]["id"], tier, track, r["kind"], str(r["value"] or ""),
                                                  game.now_iso()))
    if r["kind"] == "trophies":
        game.award(conn, sid, r["value"], "Пасс сезона: ступень %d" % tier, "pass", quiet=True)
        return "+%d 🏆" % r["value"]
    if r["kind"] == "drop":
        d = roll_drop(conn, sid, "пасс, ступень %d" % tier, rng)
        return "%s — %s %s! +%d 🏆%s" % (T["drop"], d["emoji"], d["rarity"], d["amount"],
                                                 " и значок %s" % d["badge"] if d["badge"] else "")
    if r["kind"] == "badge":
        conn.execute("UPDATE users SET badge = ? WHERE id = ?", (r["value"], sid))
        return "Значок %s — теперь он рядом с твоим именем" % r["value"]
    title = r["value"] if r["value"] != "Чемпион сезона" else "Чемпион сезона «%s»" % ov["season"]["title"]
    conn.execute("UPDATE season_claims SET value = ? WHERE student_id = ? AND season = ? AND tier = ? AND track = ?",
                 (title, sid, ov["season"]["id"], tier, track))
    conn.execute("UPDATE users SET title = ? WHERE id = ?", (title, sid))
    return "Титул «%s»" % title


def collection(conn, sid):
    """Все полученные за всё время значки и титулы — чтобы можно было переключаться."""
    rows = conn.execute("SELECT DISTINCT kind, value FROM season_claims WHERE student_id = ? AND kind IN ('badge', 'title') "
                        "ORDER BY claimed_at", (sid,)).fetchall()
    return {"badges": [r["value"] for r in rows if r["kind"] == "badge"],
            "titles": [r["value"] for r in rows if r["kind"] == "title"]}


def equip(conn, sid, kind, value):
    have = collection(conn, sid)
    if kind == "badge" and (value in have["badges"] or value == ""):
        conn.execute("UPDATE users SET badge = ? WHERE id = ?", (value, sid))
        return True
    if kind == "title" and (value in have["titles"] or value == ""):
        conn.execute("UPDATE users SET title = ? WHERE id = ?", (value, sid))
        return True
    return False


def set_premium(conn, sid, on, day=None):
    s = season_of(day)
    conn.execute("INSERT INTO season_state (student_id, season, premium) VALUES (?, ?, ?) "
                 "ON CONFLICT(student_id, season) DO UPDATE SET premium = excluded.premium", (sid, s["id"], 1 if on else 0))
