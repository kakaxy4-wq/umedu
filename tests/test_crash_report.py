import json

from app.crash_report import sanitize


def test_draft_answer_is_stripped_from_crash_json():
    draft = "ответ ученика 3,14 секрет"
    blob = sanitize({
        "build": 12,
        "exception": "IllegalStateException",
        "frames": [
            "ru.umedu.feature.train.TrainerViewModel.submit",
            "okhttp3.internal.http.CallServerInterceptor",
            "java.lang.Thread.run",
        ],
        "route": "train/{subject}/{number}",
        "last_api_error": 503,
        "answer": draft,
        "email": "kid@example.com",
        "authorization": "Bearer secret",
        "name": "Миша",
    })
    raw = json.dumps(blob, ensure_ascii=False)
    assert draft not in raw
    assert "kid@example.com" not in raw
    assert "Bearer" not in raw
    assert "Миша" not in raw
    assert blob["route"] == "train/{subject}/{number}"
    assert all("ru.umedu." in f for f in blob["frames"])
    assert "okhttp3" not in raw
