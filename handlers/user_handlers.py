import logging
from telebot import types

from keyboards import user_menu
from config import OPERATOR_IDS, WEBAPP_URL
from database import get_user_history, get_chat_by_user

logger = logging.getLogger(__name__)


def webapp_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "📝 Оставить заявку",
            web_app=types.WebAppInfo(WEBAPP_URL)
        )
    )
    return markup


def register_user_handlers(bot):

    # =========================
    # START
    # =========================
    @bot.message_handler(commands=["start"])
    def start(message):
        logger.info(f"/start от {message.from_user.id}, OPERATOR_IDS: {OPERATOR_IDS}")
        try:
            if message.from_user.id in OPERATOR_IDS:
                from keyboards import operator_menu
                from config import ADMIN_IDS
                if message.from_user.id in ADMIN_IDS:
                    bot.send_message(message.chat.id, "Добро пожаловать, админ! Напишите /admin для панели администратора.", reply_markup=operator_menu())
                else:
                    bot.send_message(message.chat.id, "Добро пожаловать!", reply_markup=operator_menu())
                return

            bot.send_message(
                message.chat.id,
                "Здравствуйте! 👋\nЧтобы оформить заявку, заполните короткую форму — это займёт меньше минуты.",
                reply_markup=user_menu()
            )
            bot.send_message(
                message.chat.id,
                "Нажмите кнопку ниже:",
                reply_markup=webapp_keyboard()
            )
        except Exception as e:
            logger.error(f"Ошибка в /start: {e}")

    # =========================
    # HISTORY
    # =========================
    @bot.message_handler(commands=["history"])
    def history(message):
        if message.from_user.id in OPERATOR_IDS:
            return
        _send_history(bot, message.chat.id, message.from_user.id)

    @bot.message_handler(func=lambda message: (message.text or "") == "📋 Мои заявки" and message.from_user.id not in OPERATOR_IDS)
    def btn_history(message):
        _send_history(bot, message.chat.id, message.from_user.id)

    # =========================
    # NEW REQUEST -> открыть Mini App
    # =========================
    @bot.message_handler(func=lambda message: (message.text or "") == "📝 Новая заявка" and message.from_user.id not in OPERATOR_IDS)
    def btn_new_request(message):
        bot.send_message(
            message.chat.id,
            "Заполните форму заявки:",
            reply_markup=webapp_keyboard()
        )

    # =========================
    # CHAT: USER → OPERATOR
    # =========================
    @bot.message_handler(func=lambda message: message.from_user.id not in OPERATOR_IDS and not (message.text or "").startswith("/"))
    def user_message(message):
        chat = get_chat_by_user(message.chat.id)

        if not chat:
            return

        request_id, operator_id = chat

        try:
            if message.photo:
                bot.send_photo(operator_id, message.photo[-1].file_id,
                            caption=f"💬 Пользователь (заявка #{request_id}):" + (message.caption or ""))
            elif message.document:
                bot.send_document(operator_id, message.document.file_id,
                                caption=f"💬 Пользователь (заявка #{request_id}):" + (message.caption or ""))
            else:
                bot.send_message(operator_id, f"💬 Пользователь (заявка #{request_id}):\n{message.text}")
        except Exception as e:
            logger.error(f"Ошибка пересылки сообщения оператору {operator_id}: {e}")


def _send_history(bot, chat_id, user_id):
    rows = get_user_history(user_id)

    if not rows:
        bot.send_message(chat_id, "У вас пока нет заявок.")
        return

    text = "📋 Ваши последние заявки:\n\n"
    for row in rows:
        request_id, restaurant, status, operator_name, rating = row
        text += f"📌 Заявка #{request_id}\n"
        text += f"🏪 Ресторан: {restaurant}\n"
        text += f"📊 Статус: {status}\n"
        if operator_name:
            text += f"👨‍💼 Оператор: {operator_name}\n"
        if rating:
            text += f"⭐ Оценка: {rating}\n"
        text += "\n"

    bot.send_message(chat_id, text)
