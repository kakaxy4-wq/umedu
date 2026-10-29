from app.outbox import Outbox


def test_same_key_does_not_create_second_attempt():
    box = Outbox()
    first, created = box.enqueue("k1", {"answer": "12"})
    second, created_again = box.enqueue("k1", {"answer": "99"})
    assert created is True
    assert created_again is False
    assert first is second
    assert second["payload"]["answer"] == "12"
    assert len(box.pending()) == 1
