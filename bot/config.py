import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_CHAT_ID = int(os.environ["ADMIN_CHAT_ID"])
NOTIFY_SECRET = os.environ["NOTIFY_SECRET"]
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8080"))
SITE_URL = os.getenv("SITE_URL", "").rstrip("/")
CALC_URL = os.getenv("CALC_URL") or SITE_URL
DOCS_URL = os.getenv("DOCS_URL") or f"{SITE_URL}/dokumenty/"
WHATSAPP_URL = os.getenv("WHATSAPP_URL", "")
