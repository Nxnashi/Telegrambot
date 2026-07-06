import logging
from telebot import types
from database import get_conn, get_request_by_id
from config import OPERATOR_IDS

logger = logging.getLogger(__name__)

user_data = {}


# =========================
# OPERATOR KEYBOARD
# =========================
def operator_keyboard(request_id):
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🔄 В процесс", callback_data=f"process_{request_id}"),
        types.InlineKeyboardButton("✔️ Выполнено", callback_data=f"done_{request_id}")
    )
    return markup


# =========================
# DASHBOARD (Mini App) KEYBOARD
# =========================
def dashboard_keyboard():
    from config import DASHBOARD_URL
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "🗂 Открыть доску заявок",
            web_app=types.WebAppInfo(DASHBOARD_URL)
        )
    )
    return markup


# =========================
# SEND TO OPERATOR
# =========================
def send_to_operator(bot, request_id, text, photo_id=None, file_type=None):
    conn = get_conn()
    cursor = conn.cursor()

    for op_id in OPERATOR_IDS:
        try:
            if photo_id and file_type == "photo":
                msg = bot.send_photo(op_id, photo_id, caption=text, reply_markup=operator_keyboard(request_id))
            elif photo_id and file_type == "document":
                msg = bot.send_document(op_id, photo_id, caption=text, reply_markup=operator_keyboard(request_id))
            else:
                msg = bot.send_message(op_id, text, reply_markup=operator_keyboard(request_id))

            cursor.execute("""
                INSERT INTO operator_messages (request_id, operator_id, message_id)
                VALUES (?, ?, ?)
            """, (request_id, op_id, msg.message_id))
        except Exception as e:
            logger.error(f"Ошибка отправки заявки оператору {op_id}: {e}")
            continue

    conn.commit()


# =========================
# КАНОНИЧЕСКИЙ ТЕКСТ ЗАЯВКИ (собирается из БД, не из старого текста сообщения)
# =========================
def build_request_text(request_id):
    row = get_request_by_id(request_id)
    if not row:
        return ""

    id_, user_id, restaurant, request_text, status, operator_name, rating, name, phone = row

    lines = [f"📌 Заявка #{id_}"]
    if name:
        lines.append(f"👤 Имя: {name}")
    if phone:
        lines.append(f"📞 Телефон: {phone}")
    lines.append(f"🏪 Ресторан: {restaurant}")
    lines.append("")
    lines.append(f"📝 Описание:\n{request_text}")

    return "\n".join(lines)


# =========================
# ОБНОВИТЬ СООБЩЕНИЕ У ОПЕРАТОРОВ
# =========================
def update_operator_message(bot, request_id, original_text, status, operator_name=None):
    conn = get_conn()
    cursor = conn.cursor()

    if status == "Заявка отправлена":
        status_bar = "🔴 Ожидает · ⬜ В процессе · ⬜ Выполнено"
    elif status == "Заявка в процессе":
        status_bar = "✅ Ожидает · 🟡 В процессе · ⬜ Выполнено"
    else:
        status_bar = "✅ Ожидает · ✅ В процессе · 🟢 Выполнено"

    operator_line = f"\n👨‍💼 Оператор: {operator_name}" if operator_name else ""
    new_text = f"{original_text}{operator_line}\n\n{status_bar}"

    cursor.execute("""
        SELECT operator_id, message_id FROM operator_messages WHERE request_id = ?
    """, (request_id,))

    for operator_id, message_id in cursor.fetchall():
        try:
            bot.edit_message_caption(operator_id, message_id, caption=new_text)
        except Exception:
            try:
                bot.edit_message_text(new_text, operator_id, message_id)
            except Exception as e:
                logger.error(f"Ошибка обновления сообщения у оператора {operator_id}: {e}")


# =========================
# USER UPDATE
# =========================
def send_user_update(bot, request_id, text, markup=None):
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT user_id FROM requests WHERE id = ?", (request_id,))
    result = cursor.fetchone()

    if not result:
        return

    try:
        bot.send_message(result[0], text, reply_markup=markup)
    except Exception as e:
        logger.error(f"Ошибка отправки обновления пользователю: {e}")


