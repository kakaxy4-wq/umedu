"""Кабинет преподавателя: ученики, уроки, проверка ДЗ, награды, журнал, сводки, аналитика.

Маршруты вынесены из main.py; общие функции берутся оттуда. Подключается в конце main.py.
"""
import re

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from . import analytics, auth, config, family, forecast, game, levels, notify, russian, season, students, subjects, weekly
from .db import get_db, get_setting, set_setting
from .content.checks import CHECKS, CHECK_BY_ID
from .content.glossary import terms_in
from .content.guides import CARDS, DRAFT_GUIDES, GUIDE_DIR, STEPS, has_guide
from .content.lessons import LESSONS, LESSON_BY_NUM, MODULES, MODULE_BY_NUM
from .content.tasks import TASKS, TASK_BY_ID
from .main import back, check_states, need_sid, oge_progress, render, select_student, subject_id, target_student

router = APIRouter()


def safe_next(path, default="/"):
    return path if path.startswith("/") and not path.startswith("//") else default


@router.get("/teacher/checks", response_class=HTMLResponse)
def teacher_checks(request: Request, student: int = 0, conn=Depends(get_db), user=Depends(auth.teacher_required)):
    if student:
        select_student(conn, user, student)
    sid = need_sid(conn, user)
    states, results = check_states(conn, sid)
    everyone = students.list_students(conn)
    matrix = {(r["student_id"], r["check_id"]): r for r in conn.execute(
        "SELECT student_id, check_id, right_count, total FROM check_results")}
    grade = (students.get_student(conn, sid) or {"grade": None})["grade"] if sid else None
    return render(request, "teacher/checks.html", conn, user, sid=sid, states=states, results=results,
                  checks=[c for c in CHECKS if c["subject"] in config.SUBJECTS
                          and (not grade or not c.get("grade") or c["grade"] == grade)],
                  modules=MODULE_BY_NUM, everyone=everyone, matrix=matrix)


@router.post("/teacher/check/{cid}/open")
def teacher_check_open(cid: str, student_id: int = Form(0), conn=Depends(get_db), user=Depends(auth.check_csrf)):
    sid = target_student(conn, user, student_id)
    check = CHECK_BY_ID.get(cid)
    if not check:
        raise HTTPException(404)
    with conn:
        conn.execute("INSERT INTO check_state (student_id, id, opened_at) VALUES (?, ?, ?) "
                     "ON CONFLICT(student_id, id) DO UPDATE SET opened_at = COALESCE(opened_at, excluded.opened_at)",
                     (sid, cid, game.now_iso()))
        game.add_notice(conn, sid, check["emoji"], "Открыта проверка «%s»!" % check["title"], big=True)
    return back("/teacher/checks?student=%d" % sid)


@router.post("/teacher/check/{cid}/reset")
def teacher_check_reset(cid: str, student_id: int = Form(0), conn=Depends(get_db), user=Depends(auth.check_csrf)):
    """Разрешить пройти ещё раз: результат удаляется, трофеи за участие остаются (повторно не начисляются)."""
    sid = target_student(conn, user, student_id)
    if cid not in CHECK_BY_ID:
        raise HTTPException(404)
    with conn:
        conn.execute("DELETE FROM check_results WHERE student_id = ? AND check_id = ?", (sid, cid))
        conn.execute("UPDATE check_state SET started_at = NULL WHERE student_id = ? AND id = ?", (sid, cid))
    return back("/teacher/checks?student=%d" % sid)


@router.post("/teacher/student/{sid}/premium")
def teacher_premium(sid: int, on: str = Form(""), conn=Depends(get_db), user=Depends(auth.check_csrf)):
    sid = target_student(conn, user, sid)
    with conn:
        season.set_premium(conn, sid, bool(on))
        if on:
            game.add_notice(conn, sid, "🎟️", "Преподаватель открыл тебе премиум-дорожку пасса!", big=True)
    return back("/season")


