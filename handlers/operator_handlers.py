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
    update_operator_message(bot,
