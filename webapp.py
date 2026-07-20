import hashlib
import hmac
import json
import logging
import os
import time
from urllib.parse import parse_qsl

from flask import request, jsonify, send_from_directory

from config import TOKEN, OPERATOR_IDS
from database import add_user, create_request, get_conn, log_event

logger = logging.getLogger(__name__)

WEBAPP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "webapp")


def validate_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400):
    """
    Проверяет подпись initData, которую прислал Telegram Mini App.
    Возвращает dict с данными пользователя, если подпись верна, иначе None.

    Подробности алгоритма: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    if not init_data:
        return None

    try:
        parsed = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))

    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        logger.warning("Mini App: подпись initData не совпала")
        return None

    auth_date = int(parsed.get("auth_date", "0"))
    if max_age_seconds and (time.time() - auth_date) > max_age_seconds:
        logger.warning("Mini App: initData устарела")
        return None

    user_json = parsed.get("user")
    if not user_json:
        return None

    return json.loads(user_json)


def _send_request_to_operators(bot, request_id, text, photos):
    from keyboards import operator_keyboard

    conn = get_conn()
    cursor = conn.cursor()

    first_photo_bytes = None
    if photos:
        first_photo_bytes = photos[0].read()

    for op_id in OPERATOR_IDS:
        try:
            if first_photo_bytes:
                msg = bot.send_photo(
                    op_id, first_photo_bytes, caption=text,
                    reply_markup=operator_keyboard(request_id)
                )
            else:
                msg = bot.send_message(op_id, text, reply_markup=operator_keyboard(request_id))

            cursor.execute(
                "INSERT INTO operator_messages (request_id, operator_id, message_id) VALUES (?, ?, ?)",
                (request_id, op_id, msg.message_id)
            )
        except Exception as e:
            logger.error(f"Ошибка отправки заявки (Mini App) оператору {op_id}: {e}")

    conn.commit()

    # Если фото было больше одного — остальные шлём отдельными сообщениями
    if len(photos) > 1:
        for extra in photos[1:]:
            data = extra.read()
            for op_id in OPERATOR_IDS:
                try:
                    bot.send_photo(op_id, data, caption=f"📎 Доп. фото к заявке #{request_id}")
                except Exception as e:
                    logger.error(f"Ошибка отправки доп. фото оператору {op_id}: {e}")


def register_webapp(app, bot):

    @app.route("/webapp/")
    @app.route("/webapp")
    def webapp_index():
        return send_from_directory(WEBAPP_DIR, "index.html")

    @app.route("/webapp/<path:filename>")
    def webapp_static(filename):
        return send_from_directory(WEBAPP_DIR, filename)

    @app.route("/api/create_request", methods=["POST"])
    def api_create_request():
        init_data = request.form.get("initData", "")
        user = validate_init_data(init_data, TOKEN)

        if not user:
            return jsonify(ok=False, error="invalid_init_data"), 403

        user_id = user.get("id")
        name = (request.form.get("name") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        restaurant = (request.form.get("restaurant") or "").strip()
        description = (request.form.get("description") or "").strip()
        photos = request.files.getlist("photos")

        if not all([name, phone, restaurant, description]):
            return jsonify(ok=False, error="missing_fields"), 400

        add_user(user_id, name, phone)
        request_id = create_request(user_id, restaurant, description, None)
        log_event(request_id, "create", name, f"{restaurant}: {description[:100]}")

        full_text = (
            f"📌 Новая заявка #{request_id} (из мини-приложения)\n\n"
            f"👤 Имя: {name}\n"
            f"📞 Телефон: {phone}\n"
            f"🏪 Ресторан: {restaurant}\n\n"
            f"📝 Описание:\n{description}"
        )

        _send_request_to_operators(bot, request_id, full_text, photos)

        logger.info(f"Новая заявка #{request_id} от пользователя {user_id} (Mini App)")

        return jsonify(ok=True, request_id=request_id)
