import logging
from telebot import types

from keyboards import phone_keyboard
from database import add_user, create_request
from config import OPERATOR_IDS
from handlers.operator_handlers import send_to_operator

logger = logging.getLogger(__name__)

user_data = {}


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
            bot.send_message(message.chat.id, "Введите ваше имя")
            bot.register_next_step_handler(message, lambda msg: get_name(msg, bot))
        except Exception as e:
            logger.error(f"Ошибка в /start: {e}")

    # =========================
    # HISTORY
    # =========================
    @bot.message_handler(commands=["history"])
    def history(message):
        if message.from_user.id in OPERATOR_IDS:
            return

        from database import get_user_history
        rows = get_user_history(message.from_user.id)

        if not rows:
            bot.send_message(message.chat.id, "У вас пока нет заявок.")
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

        bot.send_message(message.chat.id, text)

    # =========================
    # NAME
    # =========================
    def get_name(message, bot):
        user_data[message.chat.id] = {"name": message.text}
        bot.send_message(
            message.chat.id,
            "Отправьте номер телефона",
            reply_markup=phone_keyboard()
        )
        bot.register_next_step_handler(message, lambda msg: get_phone(msg, bot))

    # =========================
    # PHONE
    # =========================
    def get_phone(message, bot):
        if not message.contact:
            bot.send_message(message.chat.id, "Нужно отправить контакт кнопкой")
            bot.register_next_step_handler(message, lambda msg: get_phone(msg, bot))
            return

        user_data[message.chat.id]["phone"] = message.contact.phone_number

        add_user(
            message.from_user.id,
            user_data[message.chat.id]["name"],
            message.contact.phone_number
        )

        bot.send_message(
            message.chat.id,
            "Введите название ресторана",
            reply_markup=types.ReplyKeyboardRemove()
        )
        bot.register_next_step_handler(message, lambda msg: get_restaurant(msg, bot))

    # =========================
    # RESTAURANT
    # =========================
    def get_restaurant(message, bot):
        user_data[message.chat.id]["restaurant"] = message.text
        bot.send_message(message.chat.id, "Опишите проблему")
        bot.register_next_step_handler(message, lambda msg: get_request_text(msg, bot))

    # =========================
    # REQUEST TEXT
    # =========================
    def get_request_text(message, bot):
        user_data[message.chat.id]["request_text"] = message.text

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("Пропустить")

        bot.send_message(
            message.chat.id,
            "Прикрепите фото или нажмите Пропустить",
            reply_markup=markup
        )
        bot.register_next_step_handler(message, lambda msg: get_photo(msg, bot))

    # =========================
    # PHOTO + SEND TO OPERATOR
    # =========================
    def get_photo(message, bot):
        photo_id = None
        if message.photo:
            photo_id = message.photo[-1].file_id

        data = user_data.get(message.chat.id)
        if not data:
            bot.send_message(message.chat.id, "Ошибка данных, начните заново /start")
            return

        request_id = create_request(
            message.from_user.id,
            data["restaurant"],
            data["request_text"],
            photo_id
        )

        text = f"""📌 Новая заявка #{request_id}

        👤 Имя: {data["name"]}
        📞 Телефон: {data["phone"]}
        🏪 Ресторан: {data["restaurant"]}
        
        📝 Описание:
        {data["request_text"]}"""

        send_to_operator(bot, request_id, text, photo_id)

        from keyboards import user_menu
        bot.send_message(
            message.chat.id,
            "Заявка отправлена ✅",
            reply_markup=user_menu()
        )

        user_data.pop(message.chat.id, None)
        logger.info(f"Новая заявка #{request_id} от пользователя {message.from_user.id}")

    # =========================
    # КНОПКИ МЕНЮ
    # =========================
    @bot.message_handler(func=lambda message: (message.text or "") == "📋 Мои заявки" and message.from_user.id not in OPERATOR_IDS)
    def btn_history(message):
        from database import get_user_history
        rows = get_user_history(message.from_user.id)
        if not rows:
            bot.send_message(message.chat.id, "У вас пока нет заявок.")
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
        bot.send_message(message.chat.id, text)

    @bot.message_handler(func=lambda message: (message.text or "") == "📝 Новая заявка" and message.from_user.id not in OPERATOR_IDS)
    def btn_new_request(message):
        bot.send_message(message.chat.id, "Введите ваше имя")
        bot.register_next_step_handler(message, lambda msg: get_name(msg, bot))

    # =========================
    # CHAT: USER → OPERATOR
    # =========================
    @bot.message_handler(func=lambda message: message.from_user.id not in OPERATOR_IDS and not (message.text or "").startswith("/"))
    def user_message(message):
        from database import get_chat_by_user
        chat = get_chat_by_user(message.chat.id)

        if not chat:
            return

        request_id = chat[0]
        operator_id = chat[1]

        try:
            bot.send_message(
                operator_id,
                f"💬 Пользователь (заявка #{request_id}):\n{message.text}"
            )
        except Exception as e:
            logger.error(f"Ошибка пересылки сообщения оператору {operator_id}: {e}")