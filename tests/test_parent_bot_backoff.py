"""Опрос Telegram: неудачи подряд — пауза растёт до потолка, в журнал пишем не каждую, после успеха всё сбрасывается."""
import asyncio
import logging
import urllib.request

from app import parent_bot


def test_next_delay_grows_and_caps():
    delays = [parent_bot.next_delay(n) for n in range(1, 12)]
    assert parent_bot.BACKOFF_START <= delays[0] <= parent_bot.BACKOFF_START * 1.1
    assert delays[1] >= parent_bot.BACKOFF_START * 2
    assert all(d <= parent_bot.BACKOFF_MAX * 1.1 for d in delays)
    assert delays[-1] >= parent_bot.BACKOFF_MAX


def test_should_warn_only_on_powers_of_two():
    assert [n for n in range(1, 20) if parent_bot.should_warn(n)] == [1, 2, 4, 8, 16]


def test_get_updates_timeout_is_quiet_and_poller_backs_off(monkeypatch, caplog):
    def boom(*a, **kw):
        raise TimeoutError()
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    monkeypatch.setattr(parent_bot.config, "TELEGRAM_TOKEN", "test-token")

    results = iter([False, False, False, True])
    monkeypatch.setattr(parent_bot, "connect", lambda: type("C", (), {"close": lambda self: None})())

    def fake_poll(_conn):
        ok = next(results, None)
        if ok is None:
            raise asyncio.CancelledError
        if not ok:
            assert parent_bot.call("getUpdates", quiet=True, timeout=0) is None
        return ok
    monkeypatch.setattr(parent_bot, "poll_once", fake_poll)

    sleeps = []

    async def fake_sleep(d):
        sleeps.append(d)
    monkeypatch.setattr(parent_bot.asyncio, "sleep", fake_sleep)

    caplog.set_level(logging.INFO, logger="codequest.parent_bot")
    try:
        asyncio.run(parent_bot.poller())
    except asyncio.CancelledError:
        pass

    assert len(sleeps) == 3 and sleeps[0] < sleeps[1] < sleeps[2]
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 2                       # 1-я и 2-я неудача, 3-я — молча
    assert all("TimeoutError" in r.getMessage() and "test-token" not in r.getMessage() for r in warnings)
    assert any(r.levelno == logging.INFO and "снова работает" in r.getMessage() for r in caplog.records)
    assert not any(r.levelno >= logging.ERROR for r in caplog.records)
