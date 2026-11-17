"""Яндекс ID: кнопка только при секретах, callback привязывает подтверждённую почту, новый аккаунт — с 14 лет."""
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CQ_DATA_DIR", str(tmp_path))
    from app import config
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path / "up")
    monkeypatch.setattr(config, "COOKIE_SECURE", False)
    monkeypatch.setattr(config, "YANDEX_CLIENT_ID", "")
    monkeypatch.setattr(config, "YANDEX_CLIENT_SECRET", "")
    from fastapi.testclient import TestClient
    from app import auth, students
    from app.db import init_db
    from app.main import app
    auth._failed.clear()
    students._signups.clear()
    init_db()
    with TestClient(app) as c:
        yield c
    students._signups.clear()


def _enable(monkeypatch):
    from app import config
    monkeypatch.setattr(config, "YANDEX_CLIENT_ID", "dummy-id")
    monkeypatch.setattr(config, "YANDEX_CLIENT_SECRET", "dummy-secret")


def _install(monkeypatch, info, calls):
    from app import oauth_providers as op

    def exchange(code, client_id, client_secret):
        calls.append(("token", code, client_id, client_secret))
        if code == "bad-code":
            raise op.ProviderError("no")
        return "access-token"

    def userinfo(token):
        calls.append(("info", token))
        return dict(info)

    monkeypatch.setattr(op, "exchange_code", exchange)
    monkeypatch.setattr(op, "fetch_userinfo", userinfo)


def _profile(**kwargs):
    info = {
        "id": "1000034426",
        "login": "ivan",
        "default_email": "ivan@yandex.ru",
        "emails": ["ivan@yandex.ru", "other@example.com"],
        "real_name": "Иван Иванов",
        "display_name": "ivan",
    }
    info.update(kwargs)
    return info


def _begin(client):
    r = client.get("/auth/yandex", follow_redirects=False)
    assert r.status_code == 302, r.text
    loc = r.headers["location"]
    q = parse_qs(urlparse(loc).query)
    assert q["response_type"] == ["code"]
    assert q["client_id"] == ["dummy-id"]
    assert set(q["scope"][0].split()) == {"login:info", "login:email"}
    assert q["redirect_uri"][0].endswith("/auth/yandex/callback")
    assert "client_secret" not in loc and "dummy-secret" not in loc
    assert q["state"][0]
    return q["state"][0]


def _callback(client, state, code="ok", error=""):
    params = {"state": state}
    if error:
        params["error"] = error
    else:
        params["code"] = code
    return client.get("/auth/yandex/callback", params=params, follow_redirects=False)


def _users():
    from app.db import connect
    conn = connect()
    return [dict(r) for r in conn.execute("SELECT * FROM users ORDER BY id")]


def _identities():
    from app.db import connect
    conn = connect()
    return [dict(r) for r in conn.execute("SELECT provider, subject, user_id, email FROM oauth_identities")]


def test_login_button_hidden_when_env_unset(client, monkeypatch):
    page = client.get("/login").text
    assert "Войти с Яндекс ID" not in page
    assert client.get("/auth/yandex", follow_redirects=False).status_code == 404
    assert client.get("/auth/yandex/callback", follow_redirects=False).status_code == 404
    # одной переменной мало — кнопка по-прежнему скрыта
    from app import config
    monkeypatch.setattr(config, "YANDEX_CLIENT_ID", "dummy-id")
    assert "Войти с Яндекс ID" not in client.get("/login").text
    assert client.get("/auth/yandex", follow_redirects=False).status_code == 404


def test_login_button_visible_when_configured(client, monkeypatch):
    _enable(monkeypatch)
    page = client.get("/login").text
    assert "Войти с Яндекс ID" in page
    assert 'href="/auth/yandex"' in page
    assert "dummy-secret" not in page and "dummy-id" not in page
    from app import config
    monkeypatch.setattr(config, "OPEN_SIGNUP", True)
    monkeypatch.setattr(config, "SIGNUP", True)
    assert "Войти с Яндекс ID" in client.get("/join").text


