"""Инвариант генераторов extra_math: ответ совпадает с независимым пересчётом из data."""
import random

from app.content import extra_math
from app.content.extra_math import ABOUT, MATH, recompute


def test_every_generator_answer_matches_recompute():
    for (exam, key), fn in sorted(MATH.items()):
        for seed in range(25):
            item = fn(random.Random("%s-%s-%d" % (exam, key, seed)))
            assert item["text"], (exam, key, seed)
            assert item["explain"] and item["steps"], (exam, key, seed)
            assert str(recompute(item["data"])) == item["answer"], (exam, key, seed, item)


def test_registry_has_about_for_every_key():
    # ABOUT шире реестра (описывает и номера без генератора), главное — не забыть новый
    assert set(MATH) <= set(ABOUT)


def test_remainder_generator():
    for seed in range(60):
        item = extra_math._remainder(random.Random(seed))
        d = item["data"]
        rest = d["a"] % d["b"]
        assert d["kind"] == "remainder"
        assert int(item["answer"]) == rest
        assert 0 < rest < d["b"], "остаток строго меньше делителя и не ноль"
        assert d["a"] > d["b"] * 5, "делимое заметочно больше делителя"
        assert ("%d" % d["a"]) in item["text"] and ("%d" % d["b"]) in item["text"]
        assert str(recompute(d)) == item["answer"]
    # разные сиды дают разные числа — генератор не зациклен на одном примере
    answers = {extra_math._remainder(random.Random(s))["answer"] for s in range(30)}
    assert len(answers) > 1
