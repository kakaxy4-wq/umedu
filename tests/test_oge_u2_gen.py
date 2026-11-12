from app.content import oge_u2


def test_oge_u2_generators_contract():
    for num in (11, 14):
        texts = set()
        for seed in range(1, 51):
            v = oge_u2.make(num, seed)
            assert v == oge_u2.make(num, seed), (num, seed)
            assert v["num"] == num and v["seed"] == seed
            assert "text" in v and "answer" in v and "steps" in v
            texts.add(v["text"])
        assert len(texts) >= 10, (num, len(texts))