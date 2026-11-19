from app.content import oge_u2


def _doc13(data):
    if data["kind"] == "bullets":
        return data["n"] * data["k"]
    if data["kind"] == "bytes":
        return data["chars"] * data["b"]
    return data["content"] + 1


def test_oge_u2_generators_contract():
    for num in (11, 13, 14):
        texts = set()
        for seed in range(1, 51):
            v = oge_u2.make(num, seed)
            assert v == oge_u2.make(num, seed), (num, seed)
            assert v["num"] == num and v["seed"] == seed
            assert "text" in v and "answer" in v and "steps" in v
            if num == 13:
                assert v["answer"] == str(_doc13(v["data"]))
            texts.add(v["text"])
        assert len(texts) >= 10, (num, len(texts))