@router.post("/teacher/student/{sid}/subjects")
def teacher_student_subjects(sid: int, python: str = Form(""), russian_on: str = Form("", alias="russian"),
                             next: str = Form(""), conn=Depends(get_db), user=Depends(auth.check_csrf)):
    sid = target_student(conn, user, sid)
    chosen = [n for n, on in (("python", python), ("russian", russian_on)) if on]
    with conn:
        conn.execute("UPDATE users SET subjects = ? WHERE id = ?", (subjects.serialize(chosen), sid))
        if "russian" in chosen:
            conn.execute("INSERT OR IGNORE INTO check_state (student_id, id, opened_at) VALUES (?, 'ru_entry', ?)",
                         (sid, game.now_iso()))
            game.add_notice(conn, sid, "📖", "Подключён русский язык: тренажёры запятых и букв!", big=True)
    return back("/teacher" if next == "/teacher" else "/teacher/student/%d" % sid)


@router.post("/teacher/student/{sid}/level")
def teacher_student_level(sid: int, level: str = Form(...), age: str = Form(""), start: int = Form(0),
                          calm: str = Form(""), calm_set: str = Form(""), self_pace: str = Form(""),
                          conn=Depends(get_db), user=Depends(auth.check_csrf)):
    sid = target_student(conn, user, sid)
    if level not in levels.LEVELS:
        raise HTTPException(400)
    age_val = int(age) if age.strip().isdigit() and 6 <= int(age) <= 25 else None
    with conn:
        conn.execute("UPDATE users SET level = ?, age = ? WHERE id = ?", (level, age_val, sid))
        if calm_set:                       # галочка есть только в основной форме, не в «Принять рекомендацию»
            conn.execute("UPDATE users SET calm = ?, self_paced = ? WHERE id = ?", (1 if calm else 0, 1 if self_pace else 0, sid))
    if start in LESSON_BY_NUM and start > game.unlocked_upto(conn, sid):
        return teacher_open(start, sid, conn, user)
    return back("/teacher/student/%d#level" % sid)


@router.post("/teacher/certificates")
def teacher_cert_create(emoji: str = Form("🏅"), title: str = Form(...), reason: str = Form(...),
                        issued_at: str = Form(""), student_id: int = Form(0),
                        conn=Depends(get_db), user=Depends(auth.check_csrf)):
    sid = target_student(conn, user, student_id)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", issued_at.strip()):
        issued_at = game.now_iso()
    with conn:
        conn.execute("INSERT INTO certificates (student_id, emoji, title, reason, issued_at) VALUES (?, ?, ?, ?, ?)",
                     (sid, (emoji.strip() or "🏅")[:8], title.strip()[:80], reason.strip()[:240], issued_at.strip()))
        game.add_notice(conn, sid, emoji.strip() or "🏅", "Тебе вручили грамоту «%s»!" % title.strip()[:80], big=True)
    return back("/certificates")


@router.post("/teacher/certificates/{cid}/delete")
def teacher_cert_delete(cid: int, conn=Depends(get_db), user=Depends(auth.check_csrf)):
    auth.teacher_required(user)
    with conn:
        conn.execute("DELETE FROM certificates WHERE id = ?", (cid,))
    return back("/certificates")


@router.post("/teacher/cert-name")
def teacher_cert_name(name: str = Form(""), signer: str = Form(""), student_id: int = Form(0),
                      conn=Depends(get_db), user=Depends(auth.check_csrf)):
    sid = target_student(conn, user, student_id)
    with conn:
        conn.execute("UPDATE users SET full_name = ? WHERE id = ?", (name.strip()[:80], sid))
        set_setting(conn, "cert_teacher", signer.strip()[:80] or None)
    return back("/certificates")


@router.post("/teacher/select")
def teacher_select(student_id: int = Form(...), next: str = Form("/teacher"), conn=Depends(get_db),
                   user=Depends(auth.check_csrf)):
    auth.teacher_required(user)
    select_student(conn, user, student_id)
    return back(safe_next(next, "/teacher"))


@router.get("/teacher/students", response_class=HTMLResponse)
def teacher_students(request: Request, archived: int = 0, conn=Depends(get_db), user=Depends(auth.teacher_required)):
    rows = [students.overview(conn, s["id"]) for s in students.list_students(conn, include_archived=bool(archived))]
    return render(request, "teacher/students.html", conn, user, rows=rows, archived=archived,
                  board=students.leaderboard(conn), board_on=students.leaderboard_enabled(conn),
                  limit=students.MAX_STUDENTS)


def _access_card(request, conn, user, sid, password, created):
    st = students.get_student(conn, sid)
    return render(request, "teacher/access_card.html", conn, user, sid=sid, st=st, password=password, created=created,
                  site_url=config.BASE_URL or str(request.base_url).rstrip("/"))


