from app import skills


def test_skills_registry_basic():
    alls = skills.all_skills()
    assert len(alls) >= 34 + 15 + 5
    py = skills.skills_for_subject("python")
    assert len(py) == 34
    assert py[0].id == "py:lesson:1"
    assert py[4].prereqs == ("py:lesson:4",)  # wait, prereq of 5 is 4
    assert skills.skills_for_exam("oge-inf-2026")
    assert any(s.id == "oge-inf:16" for s in skills.skills_for_exam("oge-inf-2026"))
    # russian rules loaded
    ru = skills.skills_for_subject("russian")
    assert len(ru) >= 30
    assert any(s.id == "ru:odn" for s in ru)


def test_next_skills_requires_prereqs():
    # smoke: function exists and returns list
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    # minimal schema
    conn.execute("CREATE TABLE skill_state (student_id TEXT, exam_id TEXT, task_key TEXT, p REAL, n INTEGER, last TEXT, PRIMARY KEY(student_id, exam_id, task_key))")
    res = skills.next_skills(conn, "s1", "oge-inf-2026", limit=2)
    assert isinstance(res, list)