# =========================
# ВЗЯТЬ ЗАЯВКУ В РАБОТУ
# Используется и кнопкой в чате, и доской в мини-приложении
# =========================
def take_request(bot, request_id, operator_id, operator_name):
    """Возвращает (ok: bool, message: str)"""
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT status, operator_name FROM requests WHERE id = ?", (request_id,))
    result = cursor.fetchone()

    if not result:
        return False, "Заявка не найдена"

    status, current_operator = result

    if status == "Заявка в процессе":
        return False, f"Уже взял: {current_operator}"

    if status == "Выполнено":
        return False, "Заявка уже выполнена"

    cursor.execute(
        "UPDATE requests SET status = 'Заявка в процессе', operator_name = ? WHERE id = ?",
        (operator_name, request_id)
    )
    conn.commit()

    base_text = build_request_text(request_id)
    update_operator_message(bot, request_id, base_text, "Заявка в процессе", operator_name)

    cursor.execute("SELECT operator_id, message_id FROM operator_messages WHERE request_id = ?", (request_id,))
    for op_id, message_id in cursor.fetchall():
        try:
            if op_id == operator_id:
                done_markup = types.InlineKeyboardMarkup()
                done_markup.add(types.InlineKeyboardButton("✔️ Выполнено", callback_data=f"done_{request_id}"))
                bot.edit_message_reply_markup(op_id, message_id, reply_markup=done_markup)
            else:
                bot.edit_message_reply_markup(op_id, message_id, reply_markup=None)
        except Exception as e:
            logger.error(f"Ошибка редактирования кнопок: {e}")

    from database import open_chat
    cursor.execute("SELECT user_id FROM requests WHERE id = ?", (request_id,))
    user_id = cursor.fetchone()[0]
    open_chat(request_id, user_id, operator_id)

    try:
        bot.send_message(
            operator_id,
            f"✅ Вы взяли заявку #{request_id}\n\n💬 Чат с пользователем открыт. Просто пишите сообщения."
        )
    except Exception as e:
        logger.error(f"Ошибка уведомления оператора: {e}")

    try:
        bot.send_message(
            user_id,
            f"👋 Доброго времени суток! С вами на связи оператор {operator_name}.\n\nВы можете задавать вопросы по вашей заявке."
        )
    except Exception as e:
        logger.error(f"Ошибка уведомления пользователя: {e}")

    logger.info(f"Заявка #{request_id} взята оператором {operator_name}")
    return True, f"Заявка #{request_id} взята в работу"


# =========================
# ЗАВЕРШИТЬ ЗАЯВКУ
# Используется и кнопкой в чате, и доской в мини-приложении
# =========================
def complete_request(bot, request_id, operator_id, operator_name):
    """Возвращает (ok: bool, message: str)"""
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT status, operator_name FROM requests WHERE id = ?", (request_id,))
    result = cursor.fetchone()

    if not result:
        return False, "Заявка не найдена"

    status, current_operator = result

    if status == "Выполнено":
        return False, "Заявка уже выполнена"

    if status == "Заявка отправлена":
        return False, "Сначала возьмите заявку в работу"

    if current_operator and current_operator != operator_name:
        return False, f"Заявка закреплена за {current_operator}"

    cursor.execute("UPDATE requests SET status = 'Выполнено' WHERE id = ?", (request_id,))
    conn.commit()

    from database import close_chat
    close_chat(request_id)

    cursor.execute("SELECT user_id FROM requests WHERE id = ?", (request_id,))
    user_id = cursor.fetchone()[0]

    try:
        bot.send_message(user_id, "🔒 Чат по заявке закрыт.")
    except Exception as e:
        logger.error(f"Ошибка уведомления пользователя: {e}")

    try:
        bot.send_message(operator_id, f"✅ Заявка #{request_id} выполнена\n🔒 Чат закрыт.")
    except Exception as e:
        logger.error(f"Ошибка уведомления оператора: {e}")

    base_text = build_request_text(request_id)
    update_operator_message(bot, request_id, base_text, "Выполнено", current_operator)

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⭐ Плохо", callback_data=f"rate_1_{request_id}"))
    markup.add(types.InlineKeyboardButton("⭐⭐ Нормально", callback_data=f"rate_2_{request_id}"))
    markup.add(types.InlineKeyboardButton("⭐⭐⭐ Отлично", callback_data=f"rate_3_{request_id}"))
    send_user_update(bot, request_id, "Ваша заявка выполнена. Оцените работу:", markup)

    logger.info(f"Заявка #{request_id} выполнена оператором {current_operator}")
    return True, f"Заявка #{request_id} выполнена"