@router.post("/teacher/students", response_class=HTMLResponse)
def teacher_student_create(request: Request, display_name: str = Form(...), full_name: str = Form(""),
                           username: str = Form(""), grade: int = Form(0), price: str = Form(""),
                           conn=Depends(get_db), user=Depends(auth.check_csrf)):
    auth.teacher_required(user)
    display_name = display_name.strip()[:40]
    if not display_name:
        raise HTTPException(400, "Нужно имя ученика")
    if conn.execute("SELECT COUNT(*) FROM users WHERE role = 'student' AND active = 1").fetchone()[0] >= students.MAX_STUDENTS:
        raise HTTPException(400, "Слишком много учеников. Отправь кого-нибудь в архив.")
    login_name = username.strip().lower() or students.suggest_login(conn, display_name)
    if not students.valid_login(login_name):
        raise HTTPException(400, "Логин: латинские буквы, цифры, точка, дефис — от 2 до 32 символов")
    if conn.execute("SELECT 1 FROM users WHERE username = ?", (login_name,)).fetchone():
        raise HTTPException(400, "Логин «%s» уже занят" % login_name)
    password = students.generate_password()
    with conn:
        sid = students.create_student(conn, login_name, display_name, password, full_name.strip()[:80], grade=grade)
        if price.strip().isdigit():
            conn.execute("UPDATE users SET price = ? WHERE id = ?", (int(price), sid))
    select_student(conn, user, sid)
    # пароль показываем один раз прямо в ответе: в адресе, логах и базе его нет
    return _access_card(request, conn, user, sid, password, created=True)


@router.get("/teacher/student/{sid}", response_class=HTMLResponse)
def teacher_student(sid: int, request: Request, conn=Depends(get_db), user=Depends(auth.teacher_required)):
    if config.CHEM_SITE:
        return back("/chem/teacher/student/%d" % sid)
    if not students.get_student(conn, sid):
        raise HTTPException(404)
    select_student(conn, user, sid)
    ov = students.overview(conn, sid)
    lessons = game.lesson_list_with_state(conn, sid)
    states = {r["num"]: r for r in conn.execute("SELECT * FROM lesson_state WHERE student_id = ?", (sid,))}
    results = conn.execute("SELECT * FROM check_results WHERE student_id = ? ORDER BY finished_at", (sid,)).fetchall()
    subs = conn.execute("SELECT * FROM submissions WHERE student_id = ? ORDER BY id DESC LIMIT 20", (sid,)).fetchall()
    events = conn.execute("SELECT * FROM xp_events WHERE student_id = ? ORDER BY id DESC LIMIT 15", (sid,)).fetchall()
    st = ov["student"]
    parent_url = ((config.BASE_URL or str(request.base_url).rstrip("/")) + "/parent/" + st["parent_token"]) \
        if st["parent_token"] else ""
    rec = levels.recommend(st["age"], levels.entry_scores(conn, sid))
    return render(request, "teacher/student.html", conn, user, sid=sid, ov=ov, lessons=lessons, states=states,
                  fc=forecast.forecast(oge_progress(conn, sid)),
                  rec=rec, level_id=levels.of(st),
                  results=[(CHECK_BY_ID[r["check_id"]], r) for r in results if r["check_id"] in CHECK_BY_ID],
                  subs=subs, events=events, parent_url=parent_url, family_parents=family.parents_of(conn, sid),
                  ru=russian.teacher_view(conn, sid) if "russian" in subjects.of(st) else None,
                  alerts=[a for a in students.alerts(conn) if a["student_id"] == sid])


@router.post("/teacher/student/{sid}/edit")
def teacher_student_edit(sid: int, display_name: str = Form(...), full_name: str = Form(""), notes: str = Form(""),
                         conn=Depends(get_db), user=Depends(auth.check_csrf)):
    sid = target_student(conn, user, sid)
    with conn:
        conn.execute("UPDATE users SET display_name = ?, full_name = ?, notes = ? WHERE id = ?",
                     (display_name.strip()[:40] or "Ученик", full_name.strip()[:80], notes[:10_000], sid))
    return back("/teacher/student/%d" % sid)