def test_tables_created_by_init_db(client):
    from app.db import connect
    names = {r[0] for r in connect().execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"oauth_identities", "oauth_states", "oauth_pending"} <= names


def test_callback_creates_new_user_only_after_age_gate(client, monkeypatch):
    _enable(monkeypatch)
    calls = []
    _install(monkeypatch, _profile(), calls)
    state = _begin(client)
    started = _callback(client, state)
    assert started.status_code == 303
    assert started.headers["location"] == "/auth/yandex/complete"
    assert calls == [("token", "ok", "dummy-id", "dummy-secret"), ("info", "access-token")]
    assert _users() == []                          # callback сам аккаунт не создаёт
    form = client.get("/auth/yandex/complete")
    assert form.status_code == 200
    assert "ivan@yandex.ru" in form.text and "с 14 лет" in form.text and 'name="birth_date"' in form.text

    child = client.post("/auth/yandex/complete",
                        data={"birth_date": "2013-01-15", "consent": "1"}, follow_redirects=False)
    assert child.status_code == 200 and "с 14 лет" in child.text and "родител" in child.text
    assert _users() == [] and _identities() == []

    no_consent = client.post("/auth/yandex/complete",
                             data={"birth_date": "2005-05-15", "consent": ""}, follow_redirects=False)
    assert no_consent.status_code == 200 and "согласие" in no_consent.text
    assert _users() == []

    done = client.post("/auth/yandex/complete",
                       data={"birth_date": "2005-05-15", "consent": "1"}, follow_redirects=False)
    assert done.status_code == 303 and done.headers["location"] == "/"
    rows = _users()
    assert len(rows) == 1
    assert rows[0]["email"] == "ivan@yandex.ru" and rows[0]["username"] == "ivan@yandex.ru"
    assert rows[0]["role"] == "student" and rows[0]["guest"] == 0 and rows[0]["minor"] == 0
    assert rows[0]["display_name"] == "Иван Иванов"
    assert rows[0]["consent"]
    assert _identities() == [{"provider": "yandex", "subject": "1000034426", "user_id": rows[0]["id"],
                              "email": "ivan@yandex.ru"}]
    home = client.get("/")
    assert home.status_code == 200 and "Иван" in home.text


def test_callback_links_existing_user_by_verified_email(client, monkeypatch):
    from app import auth
    from app.db import connect
    _enable(monkeypatch)
    conn = connect()
    with conn:
        conn.execute(
            "INSERT INTO users (username, password_hash, role, display_name, email) VALUES (?, ?, 'student', ?, ?)",
            ("anya", auth.hash_password("secret123"), "Аня", "Anna@Example.com"))
    before = connect().execute("SELECT id FROM users WHERE username = 'anya'").fetchone()[0]
    calls = []
    _install(monkeypatch, _profile(id="555", default_email="anna@example.com",
                                   emails=["anna@example.com", "other@example.com"], real_name="Аня Я"), calls)
    state = _begin(client)
    r = _callback(client, state)
    assert r.status_code == 303 and r.headers["location"] == "/"
    assert len(_users()) == 1
    row = _users()[0]
    assert row["id"] == before and row["username"] == "anya"
    assert _identities() == [{"provider": "yandex", "subject": "555", "user_id": before, "email": "anna@example.com"}]
    home = client.get("/")
    assert home.status_code == 200 and "Аня" in home.text
    # пароль прежний: почтовый вход не сломан
    client.cookies.clear()
    again = client.post("/login", data={"username": "anya", "password": "secret123"}, follow_redirects=False)
    assert again.status_code == 303
    # повторный Яндекс — тот же аккаунт, без второй привязки
    client.cookies.clear()
    state = _begin(client)
    r = _callback(client, state)
    assert r.status_code == 303 and r.headers["location"] == "/"
    assert len(_users()) == 1 and len(_identities()) == 1


