"""«Разобраться» — короткая теория перед номером ОГЭ/ЕГЭ: правило, разобранный пример, типичные ошибки и «Углубиться».

Тексты лежат в app/content/theory/<экзамен>-<NN>.md (например, oge-math-09.md → oge-math-2026, №9).
На сайт попадает только проверенное: status: verified во frontmatter. Черновики (status: draft) лежат рядом и не
показываются, номер без теории работает как раньше — без шага.

Markdown разбирается здесь же, узким подмножеством: абзацы, **жирный**, *курсив*, `код`, блоки ```код```, списки,
таблицы, $формулы$ (→ MathML, app/texmath.py) и <details><summary> только в разделе «Углубиться». Любой другой HTML
в тексте экранируется — вставить скрипт или ссылку через файл теории нельзя.

Правило двух ошибок: таблица u2_theory считает ошибки подряд по номеру (подсказка после первой ошибки тоже ошибка).
После двух подряд тренажёр предлагает вернуться к теории; верный ответ или открытая теория обнуляют счётчик.
"""
import math
import re
from functools import lru_cache
from html import escape
from pathlib import Path

from markupsafe import Markup

from . import exam_model as em
from . import texmath

ROOT = Path(__file__).resolve().parent / "content" / "theory"
SECTIONS = {"Правило": "rule", "Разобранный пример": "example", "Типичные ошибки": "mistakes", "Углубиться": "deep"}
REQUIRED = ("rule", "example", "mistakes")
WRONG_IN_A_ROW = 2
WORDS_PER_MINUTE = 130            # спокойное чтение с формулами; «Углубиться» в оценку не входит

_SLUG = re.compile(r"^((?:oge|ege)-[a-z]+(?:-[a-z]+)?)-(\d{2})$")


# ---------------------------------------------------------------- markdown → безопасный HTML

_INLINE = re.compile(r"`([^`\n]+)`|\$\$(.+?)\$\$|\$([^$\n]+?)\$")


def inline(text):
    """Строка абзаца → HTML. Код и формулы заменяются метками до экранирования (так **жирный** может обнимать
    формулу), остальное экранируется целиком, потом метки возвращаются готовым HTML."""
    text = text.replace("\ue000", "").replace("\ue001", "")
    saved = []

    def keep(m):
        code, dmath, imath = m.groups()
        if code is not None:
            saved.append(f"<code>{escape(code)}</code>")
        else:
            saved.append(texmath.render(dmath if dmath is not None else imath))
        return f"\ue000{len(saved) - 1}\ue001"

    html = _emph(escape(_INLINE.sub(keep, text), quote=False))
    return re.sub("\ue000(\\d+)\ue001", lambda m: saved[int(m.group(1))], html)


def _emph(s):
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    return s


def _inline_join(lines):
    """Строки одного абзаца: два пробела в конце строки — перенос, иначе пробел. Формулы через перенос строки
    не режем: склеиваем строки до разбора."""
    out = []
    for i, ln in enumerate(lines):
        brk = ln.endswith("  ") and i < len(lines) - 1
        out.append(ln.strip() + ("\n" if brk else " "))
    text = "".join(out).strip()
    return "<br>".join(inline(chunk) for chunk in text.split("\n"))