@router.post("/teacher/student/{sid}/password", response_class=HTMLResponse)
def teacher_student_password(sid: int, request: Request, conn=Depends(get_db), user=Depends(auth.check_csrf)):
    sid = target_student(conn, user, sid)
    password = students.generate_password()
    with conn:
        students.set_password(conn, sid, password)
    return _access_card(request, conn, user, sid, password, created=False)


@router.post("/teacher/student/{sid}/archive")
def teacher_student_archive(sid: int, active: int = Form(0), conn=Depends(get_db), user=Depends(auth.check_csrf)):
    sid = target_student(conn, user, sid)
    with conn:
        students.set_active(conn, sid, bool(active))
        if not active:
            conn.execute("UPDATE users SET current_student_id = NULL WHERE current_student_id = ?", (sid,))
    return back("/teacher/students" if not active else "/teacher/student/%d" % sid)


@router.post("/teacher/student/{sid}/parent-unlink")
def teacher_parent_unlink(sid: int, parent_id: int = Form(...), conn=Depends(get_db), user=Depends(auth.check_csrf)):
    if user["role"] != "teacher":
        raise HTTPException(403)
    with conn:
        family.unlink(conn, parent_id, sid)
    return back("/teacher/student/%d#parent" % sid)


@router.post("/teacher/student/{sid}/parent-link")
def teacher_parent_link(sid: int, action: str = Form("new"), conn=Depends(get_db), user=Depends(auth.check_csrf)):
    sid = target_student(conn, user, sid)
    with conn:
        if action == "revoke":
            conn.execute("UPDATE users SET parent_token = NULL WHERE id = ?", (sid,))
        else:
            students.new_parent_token(conn, sid)  # новая ссылка — старая сразу перестаёт работать
    return back("/teacher/student/%d#parent" % sid)


@router.post("/teacher/leaderboard")
def teacher_leaderboard(enabled: str = Form(""), conn=Depends(get_db), user=Depends(auth.check_csrf)):
    auth.teacher_required(user)
    with conn:
        set_setting(conn, "leaderboard", "1" if enabled else "0")
    return back("/teacher/students")


# ------------------------------------------------------------------ преподаватель: пульт и уроки
@router.get("/teacher", response_class=HTMLResponse)
def teacher_home(request: Request, conn=Depends(get_db), user=Depends(auth.teacher_required)):
    if config.CHEM_SITE:
        return back("/chem/teacher")
    sid = subject_id(conn, user)
    if not sid:
        return back("/teacher/students")
    pending = conn.execute("SELECT s.*, u.display_name AS who FROM submissions s JOIN users u ON u.id = s.student_id "
                           "WHERE s.status = 'pending' ORDER BY s.id").fetchall()
    purchases = conn.execute("SELECT p.*, u.display_name AS who FROM purchases p JOIN users u ON u.id = p.student_id "
                             "WHERE p.status = 'requested' ORDER BY p.id").fetchall()
    events = conn.execute("SELECT * FROM xp_events WHERE student_id = ? ORDER BY id DESC LIMIT 15", (sid,)).fetchall()
    upto = game.unlocked_upto(conn, sid)
    week = conn.execute(
        "SELECT substr(created_at, 1, 10) AS day, SUM(amount) AS xp, COUNT(*) AS n FROM xp_events "
        "WHERE student_id = ? AND created_at >= date('now', '-13 days') GROUP BY day ORDER BY day", (sid,)).fetchall()
    attempts_week = conn.execute("SELECT COUNT(*) FROM task_attempts WHERE student_id = ? AND "
                                 "created_at >= date('now', '-7 days')", (sid,)).fetchone()[0]
    return render(request, "teacher/home.html", conn, user, sid=sid, pending=pending, purchases=purchases, events=events,
                  current=LESSON_BY_NUM.get(upto), upto=upto, week=week, attempts_week=attempts_week,
                  current_guide=has_guide(upto), next_lesson_at=students.get_student(conn, sid)["next_lesson_at"] or "",
                  state=conn.execute("SELECT * FROM lesson_state WHERE student_id = ? AND num = ?", (sid, upto)).fetchone(),
                  alerts=students.alerts(conn),
                  roster=[students.overview(conn, s["id"]) for s in students.list_students(conn)])


@router.get("/teacher/analytics", response_class=HTMLResponse)
def teacher_analytics(request: Request, conn=Depends(get_db), user=Depends(auth.teacher_required)):
    return render(request, "teacher/analytics.html", conn, user, a=analytics.report(conn))


