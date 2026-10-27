#!/usr/bin/env python3
"""Управление КодКвестом.

  python manage.py init                 — создать базу, преподавателя и (по желанию) первого ученика
  python manage.py migrate              — обновить схему базы (выполняется и при старте сайта)
  python manage.py passwd <логин>       — сменить пароль
  python manage.py name <логин> <имя>   — имя ученика для приветствия и публичных страниц
  python manage.py students             — список учеников
  python manage.py backup               — копия базы в data/backups/

Учеников удобнее добавлять на сайте: «👥 Ученики» → «Добавить ученика».
"""
import getpass
import shutil
import sqlite3
import sys
from datetime import datetime

from app import auth, config, students
from app.db import connect, init_db


def ask_password(prompt):
    while True:
        p1 = getpass.getpass(prompt)
        if len(p1) < 6:
            print("  Пароль должен быть не короче 6 символов.")
            continue
        if getpass.getpass("  Ещё раз: ") != p1:
            print("  Пароли не совпали.")
            continue
        return p1


def create_user(conn, role, username, display_name, password):
    """Создаёт аккаунт или обновляет пароль и имя существующего. Ученик получает открытый урок 1 и входной тест."""
    with conn:
        row = conn.execute("SELECT id FROM users WHERE username = ?", (username.lower(),)).fetchone()
        if row:
            conn.execute("UPDATE users SET password_hash = ?, display_name = ? WHERE id = ?",
                         (auth.hash_password(password), display_name, row["id"]))
            return row["id"]
        if role == "student":
            return students.create_student(conn, username, display_name, password)
        return conn.execute("INSERT INTO users (username, password_hash, role, display_name) VALUES (?, ?, 'teacher', ?)",
                            (username.lower(), auth.hash_password(password), display_name)).lastrowid


def cmd_init():
    init_db()
    conn = connect()
    print("== Аккаунт преподавателя ==")
    t_login = input("Логин преподавателя [teacher]: ").strip() or "teacher"
    t_name = input("Как тебя называть [Преподаватель]: ").strip() or "Преподаватель"
    create_user(conn, "teacher", t_login, t_name, ask_password("Пароль преподавателя: "))
    print("\n== Первый ученик (Enter — пропустить, добавишь потом на сайте) ==")
    s_login = input("Логин ученика: ").strip()
    if s_login:
        s_name = input("Имя ученика (для приветствия): ").strip() or "Ученик"
        create_user(conn, "student", s_login, s_name, ask_password("Пароль ученика: "))
    print("\nГотово! База: %s" % config.DB_PATH)


def cmd_passwd(login):
    conn = connect()
    row = conn.execute("SELECT id FROM users WHERE username = ?", (login.lower(),)).fetchone()
    if not row:
        sys.exit("Нет пользователя %s" % login)
    with conn:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                     (auth.hash_password(ask_password("Новый пароль: ")), row["id"]))
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (row["id"],))
    print("Пароль изменён, старые входы сброшены.")


def cmd_name(login, name):
    init_db()
    conn = connect()
    with conn:
        n = conn.execute("UPDATE users SET display_name = ? WHERE username = ? AND role = 'student'",
                         (name, login.lower())).rowcount
    if not n:
        sys.exit("Нет ученика с логином %s" % login)
    print("Имя ученика %s: %s" % (login, name))


def cmd_students():
    init_db()
    for s in students.list_students(connect(), include_archived=True):
        print("%-16s %-20s %s" % (s["username"], s["display_name"], "" if s["active"] else "(архив)"))


def cmd_backup():
    dest_dir = config.DATA_DIR / "backups"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / ("codequest-%s.db" % datetime.now().strftime("%Y%m%d-%H%M%S"))
    src = sqlite3.connect(config.DB_PATH)
    out = sqlite3.connect(dest)
    src.backup(out)
    out.close()
    src.close()
    # храним последние 30 копий
    for old in sorted(dest_dir.glob("codequest-*.db"))[:-30]:
        old.unlink()
    print("Копия: %s" % dest)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
    elif args[0] == "init":
        cmd_init()
    elif args[0] == "passwd" and len(args) == 2:
        cmd_passwd(args[1])
    elif args[0] == "name" and len(args) >= 3:
        cmd_name(args[1], " ".join(args[2:]))
    elif args[0] == "students":
        cmd_students()
    elif args[0] == "migrate":
        init_db()
        print("Схема базы актуальна: %s" % config.DB_PATH)
    elif args[0] == "backup":
        cmd_backup()
    elif args[0] == "has-users":
        init_db()
        sys.exit(0 if connect().execute("SELECT COUNT(*) FROM users").fetchone()[0] else 1)
    else:
        print(__doc__)
        sys.exit(1)
