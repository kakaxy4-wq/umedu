from app.content import oge_u2


def _doc13(data):
    if data["kind"] == "bullets":
        return data["n"] * data["k"]
    if data["kind"] == "bytes":
        return data["chars"] * data["b"]
    return data["content"] + 1


def test_purchase_sentences_agree_in_gender_and_case():
    """«Аня купил» и «32 карандашей» не появляются ни на одном из тысячи сидов."""
    import re
    from app.content.oge_u2 import _FEMALE, _GOODS, _bought, _noun
    female_wrong = re.compile(r"(%s) купил (?!а)" % "|".join(sorted(_FEMALE)))
    male = [n for n in ("Аня", "Боря", "Вера", "Глеб", "Даша", "Егор", "Зоя", "Кирилл") if n not in _FEMALE]
    male_wrong = re.compile(r"(%s) купила " % "|".join(male))
    seen_forms = set()
    for seed in range(1, 1001):
        text = oge_u2.make(11, seed)["text"]
        assert not female_wrong.search(text), text
        assert not male_wrong.search(text), text
        for forms in _GOODS.values():
            for n in range(1, 41):
                word = _noun(n, forms)
                if ("%d %s" % (n, word)) in text:
                    seen_forms.add((n % 10, word))
                    assert word == _noun(n, forms)
        for bad in (r"(?<!\d)1 карандашей\b", r"(?<!\d)1 яблок\b", r"(?<!\d)2 карандашей\b",
                    r"(?<!\d)32 карандашей\b", r"(?<!\d)33 открыток\b", r"(?<!\d)1 открыток\b",
                    r"(?<!\d)4 тетрадей\b", r"(?<!\d)21 яблок\b"):
            assert not re.search(bad, text), (seed, bad, text)
    assert _bought("Аня") == "купила" and _bought("Боря") == "купил"
    assert seen_forms


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