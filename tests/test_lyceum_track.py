"""Лицейская дорожка: переводные экзамены «в 8/9 класс» по формату спецификаций 1535 (issue #46)."""
import re

from test_app import client  # noqa: F401  (фикстура TestClient с временной базой)


def test_lyceum_exams_in_catalog_and_ready(client, monkeypatch):
    from app import config, exam_model as em
    from app.content import onsite_extra
    from app.u2_web import _catalog
    monkeypatch.setattr(config, "UMEDU2", True)
    cat = {e["id"]: e for e in _catalog()}
    for exam_id in ("perevod-8-2027", "perevod-9-2027"):
        assert exam_id in cat, exam_id
        assert cat[exam_id]["ready"], "номера решаются на сайте"
        keys = onsite_extra.keys_for(exam_id)
        assert keys == set(range(1, 16)), (exam_id, keys)
        exam = em.load(exam_id)
        assert exam["max_points"] == sum(t["points"] for p in exam["parts"] for t in p["tasks"])


def test_lyceum_generators_200_seeds_and_recompute():
    from app.content.extra_math import recompute
    from app.u2_web import _variant

    for exam_id in ("perevod-8-2027", "perevod-9-2027"):
        for key in range(1, 16):
            for seed in (11, 2222, 333333):
                v = _variant(exam_id, key, seed)
                assert v["text"] and v["answer"] and v["explain"], (exam_id, key, seed)
                recomputed = recompute(v["data"])
                assert str(recomputed) == v["answer"], (exam_id, key, seed, v)


def test_lyceum_diag_and_start_pages(client, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "UMEDU2", True)
    monkeypatch.setattr(config, "OPEN_SIGNUP", True)
    r = client.post("/join", data={"name": "Тест Девятиклассник", "grade": "9", "login": "qa-perevod",
                                   "password": "parol-6", "age14": "1", "consent": "1", "website": ""},
                    follow_redirects=False)
    assert r.status_code == 303, r.text[:200]
    start = client.get("/u2/start?step=Переводной").text
    assert "perevod-8-2027" in start and "Переводной" in start
    csrf = re.search(r'name="csrf" content="([^"]+)"', start).group(1)
    r = client.post("/u2/start", data={"exam_id": "perevod-8-2027", "goal": 4, "exam_date": "2027-06-03",
                                       "csrf": csrf}, follow_redirects=False)
    assert r.status_code == 303, r.text[:200]
    diag = client.get("/u2/diag/perevod-8-2027")
    assert diag.status_code == 200 and "Математика" in diag.text
    today = client.get("/u2/today").text
    assert "perevod-8-2027" in today, "задание нового экзамена попадает в план"