def test_unverified_email_does_not_link_or_register(client, monkeypatch):
    """emails[] без default_email — не подтверждённая почта: ни привязки, ни нового аккаунта."""
    from app import auth
    from app.db import connect
    _enable(monkeypatch)
    conn = connect()
    with conn:
        conn.execute(
            "INSERT INTO users (username, password_hash, role, display_name, email) VALUES (?, ?, 'student', ?, ?)",
            ("anya", auth.hash_password("secret123"), "Аня", "anna@example.com"))
    calls = []
    _install(monkeypatch, _profile(default_email=None, emails=["anna@example.com"]), calls)
    state = _begin(client)
    r = _callback(client, state)
    assert r.status_code == 200 and "не подтвердил почту" in r.text
    assert len(_users()) == 1 and _identities() == []
    # default_email чужой, а существующая почта только в emails — это новый человек, не Аня
    _install(monkeypatch, _profile(id="777", default_email="new@yandex.ru", emails=["anna@example.com", "new@yandex.ru"]),
             calls)
    state = _begin(client)
    r = _callback(client, state)
    assert r.status_code == 303 and r.headers["location"] == "/auth/yandex/complete"
    assert len(_users()) == 1 and _identities() == []
    assert "new@yandex.ru" in client.get("/auth/yandex/complete").text


def test_callback_links_username_when_email_column_empty(client, monkeypatch):
    from app import auth
    from app.db import connect
    _enable(monkeypatch)
    conn = connect()
    with conn:
        conn.execute(
            "INSERT INTO users (username, password_hash, role, display_name) VALUES (?, ?, 'student', ?)",
            ("old@example.com", auth.hash_password("secret123"), "Старый"))
    _install(monkeypatch, _profile(id="9", default_email="old@example.com", real_name="Старый"), [])
    r = _callback(client, _begin(client))
    assert r.status_code == 303 and r.headers["location"] == "/"
    row = _users()[0]
    assert row["username"] == "old@example.com" and row["email"] == "old@example.com"
    assert len(_users()) == 1


def test_callback_state_mismatch(client, monkeypatch):
    _enable(monkeypatch)
    calls = []
    _install(monkeypatch, _profile(), calls)
    state = _begin(client)
    wrong = _callback(client, "a" * len(state))
    assert wrong.status_code == 200 and "устарела" in wrong.text
    assert calls == []
    # чужой state не сжигает настоящий: тот же cookie всё ещё входит
    ok = _callback(client, state)
    assert ok.status_code == 303 and ok.headers["location"] == "/auth/yandex/complete"
    assert len(calls) == 2
    # повтор того же state — уже использован
    client.cookies.set("cq_oauth", state, path="/auth")
    replay = _callback(client, state)
    assert replay.status_code == 200 and "устарела" in replay.text
    # без cookie сессии код из адресной строки ничего не даёт
    client.cookies.clear()
    state = _begin(client)
    client.cookies.clear()
    naked = _callback(client, state)
    assert naked.status_code == 200 and "устарела" in naked.text
    assert _users() == []


def test_callback_provider_error(client, monkeypatch):
    _enable(monkeypatch)
    calls = []
    _install(monkeypatch, _profile(), calls)
    denied = _callback(client, _begin(client), error="access_denied")
    assert denied.status_code == 200 and "отменили" in denied.text
    assert calls == []
    failed = _callback(client, _begin(client), code="bad-code")
    assert failed.status_code == 200 and "Не удалось войти" in failed.text
    assert calls and calls[-1][0] == "token"
    assert _users() == [] and _identities() == []


def test_archived_yandex_user_sees_the_same_message(client, monkeypatch):
    from app import auth
    from app.db import connect
    _enable(monkeypatch)
    conn = connect()
    with conn:
        conn.execute(
            "INSERT INTO users (username, password_hash, role, display_name, email, active) "
            "VALUES (?, ?, 'student', ?, ?, 0)",
            ("anya", auth.hash_password("secret123"), "Аня", "anna@example.com"))
    _install(monkeypatch, _profile(default_email="anna@example.com"), [])
    r = _callback(client, _begin(client))
    assert r.status_code == 200 and "архиве" in r.text
    assert "cq_session" not in r.cookies