# =========================
# BAD REVIEW
# =========================
def get_bad_review(bot, message):
    chat_id = message.chat.id
    data = user_data.get(chat_id)

    if not data:
        return

    send_final_review(bot, data["request_id"], data["rating"], message.text, chat_id)


# =========================
# FINAL REVIEW
# =========================
def send_final_review(bot, request_id, rating, reason, chat_id):
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("UPDATE requests SET rating = ? WHERE id = ?", (rating, request_id))
    conn.commit()

    bot.send_message(chat_id, "Спасибо за ваш отзыв 🙏")

    text = f"📊 Отзыв по заявке #{request_id}\n\nОценка: {rating}"
    if reason:
        text += f"\n\n❗ Причина:\n{reason}"

    for op_id in OPERATOR_IDS:
        try:
            bot.send_message(op_id, text)
        except Exception as e:
            logger.error(f"Ошибка отправки отзыва оператору {op_id}: {e}")

    user_data.pop(chat_id, None)


# =========================
# CALLBACK + КОМАНДЫ ОПЕРАТОРОВ
# =========================
def register_operator_handlers(bot):

    # =========================
    # /stats
    # =========================
    @bot.message_handler(commands=["stats"])
    def stats(message):
        if message.from_user.id not in OPERATOR_IDS:
            return

        from database import get_operator_stats
        operator_name = message.from_user.first_name
        total, done, ratings = get_operator_stats(operator_name)

        rating_text = ""
        for rating, count in ratings:
            rating_text += f"  {rating}: {count}\n"

        text = f"""📊 Статистика оператора {operator_name}

        📋 Всего взято заявок: {total}
        ✅ Выполнено: {done}
        🔄 В работе: {total - done}

        ⭐ Оценки:
        {rating_text if rating_text else "  Нет оценок"}"""

        bot.send_message(message.chat.id, text)

    # =========================
    # /active
    # =========================
    @bot.message_handler(commands=["active"])
    def active(message):
        if message.from_user.id not in OPERATOR_IDS:
            return

        from database import get_active_requests
        rows = get_active_requests()

        if not rows:
            bot.send_message(message.chat.id, "Нет активных заявок ✅")
            return

        text = "📋 Активные заявки:\n\n"

        for row in rows:
            request_id, restaurant, status, operator_name = row
            text += f"📌 Заявка #{request_id}\n"
            text += f"🏪 Ресторан: {restaurant}\n"
            text += f"📊 Статус: {status}\n"
            if operator_name:
                text += f"👨‍💼 Оператор: {operator_name}\n"
            text += "\n"

        bot.send_message(message.chat.id, text)

    @bot.message_handler(func=lambda message: (message.text or "") == "📊 Статистика" and message.from_user.id in OPERATOR_IDS)
    def btn_stats(message):
        from database import get_operator_stats
        operator_name = message.from_user.first_name
        total, done, ratings = get_operator_stats(operator_name)
        rating_text = ""
        for rating, count in ratings:
            rating_text += f"  {rating}: {count}\n"
        text = f"""📊 Статистика оператора {operator_name}

📋 Всего взято заявок: {total}
✅ Выполнено: {done}
🔄 В работе: {total - done}

⭐ Оценки:
{rating_text if rating_text else "  Нет оценок"}"""
        bot.send_message(message.chat.id, text)

    @bot.message_handler(func=lambda message: (message.text or "") == "📋 Активные заявки" and message.from_user.id in OPERATOR_IDS)
    def btn_active(message):
        from database import get_active_requests
        rows = get_active_requests()
        if not rows:
            bot.send_message(message.chat.id, "Нет активных заявок ✅")
            return
        text = "📋 Активные заявки:\n\n"
        for row in rows:
            request_id, restaurant, status, operator_name = row
            text += f"📌 Заявка #{request_id}\n"
            text += f"🏪 Ресторан: {restaurant}\n"
            text += f"📊 Статус: {status}\n"
            if operator_name:
                text += f"👨‍💼 Оператор: {operator_name}\n"
            text += "\n"
        bot.send_message(message.chat.id, text)

    # =========================
    # 🗂 ДОСКА ЗАЯВОК (Mini App)
    # =========================
    @bot.message_handler(func=lambda message: (message.text or "") == "🗂 Доска заявок" and message.from_user.id in OPERATOR_IDS)
    def btn_dashboard(message):
        bot.send_message(
            message.chat.id,
            "Открой доску, чтобы видеть все заявки и перетаскивать их между статусами:",
            reply_markup=dashboard_keyboard()
        )

    # =========================
    # CALLBACKS
    # =========================
    @bot.callback_query_handler(func=lambda call: True)
    def handle_call(call):
        data = call.data

        # =========================
        # 🔄 В ПРОЦЕСС
        # =========================
        if data.startswith("process_"):
            request_id = data.split("_")[1]
            operator_name = call.from_user.first_name
            ok, msg = take_request(bot, request_id, call.from_user.id, operator_name)
            bot.answer_callback_query(call.id, None if ok else msg, show_alert=not ok)

        # =========================
        # ✔️ ВЫПОЛНЕНО
        # =========================
        elif data.startswith("done_"):
            request_id = data.split("_")[1]
            operator_name = call.from_user.first_name
            ok, msg = complete_request(bot, request_id, call.from_user.id, operator_name)
            bot.answer_callback_query(call.id, None if ok else msg, show_alert=not ok)

        # =========================
        # ⭐ РЕЙТИНГ
        # =========================
        elif data.startswith("rate_"):
            parts = data.split("_")
            rating = parts[1]
            request_id = parts[2]
            chat_id = call.message.chat.id

            bot.answer_callback_query(call.id)

            try:
                bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            except Exception as e:
                logger.error(f"Ошибка удаления кнопок оценки: {e}")

            if rating == "1":
                user_data[chat_id] = {"request_id": request_id, "rating": "Плохо"}
                msg = bot.send_message(chat_id, "😔 Напишите, что именно не понравилось")
                bot.register_next_step_handler(msg, lambda m: get_bad_review(bot, m))
            else:
                send_final_review(
                    bot, request_id,
                    "Нормально" if rating == "2" else "Отлично",
                    None, chat_id
                )

    # =========================
    # CHAT: OPERATOR → USER
    # =========================
    ADMIN_BUTTONS = ["📊 Статистика операторов", "📥 Экспорт заявок в Excel", "📋 Активные заявки", "🗂 Доска заявок"]

    @bot.message_handler(func=lambda message: message.from_user.id in OPERATOR_IDS and not (message.text or "").startswith("/") and message.text not in ADMIN_BUTTONS)
    def operator_message(message):
        from database import get_chat_by_operator
        chat = get_chat_by_operator(message.from_user.id)

        if not chat:
            return

        user_id = chat[1]
        operator_name = message.from_user.first_name
        try:
            bot.send_message(user_id, f"💬 Оператор {operator_name}:\n{message.text}")
        except Exception as e:
            logger.error(f"Ошибка пересылки сообщения пользователю {user_id}: {e}")
