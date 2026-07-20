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

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS request_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER,
        event_type TEXT,
        actor_name TEXT,
        details TEXT,
        created_at TEXT
    )
    """)

    conn.commit()

    # Миграция: добавляем колонку reason (причина отмены/отсрочки),
    # если её ещё нет (для баз, созданных до этого обновления)
    cursor.execute("PRAGMA table_info(requests)")
    columns = [row[1] for row in cursor.fetchall()]
    if "reason" not in columns:
        cursor.execute("ALTER TABLE requests ADD COLUMN reason TEXT")
        conn.commit()
    if "created_at" not in columns:
        cursor.execute("ALTER TABLE requests ADD COLUMN created_at TEXT")
        conn.commit()
    if "updated_at" not in columns:
        cursor.execute("ALTER TABLE requests ADD COLUMN updated_at TEXT")
        conn.commit()
    if "reminder_count" not in columns:
        cursor.execute("ALTER TABLE requests ADD COLUMN reminder_count INTEGER DEFAULT 0")
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
        status,
        created_at,
        updated_at
    )
    VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))
    """, (
        user_id,
        restaurant_name,
        request_text,
        photo_id,
        "Заявка отправлена"
    ))

    conn.commit()

    return cursor.lastrowid


def get_unclaimed_requests():
    """
    Заявки, которые до сих пор никто не взял в работу,
    с количеством уже отправленных напоминаний и временем ожидания в минутах.
    """
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        id,
        restaurant_name,
        COALESCE(reminder_count, 0),
        (strftime('%s', 'now') - strftime('%s', created_at)) / 60.0 AS elapsed_min
    FROM requests
    WHERE status = 'Заявка отправлена'
    AND created_at IS NOT NULL
    """)

    return cursor.fetchall()


def bump_reminder(request_id):
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE requests SET reminder_count = COALESCE(reminder_count, 0) + 1 WHERE id = ?",
        (request_id,)
    )

    conn.commit()


def log_event(request_id, event_type, actor_name=None, details=None):
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO request_events (request_id, event_type, actor_name, details, created_at)
        VALUES (?, ?, ?, ?, datetime('now'))
    """, (request_id, event_type, actor_name, details))

    conn.commit()


def get_events(limit=200, request_id=None):
    conn = get_conn()
    cursor = conn.cursor()

    if request_id:
        cursor.execute("""
            SELECT id, request_id, event_type, actor_name, details, created_at
            FROM request_events
            WHERE request_id = ?
            ORDER BY id DESC
            LIMIT ?
        """, (request_id, limit))
    else:
        cursor.execute("""
            SELECT id, request_id, event_type, actor_name, details, created_at
            FROM request_events
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))

    return cursor.fetchall()


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


def get_chats_by_operator(operator_id):
    """Все активные диалоги оператора (может быть несколько сразу)."""
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT ac.request_id, ac.user_id, r.restaurant_name
    FROM active_chats ac
    LEFT JOIN requests r ON r.id = ac.request_id
    WHERE ac.operator_id = ?
    ORDER BY ac.request_id
    """, (operator_id,))

    return cursor.fetchall()


def get_request_id_by_operator_message(operator_id, message_id):
    """По какой заявке было отправлено конкретное сообщение оператору (для reply)."""
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT request_id FROM operator_messages
    WHERE operator_id = ? AND message_id = ?
    """, (operator_id, message_id))

    row = cursor.fetchone()
    return row[0] if row else None


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
    WHERE status NOT IN ('Выполнено', 'Отменена')
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
        rating,
        reason
    FROM requests
    ORDER BY id DESC
    """)

    return cursor.fetchall()


def get_request_by_id(request_id):
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        r.id, r.user_id, r.restaurant_name, r.request_text,
        r.status, r.operator_name, r.rating,
        u.name, u.phone, r.reason
    FROM requests r
    LEFT JOIN users u ON u.telegram_id = r.user_id
    WHERE r.id = ?
    """, (request_id,))

    return cursor.fetchone()


def get_dashboard_requests(done_limit=50):
    conn = get_conn()
    cursor = conn.cursor()

    base_select = """
    SELECT
        r.id, r.restaurant_name, r.status, r.operator_name,
        r.request_text, r.rating, u.name, u.phone, r.reason
    FROM requests r
    LEFT JOIN users u ON u.telegram_id = r.user_id
    """

    cursor.execute(base_select + "WHERE r.status NOT IN ('Выполнено', 'Отменена') ORDER BY r.id DESC")
    active = cursor.fetchall()

    # Выполненные/отменённые показываем на доске только за сегодня —
    # остальная история остаётся доступной во вкладке "Журнал"
    cursor.execute(
        base_select
        + "WHERE r.status IN ('Выполнено', 'Отменена') AND date(r.updated_at) = date('now') "
        + "ORDER BY r.id DESC LIMIT ?",
        (done_limit,)
    )
    done = cursor.fetchall()

    return active + done

