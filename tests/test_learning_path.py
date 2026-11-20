import sqlite3

from app import learning_path, skills, today


def test_learning_path_enriches_plan():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    # minimal schema for today.plan (needs users, skill_state, etc.) — skip full; just check callable + skill mapping
    assert callable(learning_path.enriched_plan)
    # skill_for_step mapping sanity
    step = {"key": "oge", "title": "ОГЭ №12: 3 упражнения"}
    assert learning_path._skill_for_step(step, conn, "s1") == "oge-inf:12"


def test_skills_registry_basic():
    alls = skills.all_skills()
    assert len(alls) >= 34 + 15 + 5
    py = skills.skills_for_subject("python")
    assert len(py) == 34
    assert py[0].id == "py:lesson:1"
    assert py[4].prereqs == ("py:lesson:4",)
    ru = skills.skills_for_subject("russian")
    assert len(ru) >= 30
    assert any(s.id == "ru:odn" for s in ru)
    assert any(s.id == "oge-inf:16" for s in skills.skills_for_exam("oge-inf-2026"))
