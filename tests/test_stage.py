"""CQ_STAGE и seed_demo: без флага сайт и база не меняются."""
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
from test_app import client, login  # noqa: E402,F401


def _db(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.DATA_DIR", tmp_path)
    monkeypatch.setattr("app.config.DB_PATH", tmp_path / "t.db")
    from app.db import connect, init_db
    init_db()
    return connect()


def test_stage_off_has_no_banner_or_noindex(client):
    from app import config
    assert config.STAGE is False
    r = client.get("/login")
    assert "Тестовый стенд" not in r.text
    assert "x-robots-tag" not in {k.lower() for k in r.headers}
    assert 'name="robots"' not in r.text


def test_stage_on_banner_and_noindex(client, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "STAGE", True)
    monkeypatch.setattr(config, "UMEDU2", True)
    r = client.get("/login")
    assert r.headers["x-robots-tag"] == "noindex, nofollow"
    assert "Тестовый стенд, данные могут быть стёрты" in r.text
    assert 'name="robots" content="noindex, nofollow"' in r.text
    login(client, "student")
    page = client.get("/u2/today", follow_redirects=True)
    assert page.status_code == 200
    assert "Тестовый стенд, данные могут быть стёрты" in page.text
    assert page.headers["x-robots-tag"] == "noindex, nofollow"
    # страницы без флага стенд не помечает: выключили — заголовка нет
    monkeypatch.setattr(config, "STAGE", False)
    again = client.get("/login")
    assert "Тестовый стенд" not in again.text
    assert "x-robots-tag" not in {k.lower() for k in again.headers}


def test_seed_refuses_without_stage(tmp_path, monkeypatch):
    from app import config
    from app.demo import DemoRefused, seed_demo
    monkeypatch.setattr(config, "STAGE", False)
    conn = _db(tmp_path, monkeypatch)
    before = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    with pytest.raises(DemoRefused):
        seed_demo(conn)
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == before
    assert conn.execute("SELECT COUNT(*) FROM class").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM skill_attempt").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM parents").fetchone()[0] == 0


def test_seed_demo_class_and_second_run(tmp_path, monkeypatch):
    from app import auth, config
    from app.demo import seed_demo
    monkeypatch.setattr(config, "STAGE", True)
    conn = _db(tmp_path, monkeypatch)
    report = seed_demo(conn)
    assert report["created"] is True
    assert report["members"] == 3
    assert report["attempts"] == 42
    span = (date.fromisoformat(report["last_day"]) - date.fromisoformat(report["first_day"])).days
    assert span == 13
    assert conn.execute("SELECT COUNT(*) FROM parents WHERE username = 'demo-parent'").fetchone()[0] == 1
    linked = conn.execute(
        "SELECT u.username FROM parent_children c JOIN users u ON u.id = c.student_id"
    ).fetchone()[0]
    assert linked == "demo"
    assert conn.execute("SELECT name FROM class").fetchone()[0] == "9 класс"
    teacher = conn.execute("SELECT password_hash FROM users WHERE username = 'teacher'").fetchone()
    assert auth.verify_password("demo-teacher", teacher["password_hash"])
    parent = conn.execute("SELECT password_hash FROM parents WHERE username = 'demo-parent'").fetchone()
    assert auth.verify_password("demo-parent", parent["password_hash"])
    # повторно — ни новых попыток, ни новых учеников
    again = seed_demo(conn)
    assert again["created"] is False
    assert conn.execute("SELECT COUNT(*) FROM skill_attempt").fetchone()[0] == 42
    assert conn.execute("SELECT COUNT(*) FROM users WHERE role = 'student'").fetchone()[0] == 3
    monkeypatch.setattr(config, "STAGE", False)
    from app.demo import DemoRefused
    with pytest.raises(DemoRefused):
        seed_demo(conn)
    assert conn.execute("SELECT COUNT(*) FROM skill_attempt").fetchone()[0] == 42


def test_seed_cli_does_not_create_db_without_stage(tmp_path):
    env = os.environ.copy()
    env["CQ_ENV_FILE"] = str(tmp_path / "no.env")
    env["CQ_DATA_DIR"] = str(tmp_path / "data")
    env["CQ_DB_PATH"] = str(tmp_path / "data" / "t.db")
    env.pop("CQ_STAGE", None)
    proc = subprocess.run([sys.executable, "manage.py", "seed_demo"], cwd=ROOT, env=env,
                          capture_output=True, text=True)
    assert proc.returncode != 0
    assert "CQ_STAGE" in proc.stderr
    assert not (tmp_path / "data").exists()


def test_seed_cli_on_stage(tmp_path):
    env = os.environ.copy()
    env["CQ_ENV_FILE"] = str(tmp_path / "no.env")
    env["CQ_DATA_DIR"] = str(tmp_path / "data")
    env["CQ_DB_PATH"] = str(tmp_path / "data" / "t.db")
    env["CQ_STAGE"] = "1"
    proc = subprocess.run([sys.executable, "manage.py", "seed_demo"], cwd=ROOT, env=env,
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert "demo-anya" in proc.stdout and "demo-parent" in proc.stdout
    again = subprocess.run([sys.executable, "manage.py", "seed_demo"], cwd=ROOT, env=env,
                           capture_output=True, text=True)
    assert again.returncode == 0
    assert "не изменена" in again.stdout
