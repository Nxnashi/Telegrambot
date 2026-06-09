import sqlite3
from threading import local

_thread_local = local()


def get_conn():
    if not hasattr(_thread_local, "conn"):
        _thread_local.conn = sqlite3.connect(
            "database.db",
            check_same_thread=False
        )

    return _thread_local.conn


def create_tables():
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        telegram_id INTEGER PRIMARY KEY,
        name TEXT,
        phone TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        restaurant_name TEXT,
        request_text TEXT,
        photo_id TEXT,
        status TEXT,
        operator_name TEXT,
        rating TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS operator_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER,
        operator_id INTEGER,
        message_id INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS active_chats (
        request_id INTEGER PRIMARY KEY,
        user_id INTEGER,
        operator_id INTEGER
    )
    """)

    conn.commit()


def add_user(telegram_id, name, phone):
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT OR REPLACE INTO users (telegram_id, name, phone)
    VALUES (?, ?, ?)
    """, (telegram_id, name, phone))

    conn.commit()


def create_request(user_id, restaurant_name, request_text, photo_id):
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO requests (
        user_id,
        restaurant_name,
        request_text,
        photo_id,
        status
    )
    VALUES (?, ?, ?, ?, ?)
    """, (
        user_id,
        restaurant_name,
        request_text,
        photo_id,
        "Заявка отправлена"
    ))

    conn.commit()

    return cursor.lastrowid


def open_chat(request_id, user_id, operator_id):
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT OR REPLACE INTO active_chats (
        request_id,
        user_id,
        operator_id
    )
    VALUES (?, ?, ?)
    """, (
        request_id,
        user_id,
        operator_id
    ))

    conn.commit()


def close_chat(request_id):
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    DELETE FROM active_chats
    WHERE request_id = ?
    """, (request_id,))

    conn.commit()


def get_chat_by_user(user_id):
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT request_id, operator_id
    FROM active_chats
    WHERE user_id = ?
    """, (user_id,))

    return cursor.fetchone()


def get_chat_by_operator(operator_id):
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT request_id, user_id
    FROM active_chats
    WHERE operator_id = ?
    """, (operator_id,))

    return cursor.fetchone()


def get_user_history(user_id):
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        id,
        restaurant_name,
        status,
        operator_name,
        rating
    FROM requests
    WHERE user_id = ?
    ORDER BY id DESC
    LIMIT 10
    """, (user_id,))

    return cursor.fetchall()


def get_operator_stats(operator_name):
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT COUNT(*)
    FROM requests
    WHERE operator_name = ?
    """, (operator_name,))

    total = cursor.fetchone()[0]

    cursor.execute("""
    SELECT COUNT(*)
    FROM requests
    WHERE operator_name = ?
    AND status = 'Выполнено'
    """, (operator_name,))

    done = cursor.fetchone()[0]

    cursor.execute("""
    SELECT rating, COUNT(*)
    FROM requests
    WHERE operator_name = ?
    AND rating IS NOT NULL
    GROUP BY rating
    """, (operator_name,))

    ratings = cursor.fetchall()

    return total, done, ratings


def get_active_requests():
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        id,
        restaurant_name,
        status,
        operator_name
    FROM requests
    WHERE status != 'Выполнено'
    ORDER BY id DESC
    """)

    return cursor.fetchall()


def get_all_operators_stats():
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        operator_name,
        COUNT(*) as total,
        SUM(CASE WHEN status = 'Выполнено' THEN 1 ELSE 0 END) as done,
        SUM(CASE WHEN rating = 'Отлично' THEN 1 ELSE 0 END) as great,
        SUM(CASE WHEN rating = 'Нормально' THEN 1 ELSE 0 END) as ok,
        SUM(CASE WHEN rating = 'Плохо' THEN 1 ELSE 0 END) as bad
    FROM requests
    WHERE operator_name IS NOT NULL
    GROUP BY operator_name
    ORDER BY done DESC
    """)

    return cursor.fetchall()


def get_all_requests():
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        id,
        user_id,
        restaurant_name,
        request_text,
        status,
        operator_name,
        rating
    FROM requests
    ORDER BY id DESC
    """)

    return cursor.fetchall()