@router.get("/teacher/weekly", response_class=HTMLResponse)
def teacher_weekly(request: Request, sent: int = -1, conn=Depends(get_db), user=Depends(auth.teacher_required)):
    summary = weekly.build(conn)
    return render(request, "teacher/weekly.html", conn, user, w=summary, text=weekly.text(summary),
                  configured=weekly.configured(), sent=sent, last_sent=get_setting(conn, "weekly_sent"))


@router.post("/teacher/weekly/send")
def teacher_weekly_send(conn=Depends(get_db), user=Depends(auth.check_csrf)):
    if user["role"] != "teacher":
        raise HTTPException(403)
    ok = weekly.configured() and notify.send_now(weekly.text(weekly.build(conn)))
    return back("/teacher/weekly?sent=%d" % (1 if ok else 0))


@router.get("/teacher/lessons", response_class=HTMLResponse)
def teacher_lessons(request: Request, conn=Depends(get_db), user=Depends(auth.teacher_required)):
    sid = need_sid(conn, user)
    lessons = game.lesson_list_with_state(conn, sid)
    states = {r["num"]: r for r in conn.execute("SELECT * FROM lesson_state WHERE student_id = ?", (sid,))}
    return render(request, "teacher/lessons.html", conn, user, sid=sid, lessons=lessons, states=states, modules=MODULES,
                  upto=game.unlocked_upto(conn, sid), guides={l["num"] for l in LESSONS if has_guide(l["num"])})


@router.post("/teacher/lesson/{num}/open")
def teacher_open(num: int, student_id: int = Form(0), conn=Depends(get_db), user=Depends(auth.check_csrf)):
    sid = target_student(conn, user, student_id)
    if num not in LESSON_BY_NUM:
        raise HTTPException(404)
    with conn:
        game.open_lesson(conn, sid, num)
    return back("/teacher/lessons#l%d" % num)


@router.post("/teacher/lesson/{num}/done")
def teacher_done(num: int, student_id: int = Form(0), conn=Depends(get_db), user=Depends(auth.check_csrf)):
    sid = target_student(conn, user, student_id)
    if num not in LESSON_BY_NUM or num > game.unlocked_upto(conn, sid):
        raise HTTPException(400, "Урок ещё не открыт")
    with conn:
        game.mark_lesson_done(conn, sid, num)
    return back("/teacher/lessons#l%d" % num)


@router.post("/teacher/lesson/{num}/undone")
def teacher_undone(num: int, student_id: int = Form(0), conn=Depends(get_db), user=Depends(auth.check_csrf)):
    """Отменить «Проведено», нажатое по ошибке: снимаем отметку и забираем +20 за это занятие."""
    sid = target_student(conn, user, student_id)
    with conn:
        conn.execute("UPDATE lesson_state SET done_at = NULL WHERE student_id = ? AND num = ?", (sid, num))
        conn.execute("DELETE FROM xp_events WHERE student_id = ? AND kind = 'lesson' AND ref = ?", (sid, str(num)))
    return back("/teacher/lessons#l%d" % num)


@router.post("/teacher/lesson/{num}/note")
def teacher_note(num: int, note: str = Form(""), student_id: int = Form(0), conn=Depends(get_db),
                 user=Depends(auth.check_csrf)):
    sid = target_student(conn, user, student_id)
    with conn:
        conn.execute("INSERT OR IGNORE INTO lesson_state (student_id, num) VALUES (?, ?)", (sid, num))
        conn.execute("UPDATE lesson_state SET teacher_note = ? WHERE student_id = ? AND num = ?", (note[:10_000], sid, num))
    return back("/lesson/%d" % num)


@router.get("/teacher/guide/{num}", response_class=HTMLResponse)
def teacher_guide(num: int, request: Request, conn=Depends(get_db), user=Depends(auth.teacher_required)):
    lesson = LESSON_BY_NUM.get(num)
    if not lesson or not has_guide(num):
        raise HTTPException(404, "Для этого урока подготовка ещё не написана")
    source = (GUIDE_DIR / ("lesson_%d.html" % num)).read_text(encoding="utf-8")
    source += " ".join(c["front"] + " " + c["back"] for c in CARDS.get(num, []))
    source += " ".join(s for part in (STEPS.get(num) or {}).values() for s in part)
    return render(request, "teacher/guide.html", conn, user, lesson=lesson, cards=CARDS.get(num, []),
                  steps=STEPS.get(num), glossary=terms_in(source), draft=num in DRAFT_GUIDES)


