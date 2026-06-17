import logging
from telebot import types

from keyboards import phone_keyboard
from database import add_user, create_request
from config import OPERATOR_IDS
from handlers.operator_handlers import send_to_operator

logger = logging.getLogger(__name__)

user_data = {}

# Пользователи в режиме сбора описания
collecting = {}


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

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("✅ Готово"))

        bot.send_message(
            message.chat.id,
            "Опишите проблему — отправьте текст, фото или файлы.\nКогда закончите, нажмите *✅ Готово*.",
            parse_mode="Markdown",
            reply_markup=markup
        )

        # Инициализируем сбор
        collecting[message.chat.id] = {
            "texts": [],
            "files": []  # list of (file_id, file_type)
        }

        bot.register_next_step_handler(message, lambda msg: collect_description(msg, bot))

    # =========================
    # COLLECT DESCRIPTION
    # =========================
    def collect_description(message, bot):
        chat_id = message.chat.id

        # Нажал "Готово"
        if message.text == "✅ Готово":
            _finish_request(message, bot)
            return

        data = collecting.get(chat_id)
        if data is None:
            return

        # Собираем текст
        text = message.text or message.caption or ""
        if text:
            data["texts"].append(text)

        # Собираем файлы
        if message.photo:
            data["files"].append((message.photo[-1].file_id, "photo"))
        elif message.document:
            data["files"].append((message.document.file_id, "document"))

        # Продолжаем слушать
        bot.register_next_step_handler(message, lambda msg: collect_description(msg, bot))

    # =========================
    # FINISH REQUEST
    # =========================
    def _finish_request(message, bot):
        chat_id = message.chat.id
        data = user_data.get(chat_id)
        collected = collecting.get(chat_id)

        if not data or collected is None:
            bot.send_message(chat_id, "Ошибка данных, начните заново /start")
            return

        # Собираем весь текст
        full_text = "\n".join(collected["texts"]) if collected["texts"] else "—"
        files = collected["files"]

        # Берём первый файл для БД (основной)
        photo_id = files[0][0] if files else None
        file_type = files[0][1] if files else None

        request_id = create_request(
            message.from_user.id,
            data["restaurant"],
            full_text,
            photo_id
        )

        text = f"""📌 Новая заявка #{request_id}

👤 Имя: {data["name"]}
📞 Телефон: {data["phone"]}
🏪 Ресторан: {data["restaurant"]}

📝 Описание:
{full_text}"""

        # Отправляем заявку оператору
        send_to_operator(bot, request_id, text, photo_id, file_type)

        # Если файлов больше одного — отправляем остальные отдельно
        if len(files) > 1:
            for fid, ftype in files[1:]:
                for op_id in OPERATOR_IDS:
                    try:
                        if ftype == "photo":
                            bot.send_photo(op_id, fid, caption=f"📎 Доп. файл к заявке #{request_id}")
                        else:
                            bot.send_document(op_id, fid, caption=f"📎 Доп. файл к заявке #{request_id}")
                    except Exception as e:
                        logger.error(f"Ошибка отправки доп. файла оператору {op_id}: {e}")

        from keyboards import user_menu
        bot.send_message(
            chat_id,
            "Заявка отправлена ✅",
            reply_markup=user_menu()
        )

        user_data.pop(chat_id, None)
        collecting.pop(chat_id, None)
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
        # Если пользователь в режиме сбора — не перехватываем
        if message.chat.id in collecting:
            return

        from database import get_chat_by_user
        chat = get_chat_by_user(message.chat.id)

        if not chat:
            return

        request_id = chat[0]
        operator_id = chat[1]

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