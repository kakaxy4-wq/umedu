"""Удаление аккаунта: из кабинета ученика и с публичной страницы (без приложения).

Ребёнка младше 14 лет эти страницы не удаляют — это делает родитель в своём кабинете.
"""
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from . import account, auth, config, family
from .db import get_db
from .main import back, only_student, render

router = APIRouter()

_GALLERY_NEXT = {"/account", "/u2/me", "/portfolio", "/chem/me"}


def _ip(request):
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "?")


def _clear_cookies(response):
    for key in (auth.COOKIE, family.COOKIE):
        response.delete_cookie(key, path="/", secure=config.COOKIE_SECURE, httponly=True, samesite="lax")


def _student(conn, user):
    only_student(user)
    row = conn.execute("SELECT * FROM users WHERE id = ? AND role = 'student'", (user["id"],)).fetchone()
    return dict(row)


# ------------------------------------------------------------------ кабинет ученика
@router.get("/account", response_class=HTMLResponse)
def account_page(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    st = _student(conn, user)
    return render(request, "account/home.html", conn, user, gallery_on=account.granted(st))


@router.post("/account/gallery")
def account_gallery(request: Request, gallery: str = Form(""), next: str = Form(""),
                    conn=Depends(get_db), user=Depends(auth.check_csrf)):
    st = _student(conn, user)
    if st["minor"]:
        raise HTTPException(403, "Ник в галерее включает родитель.")
    account.set_gallery(conn, st["id"], gallery == "1", account.BY_STUDENT)
    return back(next if next in _GALLERY_NEXT else "/account")


def _student_delete_page(request, conn, user, st, error=None):
    blocked = None
    if st["minor"]:
        blocked = ("Тебе меньше 14 лет. Аккаунт удаляет родитель — из своего кабинета или на странице "
                   "удаления, войдя как родитель.")
    return render(request, "account/delete_form.html", conn, user, fam=None, heading="Удалить аккаунт",
                  lead="Удалим аккаунт, ответы, прогресс, проекты и согласие. Восстановить нельзя.",
                  action="/account/delete", error=error, minors=[], warn_minors=False, need_login=False,
                  confirm_text="Я понимаю, что аккаунт и учебные данные будут удалены без восстановления",
                  password_label="Пароль", blocked=blocked, done=False)


@router.get("/account/delete", response_class=HTMLResponse)
def account_delete_page(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    return _student_delete_page(request, conn, user, _student(conn, user))


@router.post("/account/delete", response_class=HTMLResponse)
def account_delete(request: Request, password: str = Form(""), confirm: str = Form(""),
                   conn=Depends(get_db), user=Depends(auth.check_csrf)):
    st = _student(conn, user)
    if st["minor"]:
        return _student_delete_page(request, conn, user, st)
    if confirm != "1":
        return _student_delete_page(request, conn, user, st, error="Подтверди удаление — поставь галочку.")
    if not account.password_ok(st["password_hash"], password):
        return _student_delete_page(request, conn, user, st, error="Неверный пароль.")
    account.delete_student(conn, st["id"])
    resp = render(request, "account/deleted.html", conn, None, parent=False, child_name="")
    _clear_cookies(resp)
    return resp


# ------------------------------------------------------------------ публичная страница (Google Play и запрос без приложения)
def _public_page(request, conn, error=None, who="student"):
    return render(request, "account/delete_form.html", conn, None, fam=None,
                  heading="Удаление аккаунта",
                  lead=("Так можно удалить аккаунт на сайте «%s» без приложения: нужны логин и пароль. "
                        "Ребёнка младше 14 лет удаляет родитель.") % config.SITE_NAME,
                  action="/delete-account", error=error, minors=[], warn_minors=True, need_login=True, who=who,
                  confirm_text="Я понимаю, что аккаунт и учебные данные будут удалены без восстановления",
                  password_label="Пароль", blocked=None, done=False,
                  operator=config.OPERATOR, contact=config.CONTACT)


@router.get("/delete-account", response_class=HTMLResponse)
def public_delete_page(request: Request, conn=Depends(get_db)):
    return _public_page(request, conn)


@router.post("/delete-account", response_class=HTMLResponse)
def public_delete(request: Request, who: str = Form("student"), username: str = Form(""), password: str = Form(""),
                  confirm: str = Form(""), website: str = Form(""), conn=Depends(get_db)):
    ip = _ip(request)
    if website:
        return _public_page(request, conn, "Не получилось. Обновите страницу и попробуйте ещё раз.", who)
    if auth.too_many_fails(ip):
        return _public_page(request, conn, "Слишком много попыток. Подождите 15 минут.", who)
    if confirm != "1":
        return _public_page(request, conn, "Подтвердите удаление — поставьте галочку.", who)
    login = username.strip()
    if not login or not password:
        return _public_page(request, conn, "Введите логин и пароль.", who)
    if who == "parent":
        row = account.parent_login(conn, login)
        if not account.password_ok(row["password_hash"] if row else "", password):
            auth.register_fail(ip)
            return _public_page(request, conn, "Неверный логин или пароль.", who)
        account.delete_parent(conn, row["id"])
        resp = render(request, "account/deleted.html", conn, None, parent=True, child_name="", public=True)
        _clear_cookies(resp)
        return resp
    row = account.student_login(conn, login)
    if not account.password_ok(row["password_hash"] if row else "", password):
        auth.register_fail(ip)
        return _public_page(request, conn, "Неверный логин или пароль.", who)
    if row["minor"]:
        return _public_page(request, conn,
                            "Это аккаунт ребёнка младше 14 лет. Его удаляет родитель: выберите «Родитель» "
                            "и введите логин и пароль кабинета родителя.", who)
    account.delete_student(conn, row["id"])
    resp = render(request, "account/deleted.html", conn, None, parent=False, child_name="", public=True)
    _clear_cookies(resp)
    return resp