@router.get("/teacher/guide/{num}/cards", response_class=HTMLResponse)
def teacher_guide_cards(num: int, request: Request, conn=Depends(get_db), user=Depends(auth.teacher_required)):
    lesson = LESSON_BY_NUM.get(num)
    if not lesson or not CARDS.get(num):
        raise HTTPException(404)
    return render(request, "guide_cards.html", conn, user, lesson=lesson, cards=CARDS[num])


@router.post("/teacher/schedule")
def teacher_schedule(next_lesson_at: str = Form(""), student_id: int = Form(0), conn=Depends(get_db),
                     user=Depends(auth.check_csrf)):
    sid = target_student(conn, user, student_id)
    value = next_lesson_at.strip()
    if value and not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", value):
        raise HTTPException(400, "Неверная дата")
    with conn:
        conn.execute("UPDATE users SET next_lesson_at = ? WHERE id = ?", (value or None, sid))
    return back("/teacher")


@router.post("/teacher/xp")
def teacher_xp(amount: int = Form(...), reason: str = Form(...), student_id: int = Form(0), conn=Depends(get_db),
               user=Depends(auth.check_csrf)):
    sid = target_student(conn, user, student_id)
    amount = max(-500, min(500, amount))
    with conn:
        game.award(conn, sid, amount, reason.strip()[:200] or "Бонус от преподавателя", "manual")
    return back("/teacher")


@router.get("/teacher/reviews", response_class=HTMLResponse)
def teacher_reviews(request: Request, conn=Depends(get_db), user=Depends(auth.teacher_required)):
    q = "SELECT s.*, u.display_name AS who FROM submissions s JOIN users u ON u.id = s.student_id "
    pending = conn.execute(q + "WHERE s.status = 'pending' ORDER BY s.id").fetchall()
    done = conn.execute(q + "WHERE s.status != 'pending' ORDER BY s.id DESC LIMIT 40").fetchall()
    return render(request, "teacher/reviews.html", conn, user, pending=pending, done=done, lessons=LESSON_BY_NUM)


@router.post("/teacher/review/{sub_id}")
def teacher_review(sub_id: int, action: str = Form(...), comment: str = Form(""), xp: int = Form(0),
                   star_ok: str = Form(""), conn=Depends(get_db), user=Depends(auth.check_csrf)):
    auth.teacher_required(user)
    sub = conn.execute("SELECT * FROM submissions WHERE id = ?", (sub_id,)).fetchone()
    if not sub or sub["status"] != "pending":
        return back("/teacher/reviews")
    sid = sub["student_id"]
    title = LESSON_BY_NUM[sub["lesson"]]["title"]
    with conn:
        if action == "approve":
            already = conn.execute("SELECT COALESCE(SUM(xp_awarded), 0) FROM submissions WHERE student_id = ? AND lesson = ?",
                                   (sid, sub["lesson"])).fetchone()[0]
            star = 1 if (star_ok and sub["star"]) else 0
            total = max(0, min(100, xp)) + (game.XP_HOMEWORK_STAR if star else 0)
            conn.execute("UPDATE submissions SET status = 'approved', teacher_comment = ?, xp_awarded = ?, star = ?, "
                         "reviewed_at = ? WHERE id = ?", (comment[:5000], total, star, game.now_iso(), sub_id))
            game.add_notice(conn, sid, "✅", "Домашка к уроку %d принята!%s" % (
                sub["lesson"], (" «%s»" % comment[:80]) if comment else ""), big=True)
            if total and not already:
                game.award(conn, sid, total, "Домашка к уроку %d «%s»%s" % (sub["lesson"], title, " ⭐" if star else ""),
                           "homework", str(sub["lesson"]))
            else:
                game.sync_achievements(conn, sid)
        else:
            conn.execute("UPDATE submissions SET status = 'returned', teacher_comment = ?, reviewed_at = ? WHERE id = ?",
                         (comment[:5000], game.now_iso(), sub_id))
            game.add_notice(conn, sid, "🔧", "Домашку к уроку %d нужно доработать: %s" % (sub["lesson"], comment[:120]))
    return back("/teacher/reviews")


