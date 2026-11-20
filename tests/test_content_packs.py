from app.content import packs, ru


def test_ru_rules_pack_matches_hardcoded():
    loaded = packs.load_ru_rules()
    assert len(loaded) == len(ru.RULES)
    for rid, (title, text) in ru.RULES.items():
        assert rid in loaded, rid
        assert loaded[rid] == (title, text), rid


def test_list_packs():
    assert "ru_rules.yaml" in packs.list_packs()
