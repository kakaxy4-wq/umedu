"""Родителям: страница по секретной ссылке, кабинет родителя, политика ПДн, лендинг.

Маршруты вынесены из main.py; общие функции берутся оттуда. Подключается в конце main.py.
"""
from datetime import timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from . import auth, certificates, config, family, forecast, game, russian, students, subjects, theme
from .db import get_db
from .content.checks import CHECK_BY_ID
from .main import FamilyLogin, back, cert_signer, oge_progress, render

router = APIRouter()


@router.get("/welcome", response_class=HTMLResponse)
def welcome(request: Request, conn=Depends(get_db)):
    """Лендинг публичного сайта: что это, для кого, как устроено. На семейном сайте не нужен."""
    if theme.THEME != "public":
        return back("/login")
    return render(request, "landing.html", conn, None, contact=config.CONTACT, student_name="")


# ------------------------------------------------------------------ родителям: прогресс по секретной ссылке
def _parent_student(conn, token):
    st = students.by_parent_token(conn, token)
    if not st:
        raise HTTPException(404, "Ссылка устарела. Попросите у преподавателя новую.")
    return st


@router.get("/parent/{token}", response_class=HTMLResponse)
def parent_page(token: str, request: Request, conn=Depends(get_db)):
    st = _parent_student(conn, token)
    sid = st["id"]
    if config.CHEM_SITE:
        from . import chem
        return render(request, "chem/parent.html", conn, None, st=st, card=chem.student_card(conn, sid),
                      lessons=chem.lessons(conn, sid, limit=40), pays=chem.payments(conn, sid, 20),
                      hw=chem.hw_list(conn, sid)[:20], statuses=chem.STATUSES, grades=chem.GRADES,
                      files=chem.lesson_files(conn, sid), token=token)
    fam = family.load(request, conn)
    linked = bool(fam and conn.execute("SELECT 1 FROM parent_children WHERE parent_id = ? AND student_id = ?",
                                       (fam["id"], sid)).fetchone())
    return render(request, "parent.html", conn, None, token=token, cert_base="/parent/" + token, fam=fam,
                  linked=linked, **_parent_ctx(conn, st))


def _parent_ctx(conn, st):
    """Всё для страницы успехов ребёнка: и по секретной ссылке, и в кабинете родителя."""
    sid = st["id"]
    lessons = [l for l in game.lesson_list_with_state(conn, sid) if l["open"]]
    states = {r["num"]: r for r in conn.execute("SELECT * FROM lesson_state WHERE student_id = ?", (sid,))}
    results = conn.execute("SELECT check_id, right_count, total, skipped, finished_at FROM check_results "
                           "WHERE student_id = ? ORDER BY finished_at", (sid,)).fetchall()
    subj = subjects.of(st)
    since = (config.today() - timedelta(days=13)).isoformat()
    days = {r[0] for r in conn.execute("SELECT DISTINCT substr(created_at, 1, 10) FROM xp_events WHERE student_id = ? "
                                       "AND created_at >= ?", (sid, since))}
    activity = [{"day": d, "on": d.isoformat() in days} for d in
                (config.today() - timedelta(days=i) for i in range(13, -1, -1))]
    plans = conn.execute("SELECT COUNT(*) FROM xp_events WHERE student_id = ? AND kind = 'drop' AND ref LIKE 'today:%' "
                         "AND created_at >= ?", (sid, since)).fetchone()[0]
    return dict(st=st, me=game.stats(conn, sid), lessons=lessons, states=states,
                fc=forecast.forecast(oge_progress(conn, sid)) if "python" in subj else None,
                ru_ov=russian.overview(conn, sid) if "russian" in subj else None, activity=activity, plans=plans,
                results=[(CHECK_BY_ID[r["check_id"]], r) for r in results if r["check_id"] in CHECK_BY_ID],
                certs=certificates.earned(conn, sid),
                recent=conn.execute("SELECT * FROM xp_events WHERE student_id = ? ORDER BY id DESC LIMIT 10",
                                    (sid,)).fetchall())


@router.get("/parent/{token}/certificate/{kind}/{ref}", response_class=HTMLResponse)
def parent_certificate(token: str, kind: str, ref: str, request: Request, conn=Depends(get_db)):
    st = _parent_student(conn, token)
    cert = certificates.find(conn, st["id"], kind, ref)
    if not cert:
        raise HTTPException(404)
    return render(request, "certificate.html", conn, None, cert=cert, holder=certificates.holder_name(conn, st["id"]),
                  teacher_name=cert_signer(conn), year=(cert["date"] or game.now_iso())[:4],
                  back_url="/parent/%s" % token)


# ------------------------------------------------------------------ кабинет родителя со своим входом (app/family.py)
def _client_ip(request):
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "?")


def _family_only(request, conn):
    fam = family.load(request, conn)
    if not fam:
        raise FamilyLogin()
    return fam


@router.get("/parent/{token}/account", response_class=HTMLResponse)
def family_join_page(token: str, request: Request, conn=Depends(get_db)):
    st = family.by_token(conn, token)
    return render(request, "family/join.html", conn, None, st=st, token=token, fam=family.load(request, conn),
                  suggested=students.generate_password(), form={})


