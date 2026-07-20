import logging

from apscheduler.schedulers.background import BackgroundScheduler

from config import OPERATOR_IDS
from database import get_unclaimed_requests, bump_reminder, log_event

logger = logging.getLogger(__name__)


def _threshold_for(reminder_count):
    """
    Через сколько минут после создания заявки должно быть отправлено
    напоминание номер (reminder_count + 1):
      0 -> 15 мин
      1 -> 30 мин
      2+ -> +60 мин к предыдущему порогу (30, 90, 150, 210...)
    """
    if reminder_count == 0:
        return 15
    if reminder_count == 1:
        return 30
    return 30 + 60 * (reminder_count - 1)


def check_reminders(bot):
    try:
        rows = get_unclaimed_requests()
    except Exception as e:
        logger.error(f"Ошибка чтения непринятых заявок для напоминаний: {e}")
        return

    for request_id, restaurant, reminder_count, elapsed_min in rows:
        threshold = _threshold_for(reminder_count)

        if elapsed_min < threshold:
            continue

        text = (
            f"⏰ Заявка #{request_id} ({restaurant}) до сих пор не взята в работу!\n"
            f"Прошло уже {int(elapsed_min)} мин."
        )

        for op_id in OPERATOR_IDS:
            try:
                bot.send_message(op_id, text)
            except Exception as e:
                logger.error(f"Ошибка отправки напоминания оператору {op_id}: {e}")

        bump_reminder(request_id)
        log_event(
            request_id, "reminder", None,
            f"{int(elapsed_min)} мин, напоминание #{reminder_count + 1}"
        )
        logger.info(f"Напоминание #{reminder_count + 1} по заявке #{request_id} отправлено")


def start_scheduler(bot):
    scheduler = BackgroundScheduler()
    scheduler.add_job(lambda: check_reminders(bot), "interval", minutes=1, id="reminders_job")
    scheduler.start()
    logger.info("Планировщик напоминаний запущен (проверка раз в минуту)")
    return scheduler
