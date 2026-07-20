import logging
from config import ADMIN_IDS

logger = logging.getLogger(__name__)


def register_admin_handlers(bot):

    # =========================
    # /admin — главное меню
    # =========================
    @bot.message_handler(commands=["admin"])
    def admin_menu(message):
        if message.from_user.id not in ADMIN_IDS:
            return

        from telebot.types import ReplyKeyboardMarkup, KeyboardButton
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(KeyboardButton("🗂 Доска заявок"))

        bot.send_message(
            message.chat.id,
            "👑 Панель администратора\n\nСтатистика, экспорт в Excel и все заявки — на доске.",
            reply_markup=markup
        )