@router.post("/parent/{token}/account", response_class=HTMLResponse)
def family_join(token: str, request: Request, name: str = Form(""), login: str = Form(""), password: str = Form(""),
                consent: str = Form(""), conn=Depends(get_db)):
    st = family.by_token(conn, token)
    ip = _client_ip(request)
    err = None
    if auth.too_many_fails(ip):
        err = "Слишком много попыток. Подождите 15 минут."
    else:
        with conn:
            pid, err = family.signup(conn, name, login, password, consent == "1")
            if pid:
                family.link(conn, pid, st["id"])
                game.tell_teacher(conn, st["id"], "👪 Родитель завёл кабинет: %s" % name.strip()[:60],
                                  "/teacher/student/%d#parent" % st["id"])
        if err:
            auth.register_fail(ip)
    if err:
        return render(request, "family/join.html", conn, None, st=st, token=token, fam=None, error=err,
                      suggested=students.generate_password(), form={"name": name, "login": login})
    resp = back("/family")
    family.set_cookie(resp, family.create_session(conn, pid))
    return resp


@router.post("/parent/{token}/link")
def family_link(token: str, request: Request, csrf: str = Form(""), conn=Depends(get_db)):
    st = family.by_token(conn, token)
    fam = _family_only(request, conn)
    family.check_csrf(fam, csrf)
    with conn:
        err = family.link(conn, fam["id"], st["id"])
    if err:
        raise HTTPException(400, err)
    return back("/family")


@router.get("/family/login", response_class=HTMLResponse)
def family_login_page(request: Request, conn=Depends(get_db)):
    if family.load(request, conn):
        return back("/family")
    return render(request, "family/login.html", conn, None)


@router.post("/family/login", response_class=HTMLResponse)
def family_login(request: Request, username: str = Form(""), password: str = Form(""), conn=Depends(get_db)):
    ip = _client_ip(request)
    if auth.too_many_fails(ip):
        return render(request, "family/login.html", conn, None, error="Слишком много попыток. Подождите 15 минут.")
    pid = family.check_login(conn, username, password)
    if not pid:
        auth.register_fail(ip)
        return render(request, "family/login.html", conn, None, error="Неверный логин или пароль")
    resp = back("/family")
    family.set_cookie(resp, family.create_session(conn, pid))
    return resp


@router.post("/family/logout")
def family_logout(request: Request, csrf: str = Form(""), conn=Depends(get_db)):
    fam = _family_only(request, conn)
    family.check_csrf(fam, csrf)
    resp = back("/family/login")
    family.drop_session(conn, request, resp)
    return resp


@router.get("/family", response_class=HTMLResponse)
def family_home(request: Request, conn=Depends(get_db)):
    fam = _family_only(request, conn)
    week = (config.today() - timedelta(days=6)).isoformat()
    kids = []
    for st in family.children(conn, fam["id"]):
        sid = st["id"]
        days = conn.execute("SELECT COUNT(DISTINCT substr(created_at, 1, 10)) FROM xp_events WHERE student_id = ? "
                            "AND created_at >= ?", (sid, week)).fetchone()[0]
        kids.append({"st": st, "me": game.stats(conn, sid), "days": days,
                     "fc": forecast.forecast(oge_progress(conn, sid)) if "python" in subjects.of(st) else None})
    return render(request, "family/home.html", conn, None, fam=fam, kids=kids)


@router.get("/family/child/{sid}", response_class=HTMLResponse)
def family_child(sid: int, request: Request, conn=Depends(get_db)):
    fam = _family_only(request, conn)
    st = family.child(conn, fam["id"], sid)
    return render(request, "parent.html", conn, None, fam=fam, in_family=True, cert_base="/family/child/%d" % sid,
                  **_parent_ctx(conn, st))


@router.get("/family/child/{sid}/certificate/{kind}/{ref}", response_class=HTMLResponse)
def family_certificate(sid: int, kind: str, ref: str, request: Request, conn=Depends(get_db)):
    fam = _family_only(request, conn)
    st = family.child(conn, fam["id"], sid)
    cert = certificates.find(conn, st["id"], kind, ref)
    if not cert:
        raise HTTPException(404)
    return render(request, "certificate.html", conn, None, cert=cert, holder=certificates.holder_name(conn, st["id"]),
                  teacher_name=cert_signer(conn), year=(cert["date"] or game.now_iso())[:4],
                  back_url="/family/child/%d" % sid)


@router.post("/family/child/{sid}/unlink")
def family_unlink(sid: int, request: Request, csrf: str = Form(""), conn=Depends(get_db)):
    fam = _family_only(request, conn)
    family.check_csrf(fam, csrf)
    with conn:
        family.unlink(conn, fam["id"], sid)
    return back("/family")


@router.get("/privacy", response_class=HTMLResponse)
def privacy(request: Request, conn=Depends(get_db)):
    return render(request, "privacy.html", conn, None, operator=config.OPERATOR, contact=config.CONTACT,
                  version=family.CONSENT_VERSION, student_name="")
