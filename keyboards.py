from telebot import types

from telebot.types import (
    ReplyKeyboardMarkup,
    KeyboardButton
)


def phone_keyboard():

    keyboard = ReplyKeyboardMarkup(
        resize_keyboard=True,
        one_time_keyboard=True
    )

    button = KeyboardButton(
        "Отправить номер",
        request_contact=True
    )

    keyboard.add(button)

    return keyboard

def operator_keyboard(request_id):

    markup = types.InlineKeyboardMarkup()

    markup.add(
        types.InlineKeyboardButton(
            "🔄 В процесс",
            callback_data=f"process_{request_id}"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "✔️ Выполнено",
            callback_data=f"done_{request_id}"
        )
    )

    return markup

def user_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("📋 Мои заявки"))
    markup.add(KeyboardButton("📝 Новая заявка"))
    return markup

def operator_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("🗂 Доска заявок"))
    return markup

def admin_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("🗂 Доска заявок"))
    return markup
