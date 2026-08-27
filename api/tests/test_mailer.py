import httpx
import pytest

from app.mailer import send_email
from conftest import MAILHOG_API_URL


@pytest.mark.asyncio
async def test_send_email_delivers_to_mailhog_with_reply_to():
    to_address = "it@example.com"
    reply_to_address = "jan.nowak@example.com"
    subject = "Test routing"
    body = "Nie dziala mi komputer"

    async with httpx.AsyncClient() as client:
        await client.delete(f"{MAILHOG_API_URL}/v1/messages")

        await send_email(to=to_address, reply_to=reply_to_address, subject=subject, body=body)

        response = await client.get(f"{MAILHOG_API_URL}/v2/messages")
        response.raise_for_status()
        messages = response.json()["items"]

    assert len(messages) == 1

    headers = messages[0]["Content"]["Headers"]
    assert headers["To"] == [to_address]
    assert headers["Reply-To"] == [reply_to_address]
    assert headers["Subject"] == [subject]