@router.get("/teacher/rewards", response_class=HTMLResponse)
def teacher_rewards(request: Request, conn=Depends(get_db), user=Depends(auth.teacher_required)):
    rewards = conn.execute("SELECT * FROM rewards ORDER BY active DESC, cost").fetchall()
    purchases = conn.execute("SELECT p.*, u.display_name AS who FROM purchases p JOIN users u ON u.id = p.student_id "
                             "ORDER BY p.id DESC LIMIT 60").fetchall()
    return render(request, "teacher/rewards.html", conn, user, rewards=rewards, purchases=purchases)


@router.post("/teacher/rewards")
def teacher_reward_add(emoji: str = Form("🎁"), title: str = Form(...), cost: int = Form(...),
                       conn=Depends(get_db), user=Depends(auth.check_csrf)):
    auth.teacher_required(user)
    with conn:
        conn.execute("INSERT INTO rewards (emoji, title, cost) VALUES (?, ?, ?)",
                     ((emoji.strip() or "🎁")[:8], title.strip()[:120], max(1, cost)))
    return back("/teacher/rewards")


@router.post("/teacher/rewards/{rid}/toggle")
def teacher_reward_toggle(rid: int, conn=Depends(get_db), user=Depends(auth.check_csrf)):
    auth.teacher_required(user)
    with conn:
        conn.execute("UPDATE rewards SET active = 1 - active WHERE id = ?", (rid,))
    return back("/teacher/rewards")


@router.post("/teacher/purchase/{pid}")
def teacher_purchase(pid: int, action: str = Form(...), conn=Depends(get_db), user=Depends(auth.check_csrf)):
    auth.teacher_required(user)
    row = conn.execute("SELECT * FROM purchases WHERE id = ? AND status = 'requested'", (pid,)).fetchone()
    if row:
        sid = row["student_id"]
        status = "given" if action == "give" else "declined"
        with conn:
            conn.execute("UPDATE purchases SET status = ?, resolved_at = ? WHERE id = ?", (status, game.now_iso(), pid))
            if status == "given":
                game.add_notice(conn, sid, "🎁", "Награда «%s» выдана! Наслаждайся 🎉" % row["title"], big=True)
            else:
                game.add_notice(conn, sid, "↩️", "Запрос «%s» отклонён, гемы вернулись" % row["title"])
            game.sync_achievements(conn, sid)
    return back("/teacher/rewards")


@router.get("/teacher/solutions", response_class=HTMLResponse)
def teacher_solutions(request: Request, conn=Depends(get_db), user=Depends(auth.teacher_required)):
    sid = need_sid(conn, user)
    rows = conn.execute("SELECT task_id, COUNT(*) AS n, SUM(passed) AS ok, MAX(created_at) AS last "
                        "FROM task_attempts WHERE student_id = ? GROUP BY task_id", (sid,)).fetchall()
    by_task = {r["task_id"]: r for r in rows}
    return render(request, "teacher/solutions.html", conn, user, sid=sid, tasks=TASKS, by_task=by_task, lessons=LESSON_BY_NUM)


@router.get("/teacher/attempts/{task_id}", response_class=HTMLResponse)
def teacher_attempts(task_id: str, request: Request, student: int = 0, conn=Depends(get_db),
                     user=Depends(auth.teacher_required)):
    task = TASK_BY_ID.get(task_id)
    if not task:
        raise HTTPException(404)
    if student:
        select_student(conn, user, student)
    sid = need_sid(conn, user)
    attempts = conn.execute("SELECT * FROM task_attempts WHERE student_id = ? AND task_id = ? ORDER BY id DESC LIMIT 30",
                            (sid, task_id)).fetchall()
    return render(request, "teacher/attempts.html", conn, user, sid=sid, task=task, attempts=attempts)


@router.get("/teacher/journal", response_class=HTMLResponse)
def teacher_journal(request: Request, conn=Depends(get_db), user=Depends(auth.teacher_required)):
    sid = need_sid(conn, user)
    events = conn.execute("SELECT * FROM xp_events WHERE student_id = ? ORDER BY id DESC LIMIT 300", (sid,)).fetchall()
    return render(request, "teacher/journal.html", conn, user, sid=sid, events=events)
