"""Портфолио проектов ученика и публичная галерея.

Маршруты вынесены из main.py; общие функции берутся оттуда. Подключается в конце main.py.
"""
import secrets

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from . import account, auth, config, game
from .db import get_db
from .main import FILE_EXT, IMAGE_EXT, back, is_teacher, need_sid, render, save_upload, upload_path

router = APIRouter()


# ------------------------------------------------------------------ портфолио
def _slug():
    return secrets.token_urlsafe(6).replace("-", "x").replace("_", "y").lower()


def _own_project(conn, sid, pid):
    row = conn.execute("SELECT * FROM projects WHERE id = ? AND student_id = ?", (pid, sid)).fetchone()
    if not row:
        raise HTTPException(404)
    return row


@router.get("/portfolio", response_class=HTMLResponse)
def portfolio(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    sid = need_sid(conn, user)
    projects = conn.execute("SELECT * FROM projects WHERE student_id = ? ORDER BY updated_at DESC", (sid,)).fetchall()
    return render(request, "student/portfolio.html", conn, user, projects=projects, base_url=config.BASE_URL)


@router.get("/portfolio/new", response_class=HTMLResponse)
def project_new(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    need_sid(conn, user)
    return render(request, "student/project_edit.html", conn, user, project=None)


@router.get("/portfolio/{pid}/edit", response_class=HTMLResponse)
def project_edit(pid: int, request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    return render(request, "student/project_edit.html", conn, user, project=_own_project(conn, need_sid(conn, user), pid))


@router.post("/portfolio/save")
async def project_save(request: Request, pid: int = Form(0), title: str = Form(...), description: str = Form(""),
                       code: str = Form(""), public: str = Form(""), image: UploadFile = File(None),
                       upload: UploadFile = File(None), conn=Depends(get_db), user=Depends(auth.check_csrf)):
    sid = need_sid(conn, user)
    if pid:
        _own_project(conn, sid, pid)
    img_name, img_path = await save_upload(image, IMAGE_EXT)
    file_name, file_path = await save_upload(upload, FILE_EXT)
    now = game.now_iso()
    with conn:
        if pid:
            conn.execute("UPDATE projects SET title = ?, description = ?, code = ?, public = ?, updated_at = ?, "
                         "image_path = COALESCE(?, image_path), file_name = COALESCE(?, file_name), "
                         "file_path = COALESCE(?, file_path) WHERE id = ? AND student_id = ?",
                         (title[:120], description[:10_000], code[:200_000], 1 if public else 0, now,
                          img_path, file_name, file_path, pid, sid))
        else:
            conn.execute("INSERT INTO projects (student_id, slug, title, description, code, image_path, file_name, "
                         "file_path, public, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         (sid, _slug(), title[:120], description[:10_000], code[:200_000], img_path, file_name,
                          file_path, 1 if public else 0, now, now))
            if user["role"] == "student":
                game.tell_teacher(conn, sid, "🗂️ Новый проект в портфолио: %s" % title)
        if user["role"] == "student":
            game.sync_achievements(conn, sid)
    return back("/portfolio")


@router.post("/portfolio/{pid}/delete")
def project_delete(pid: int, conn=Depends(get_db), user=Depends(auth.check_csrf)):
    sid = need_sid(conn, user)
    with conn:
        conn.execute("DELETE FROM projects WHERE id = ? AND student_id = ?", (pid, sid))
    return back("/portfolio")


@router.get("/files/project/{pid}/{kind}")
def project_file(pid: int, kind: str, request: Request, conn=Depends(get_db)):
    row = conn.execute("SELECT * FROM projects WHERE id = ?", (pid,)).fetchone()
    if not row:
        raise HTTPException(404)
    if not row["public"]:
        user = auth.load_user(request, conn)
        if not user or (not is_teacher(user) and user["id"] != row["student_id"]):
            raise HTTPException(404)
    if kind == "image" and row["image_path"]:
        return FileResponse(upload_path(row["image_path"]))
    if kind == "file" and row["file_path"]:
        return FileResponse(upload_path(row["file_path"]), filename=row["file_name"])
    raise HTTPException(404)


@router.get("/p/{slug}", response_class=HTMLResponse)
def public_project(slug: str, request: Request, conn=Depends(get_db)):
    row = account.public_project(conn, slug)
    if not row:
        raise HTTPException(404)
    return render(request, "public_project.html", conn, None, project=row, student_name=row["author"])


@router.get("/gallery", response_class=HTMLResponse)
def gallery(request: Request, conn=Depends(get_db)):
    projects = account.public_projects(conn)
    return render(request, "gallery.html", conn, None, projects=projects, student_name="")
