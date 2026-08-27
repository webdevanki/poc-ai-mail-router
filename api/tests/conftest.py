from app.config import settings

MAILHOG_API_URL = f"http://{settings.smtp_host}:8025/api"
