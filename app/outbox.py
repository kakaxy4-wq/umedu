"""Очередь попыток: один ключ идемпотентности — одна попытка.

На телефоне это Room. Здесь — тот же инвариант, чтобы его нельзя было
разъехать с Kotlin-тестами `:core:model`.
"""


class Outbox:
    def __init__(self):
        self._items = {}

    def enqueue(self, idempotency_key, payload):
        existing = self._items.get(idempotency_key)
        if existing is not None:
            return existing, False
        item = {"key": idempotency_key, "payload": dict(payload), "state": "pending"}
        self._items[idempotency_key] = item
        return item, True

    def pending(self):
        return [item for item in self._items.values() if item["state"] == "pending"]

    def mark_acked(self, idempotency_key):
        item = self._items[idempotency_key]
        item["state"] = "acked"
        return item
