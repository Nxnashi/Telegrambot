import os
from pathlib import Path
from dotenv import load_dotenv

# Локально грузим .env, на Koyeb переменные уже в окружении
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

# =========================
# BOT
# =========================
TOKEN = os.getenv("BOT_TOKEN")

# =========================
# WEBHOOK
# =========================
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# =========================
# OPERATORS
# =========================
OPERATOR_IDS = [
    int(x)
    for x in os.getenv("OPERATOR_IDS", "").split(",")
    if x.strip()
]

# =========================
# ADMINS
# =========================
ADMIN_IDS = [
    int(x)
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip()
]

# =========================
# MINI APP (Telegram Web App)
# =========================
WEBAPP_URL = os.getenv("WEBAPP_URL")
