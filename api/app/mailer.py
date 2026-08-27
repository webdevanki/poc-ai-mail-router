from email.message import EmailMessage

import aiosmtplib
from loguru import logger

from app.config import settings


async def send_email(to: str, reply_to: str, subject: str, body: str) -> None:
    """Wysyła e-mail asynchronicznie przez SMTP (MailHog), nie blokując event loopa FastAPI."""

    safe_subject = subject.replace("\r", " ").replace("\n", " ")

    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = to
    message["Reply-To"] = reply_to
    message["Subject"] = safe_subject
    message.set_content(body)

    await aiosmtplib.send(
        message,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        timeout=settings.smtp_timeout,
    )

    logger.info("Email sent to={} reply_to={} subject={}", to, reply_to, safe_subject)