_UL = re.compile(r"^\s{0,3}[-*•]\s+(.*)$")
_OL = re.compile(r"^\s{0,3}(\d+)[.)]\s+(.*)$")
_TABLE_SEP = re.compile(r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")


def _cells(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith("\\|"):
        line = line[:-1]
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", line)]   # «\|» — палка внутри ячейки


def blocks(md):
    """Markdown-фрагмент → HTML-блоки."""
    lines = md.replace("\r\n", "\n").split("\n")
    out, i, n = [], 0, len(lines)
    while i < n:
        line = lines[i]
        s = line.strip()
        if not s:
            i += 1
            continue
        if s.startswith("```"):
            lang = s[3:].strip()
            buf, i = [], i + 1
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            label = f' data-lang="{escape(lang)}"' if re.fullmatch(r"[\w+-]{1,20}", lang or "") else ""
            out.append(f'<pre class="th-code"{label}><code>{escape(chr(10).join(buf))}</code></pre>')
            continue
        if s.startswith("$$"):
            buf = [s[2:]]
            if s.endswith("$$") and len(s) > 3:
                buf = [s[2:-2]]
                i += 1
            else:
                i += 1
                while i < n and "$$" not in lines[i]:
                    buf.append(lines[i])
                    i += 1
                if i < n:
                    buf.append(lines[i].split("$$")[0])
                    i += 1
            out.append(f'<div class="th-math">{texmath.render(" ".join(buf).strip(), display=True)}</div>')
            continue
        if s.startswith("#"):
            level = min(len(s) - len(s.lstrip("#")), 4)
            out.append(f"<h{level}>{inline(s.lstrip('#').strip())}</h{level}>")
            i += 1
            continue
        if s.startswith("|") and i + 1 < n and _TABLE_SEP.match(lines[i + 1].strip()):
            head = _cells(s)
            rows, i = [], i + 2
            while i < n and lines[i].strip().startswith("|"):
                rows.append(_cells(lines[i]))
                i += 1
            th = "".join(f"<th>{inline(c)}</th>" for c in head)
            body = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows)
            out.append(f'<div class="th-table"><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>')
            continue
        if _UL.match(line) or _OL.match(line):
            ordered = bool(_OL.match(line))
            pat = _OL if ordered else _UL
            items, start = [], None
            while i < n and lines[i].strip():
                m = pat.match(lines[i])
                if m:
                    if ordered and start is None:
                        start = int(m.group(1))
                    items.append([m.group(2) if ordered else m.group(1)])
                elif lines[i].startswith((" ", "\t")) and items and not (_UL.match(lines[i]) or _OL.match(lines[i])):
                    items[-1].append(lines[i])
                else:
                    break
                i += 1
            tag = "ol" if ordered else "ul"
            attr = f' start="{start}"' if ordered and start not in (None, 1) else ""
            lis = "".join(f"<li>{_inline_join(it)}</li>" for it in items)
            out.append(f"<{tag}{attr}>{lis}</{tag}>")
            continue
        buf, i = [line], i + 1          # первая строка — всегда начало абзаца, даже если похожа на блок
        while i < n and lines[i].strip() and not _starts_block(lines, i) \
                and not _STEP.match(lines[i].strip()) and not _ANSWER.match(lines[i].strip()):
            buf.append(lines[i])
            i += 1
        out.append(_paragraph(buf))
    return out


def _starts_block(lines, i):
    s = lines[i].strip()
    if s.startswith(("```", "$$", "#")):
        return True
    if s.startswith("|") and i + 1 < len(lines) and _TABLE_SEP.match(lines[i + 1].strip()):
        return True
    return bool(_UL.match(lines[i]) or _OL.match(lines[i]))


_STEP = re.compile(r"^(\*\*)?Шаг\s+(\d+)\.\s*")
_ANSWER = re.compile(r"^(\*\*)?Ответ:")


def _paragraph(lines):
    first = lines[0].strip()
    m = _STEP.match(first)
    if m:
        # «**Шаг 2.** Текст» → номер в кружке и «Текст»; «**Шаг 2. Заголовок.**» → «**Заголовок.**»
        rest = ("**" if m.group(1) else "") + first[m.end():]
        if rest.startswith("****"):
            rest = rest[4:].lstrip()
        html = _inline_join([rest] + lines[1:])
        return (f'<div class="th-step"><span class="th-step-n" aria-label="Шаг {m.group(2)}">{m.group(2)}</span>'
                f'<p>{html}</p></div>')
    html = _inline_join(lines)
    if _ANSWER.match(first):
        return f'<p class="th-answer">{html}</p>'
    return f"<p>{html}</p>"


# ---------------------------------------------------------------- файлы теории

def _split(text):
    if not text.startswith("---"):
        raise ValueError("нет frontmatter")
    _, fm, body = text.split("---", 2)
    meta = {}
    for line in fm.strip().split("\n"):        # «ключ: значение»; двоеточие в значении — часть значения
        k, sep, v = line.partition(":")
        if sep and k.strip():
            meta[k.strip()] = v.strip()
    return meta, body


def _sections(body):
    title, cur, parts = None, None, {}
    for line in body.split("\n"):
        if line.startswith("# ") and title is None:
            title = line[2:].strip()
            continue
        if line.startswith("## "):
            cur = SECTIONS.get(line[3:].strip())
            if cur:
                parts[cur] = []
            continue
        if cur:
            parts[cur].append(line)
    return title, {k: "\n".join(v).strip() for k, v in parts.items()}


def _deep(md):
    """«Углубиться»: снимаем обёртку <details>, сворачивание рисует шаблон. Свой HTML внутри не пропускаем."""
    summary = None
    m = re.search(r"<summary>(.*?)</summary>", md, re.S)
    if m:
        summary = m.group(1).strip()
    md = re.sub(r"</?details>|<summary>.*?</summary>", "", md, flags=re.S)
    return summary, md.strip()


def _words(md):
    return len(re.findall(r"[^\W\d_]{2,}|\d+", md))


def parse(path):
    """Один файл → словарь для шаблона. Ошибка формата — ValueError (тест прогоняет все файлы)."""
    path = Path(path)
    m = _SLUG.match(path.stem)
    if not m:
        raise ValueError(f"{path.name}: имя должно быть вида oge-math-09.md")
    meta, body = _split(path.read_text(encoding="utf-8"))
    title, parts = _sections(body)
    missing = [k for k in REQUIRED if not parts.get(k)]
    if missing:
        raise ValueError(f"{path.name}: нет разделов {missing}")
    exam_id, key = f"{m.group(1)}-2026", int(m.group(2))
    if int(meta.get("kim_number", -1)) != key:
        raise ValueError(f"{path.name}: kim_number не совпадает с именем файла")
    summary, deep_md = _deep(parts.get("deep", ""))
    words = sum(_words(parts[k]) for k in REQUIRED)
    return {
        "exam_id": exam_id, "key": key, "slug": path.stem,
        "topic": str(meta.get("topic") or title or ""), "source": str(meta.get("source") or ""),
        "status": str(meta.get("status") or "draft"), "checked": str(meta.get("checked") or ""),
        "minutes": max(2, math.ceil(words / WORDS_PER_MINUTE)),
        # Markup: HTML собран из экранированного текста здесь же, шаблону его повторно экранировать не нужно
        "rule": Markup("".join(blocks(parts["rule"]))), "example": Markup("".join(blocks(parts["example"]))),
        "mistakes": Markup("".join(blocks(parts["mistakes"]))),
        "deep": Markup("".join(blocks(deep_md))) if deep_md else "",
        "deep_summary": summary or "Если осталось время и хочется глубже",
    }


@lru_cache(maxsize=1)
def _all():
    out = {}
    for path in sorted(ROOT.glob("*.md")):
        item = parse(path)
        out[(item["exam_id"], item["key"])] = item
    return out


def all_items():
    """Все файлы, включая черновики (для тестов и проверки контента)."""
    return dict(_all())


def get(exam_id, key):
    """Проверенная теория номера или None — тогда шага «Разобраться» нет."""
    item = _all().get((exam_id, key))
    return item if item and item["status"] == "verified" else None


def has(exam_id, key):
    return get(exam_id, key) is not None


def keys_for(exam_id):
    return {k for (e, k), it in _all().items() if e == exam_id and it["status"] == "verified"}


def valid_for_exam(item):
    """Номер из файла есть в модели экзамена (иначе на страницу не попасть)."""
    try:
        return item["key"] in em.points(em.load(item["exam_id"]))
    except (FileNotFoundError, KeyError):
        return False


# ---------------------------------------------------------------- прогресс ученика

def state(conn, sid, exam_id, key):
    row = conn.execute("SELECT seen_at, wrong_streak FROM u2_theory WHERE student_id = ? AND exam_id = ? AND task_key = ?",
                       (sid, exam_id, str(key))).fetchone()
    return {"seen": bool(row and row[0]), "streak": row[1] if row else 0}


def mark_seen(conn, sid, exam_id, key, today):
    """Открыл теорию: шаг пройден, счётчик ошибок подряд обнулён."""
    with conn:
        conn.execute(
            "INSERT INTO u2_theory (student_id, exam_id, task_key, seen_at, wrong_streak) VALUES (?, ?, ?, ?, 0) "
            "ON CONFLICT(student_id, exam_id, task_key) DO UPDATE SET seen_at = excluded.seen_at, wrong_streak = 0",
            (sid, exam_id, str(key), today.isoformat()))


def note_answer(conn, sid, exam_id, key, ok):
    """Учитывает ответ. Возвращает True, если пора предложить теорию (две ошибки подряд и теория есть)."""
    if not has(exam_id, key):
        return False
    with conn:
        if ok:
            conn.execute("UPDATE u2_theory SET wrong_streak = 0 WHERE student_id = ? AND exam_id = ? AND task_key = ?",
                         (sid, exam_id, str(key)))
            return False
        conn.execute(
            "INSERT INTO u2_theory (student_id, exam_id, task_key, seen_at, wrong_streak) VALUES (?, ?, ?, NULL, 1) "
            "ON CONFLICT(student_id, exam_id, task_key) DO UPDATE SET wrong_streak = wrong_streak + 1",
            (sid, exam_id, str(key)))
    return state(conn, sid, exam_id, key)["streak"] >= WRONG_IN_A_ROW


def seen_keys(conn, sid, exam_id):
    """Номера экзамена, теорию которых ученик уже открывал (ключи — строки, как в таблице)."""
    return {r[0] for r in conn.execute(
        "SELECT task_key FROM u2_theory WHERE student_id = ? AND exam_id = ? AND seen_at IS NOT NULL", (sid, exam_id))}


def fit_plan(exam_id, items, budget, seen):
    """План дня с теорией: непрочитанная теория номера входит в минуты дня, и план не выходит за budget.

    Номер, который «не влезает» вместе с теорией, сначала теряет повторы (× 2 → × 1), потом выпадает целиком.
    Каждому пункту добавляет theory — минуты теории (0, если теории нет или она уже прочитана)."""
    out, used = [], 0
    for it in items:
        th = get(exam_id, it["n"])
        extra = th["minutes"] if th and str(it["n"]) not in seen else 0
        times = it.get("times", 1) or 1
        per = max(1, it["minutes"] // times)
        while times and used + per * times + extra > budget:
            times -= 1
        if not times:
            continue
        it = {**it, "times": times, "minutes": per * times + extra, "theory": extra}
        used += it["minutes"]
        out.append(it)
    return out


def offer(conn, sid, exam_id, key):
    return has(exam_id, key) and state(conn, sid, exam_id, key)["streak"] >= WRONG_IN_A_ROW
