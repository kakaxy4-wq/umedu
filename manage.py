#!/usr/bin/env python3
"""Управление КодКвестом.

  python manage.py init                 — создать базу, преподавателя и (по желанию) первого ученика
  python manage.py migrate              — обновить схему базы (выполняется и при старте сайта)
  python manage.py passwd <логин>       — сменить пароль
  python manage.py name <логин> <имя>   — имя ученика для приветствия и публичных страниц
  python manage.py students             — список учеников
  python manage.py backup               — копия базы в data/backups/
  python manage.py purge-inactive       — кто будет удалён через год без занятий (база не меняется)
  python manage.py purge-inactive --apply
                                        — удалить таких учеников и пустые кабинеты родителей
                                        Сайт делает это сам раз в сутки. Выключить: CQ_PURGE_INACTIVE=0
  python manage.py delete-student <логин> [--apply]
  python manage.py delete-parent <логин> [--apply]
                                        — удалить один аккаунт; без --apply только показывает, что пропадёт
  python manage.py seed_demo            — демо-ученик, родитель и класс с попытками за 2 недели.
                                        Только стенд (CQ_STAGE=1). На проде команда отказывается
                                        и базу не меняет. Повторный запуск тоже ничего не меняет.

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


def _print_purge(report):
    for st in report["students"]:
        print("ученик %-16s %-20s последнее: %s%s" % (
            st["username"], st["display_name"], st["last"], " · младше 14" if st["minor"] else ""))
    for p in report["parents"]:
        print("родитель %-16s %-20s последнее: %s" % (p["username"], p["display_name"], p["last"]))
    if not report["students"] and not report["parents"]:
        print("Некого удалять.")
    elif report["dry_run"]:
        print("База не изменена. Чтобы удалить, добавьте --apply.")
    else:
        print("Удалено: учеников %d, родителей %d." % (len(report["students"]), len(report["parents"])))


def cmd_purge(apply):
    init_db()
    from app import account
    _print_purge(account.purge_inactive(connect(), dry_run=not apply))


def cmd_delete_student(login, apply):
    init_db()
    from app import account
    conn = connect()
    row = conn.execute("SELECT id, username, display_name FROM users WHERE username = ? AND role = 'student'",
                       (login.lower(),)).fetchone()
    if not row:
        sys.exit("Нет ученика %s" % login)
    print("Ученик %s (%s), id=%d. Удалятся аккаунт, ответы, прогресс, проекты, согласия и файлы." % (
        row["username"], row["display_name"], row["id"]))
    if not apply:
        print("База не изменена. Чтобы удалить, добавьте --apply.")
        return
    account.delete_student(conn, row["id"])
    print("Удалено.")


def cmd_delete_parent(login, apply):
    init_db()
    from app import account
    conn = connect()
    row = conn.execute("SELECT id, username, display_name FROM parents WHERE username = ?", (login.lower(),)).fetchone()
    if not row:
        sys.exit("Нет родителя %s" % login)
    kids = account.exclusive_minors(conn, row["id"])
    print("Родитель %s (%s), id=%d." % (row["username"], row["display_name"], row["id"]))
    if kids:
        print("Вместе с ним удалятся дети младше 14 лет: %s." % ", ".join(k["display_name"] for k in kids))
    if not apply:
        print("База не изменена. Чтобы удалить, добавьте --apply.")
        return
    account.delete_parent(conn, row["id"])
    print("Удалено.")


def cmd_seed_demo():
    from app.demo import DemoRefused, seed_demo
    if not config.STAGE:
        sys.stderr.write("seed_demo только для тестового стенда (CQ_STAGE=1). База не изменена.\n")
        sys.exit(1)
    init_db()
    try:
        report = seed_demo(connect())
    except DemoRefused as exc:
        sys.stderr.write(str(exc) + "\n")
        sys.exit(1)
    if report["created"]:
        print("Демо-класс записан: %d учеников, попыток %d, дни %s … %s." % (
            report["members"], report["attempts"], report["first_day"], report["last_day"]))
    else:
        print("Демо уже есть, база не изменена. Попыток %d, дни %s … %s." % (
            report["attempts"], report["first_day"], report["last_day"]))
    print("Преподаватель: %s. Пароль demo-teacher — только если учётки ещё не было, иначе пароль прежний." % report["teacher"])
    for login in report["students"]:
        print("Ученик %s / %s" % (login, report["passwords"][login]))
    print("Родитель %s / %s" % (report["parent"], report["passwords"][report["parent"]]))
    print("Пароли только для стенда. Данные можно стереть.")


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
    elif args[0] == "purge-inactive":
        cmd_purge(apply="--apply" in args[1:])
    elif args[0] == "delete-student" and len(args) >= 2:
        cmd_delete_student(args[1], apply="--apply" in args[2:])
    elif args[0] == "delete-parent" and len(args) >= 2:
        cmd_delete_parent(args[1], apply="--apply" in args[2:])
    elif args[0] == "has-users":
        init_db()
        sys.exit(0 if connect().execute("SELECT COUNT(*) FROM users").fetchone()[0] else 1)
    elif args[0] == "seed_demo":
        cmd_seed_demo()
    else:
        print(__doc__)
        sys.exit(1)
