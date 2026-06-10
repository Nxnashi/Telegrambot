import logging
import os
import telebot

from flask import Flask, request

from config import TOKEN, WEBHOOK_URL
from database import create_tables

from handlers.user_handlers import register_user_handlers
from handlers.operator_handlers import register_operator_handlers
from handlers.admin_handlers import register_admin_handlers

# =========================
# LOGGING
# =========================
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# =========================
# BOT
# =========================
bot = telebot.TeleBot(TOKEN)

# =========================
# FLASK
# =========================
app = Flask(__name__)

# =========================
# DATABASE
# =========================
create_tables()

# =========================
# HANDLERS
# =========================
register_user_handlers(bot)
register_operator_handlers(bot)
register_admin_handlers(bot)

# =========================
# WEBHOOK ROUTE
# =========================
@app.route("/webhook", methods=["POST"])
def webhook():
    if request.headers.get("content-type") == "application/json":
        json_string = request.get_data().decode("utf-8")
        logger.debug(f"Incoming update: {json_string[:200]}")
        try:
            update = telebot.types.Update.de_json(json_string)
            bot.process_new_updates([update])
        except Exception as e:
            logger.error(f"Ошибка обработки update: {e}")
        return "OK", 200
    return "Forbidden", 403


@app.route("/", methods=["GET"])
def index():
    return "Bot is running", 200


# =========================
# WEBHOOK SETUP
# =========================
def setup_webhook():
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    logger.info(f"Webhook установлен: {WEBHOOK_URL}")


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    setup_webhook()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
else:
    # Запуск через gunicorn
    setup_webhook()