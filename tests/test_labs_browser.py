"""Полный цикл «закона Ома» в браузере: вопрос, предсказание, опыт, сравнение, закон, перенос.

Нужны пакет playwright и chromium. Без них тест пропускается, остальные проверки живут в test_labs.py.
"""
import shutil
import socket
import threading
import time
from pathlib import Path

import pytest

from app import config

SHOTS = Path("/opt/cursor/artifacts/screenshots")
VIDEO = Path("/opt/cursor/artifacts/lab-ohm-cycle.webm")


@pytest.fixture()
def lab_server(tmp_path, monkeypatch):
    monkeypatch.setenv("CQ_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path / "up")
    monkeypatch.setattr(config, "COOKIE_SECURE", False)
    monkeypatch.setattr(config, "UMEDU2", True)
    from app import auth, knowledge as kn
    from app.db import connect, init_db
    import manage
    auth._failed.clear()
    init_db()
    conn = connect()
    manage.create_user(conn, "teacher", "teacher", "Папа", "secret123")
    manage.create_user(conn, "student", "student", "Миша", "secret123")
    sid = conn.execute("SELECT id FROM users WHERE username = 'student'").fetchone()[0]
    with conn:
        kn.enroll(conn, sid, "oge-phys-2026", 4, None)
    conn.close()
    import uvicorn
    from app.main import app
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 8
    while not server.started:
        if time.time() > deadline:
            raise RuntimeError("сервер лаборатории не поднялся")
        time.sleep(0.05)
    yield port
    server.should_exit = True
    thread.join(timeout=5)


def _set_range(page, name, value):
    page.locator('[data-ctl="%s"]' % name).evaluate(
        "(el, v) => { el.value = String(v); el.dispatchEvent(new Event('input', { bubbles: true })); }", value)


def test_ohm_cycle_keyboard_themes_and_widths(lab_server):  # noqa: F811
    playwright = pytest.importorskip("playwright.sync_api")
    import httpx
    url = "http://127.0.0.1:%d" % lab_server
    login = httpx.post(url + "/login", data={"username": "student", "password": "secret123"}, follow_redirects=False)
    assert login.status_code == 303, login.text
    token = login.cookies.get("cq_session")
    assert token
    SHOTS.mkdir(parents=True, exist_ok=True)
    with playwright.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:  # браузер не скачан — в CI без chromium тест не валит весь прогон
            pytest.skip("chromium недоступен: %s" % exc)
        context = browser.new_context(
            viewport={"width": 375, "height": 812}, record_video_dir="/tmp/lab-video",
            record_video_size={"width": 390, "height": 844})
        context.add_cookies([{"name": "cq_session", "value": token, "url": url}])
        page = context.new_page()
        page.goto(url + "/u2/lab/ohm", wait_until="networkidle")
        assert "закон Ома" in page.content()
        page.get_by_role("button", name="Дальше").click()
        page.get_by_role("radio", name="Вырастет вдвое").check()
        page.get_by_role("button", name="Это моё предсказание").click()
        page.locator("#lab-scene").wait_for()
        page.wait_for_function("() => document.querySelector('[data-meter=\"I\"]').textContent.includes('А')")
        slider = page.locator('[data-ctl="U"]')
        slider.focus()
        before = float(slider.input_value())
        page.keyboard.press("ArrowRight")
        assert float(slider.input_value()) > before
        live = page.locator("#lab-meters").inner_text()
        assert "А" in live and "В" in live
        for volts in (3, 6, 9, 12):
            _set_range(page, "U", volts)
            page.locator("#lab-record").click()
        page.wait_for_timeout(1000)
        frames = page.evaluate("() => window.__labFrames")
        assert frames >= 30, frames
        Path("/tmp/lab-fps.txt").write_text(str(frames), encoding="utf-8")
        page.set_viewport_size({"width": 375, "height": 812})
        page.evaluate("() => window.scrollTo(0, 0)")
        overflow = page.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
        assert overflow <= 1, overflow
        page.get_by_role("button", name="К сравнению").scroll_into_view_if_needed()
        covered = page.evaluate("""() => {
          const btn = [...document.querySelectorAll('button')].find(b => b.textContent.includes('сравнению'));
          const nav = document.querySelector('.u2-tabs').getBoundingClientRect();
          const box = btn.getBoundingClientRect();
          return box.bottom > nav.top + 1;
        }""")
        assert not covered
        page.set_viewport_size({"width": 375, "height": 1500})
        page.evaluate("() => window.scrollTo(0, 0)")
        page.screenshot(path=str(SHOTS / "lab-ohm-375.png"))
        page.evaluate("() => document.documentElement.setAttribute('data-theme', 'dark')")
        dark = page.evaluate("() => getComputedStyle(document.body).backgroundColor")
        page.evaluate("() => window.scrollTo(0, 0)")
        page.screenshot(path=str(SHOTS / "lab-ohm-375-dark.png"))
        page.set_viewport_size({"width": 1280, "height": 1400})
        page.evaluate("() => document.documentElement.setAttribute('data-theme', 'light')")
        light = page.evaluate("() => getComputedStyle(document.body).backgroundColor")
        assert dark != light
        overflow = page.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
        assert overflow <= 1, overflow
        page.evaluate("() => window.scrollTo(0, 0)")
        page.screenshot(path=str(SHOTS / "lab-ohm-1280.png"))
        page.get_by_role("button", name="К сравнению").click()
        page.locator("#lab-value").fill("0,6")
        page.get_by_role("button", name="Проверить").click()
        page.locator("#lab-check-out").wait_for()
        assert "Сходится" in page.locator("#lab-check-out").inner_text()
        page.get_by_role("button", name="К закону").click()
        assert "I = U / R" in page.content()
        page.get_by_role("button", name="К заданиям").click()
        page.locator('input[name="a0"]').fill("0,3")
        page.locator('input[name="a1"]').fill("20")
        page.get_by_role("button", name="Записать ответы").click()
        page.wait_for_load_state("networkidle")
        assert page.get_by_text("Верно").count() == 2
        assert "Неверно" not in page.content()
        page.close()
        context.close()
        browser.close()
        video = next(Path("/tmp/lab-video").glob("*.webm"))
        VIDEO.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(video, VIDEO)
