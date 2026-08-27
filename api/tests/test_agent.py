import httpx
import pytest

from app.agent import route_message
from app.schemas import TargetDepartment
from conftest import MAILHOG_API_URL


@pytest.mark.asyncio
async def test_agent_routes_it_problem_and_sends_email():
    sender_email = "jan.nowak@example.com"
    message = "Moj laptop sluzbowy w ogole nie wlacza sie od rana, ekran jest czarny mimo podlaczenia do zasilania."

    async with httpx.AsyncClient() as client:
        await client.delete(f"{MAILHOG_API_URL}/v1/messages")

        result = await route_message(sender_email=sender_email, message=message)

        response = await client.get(f"{MAILHOG_API_URL}/v2/messages")
        response.raise_for_status()
        messages = response.json()["items"]

    assert result.target_email == TargetDepartment.IT
    assert len(result.category) <= 30, f"category powinna byc krotka, otrzymano: {result.category!r}"
    assert len(messages) == 1

    headers = messages[0]["Content"]["Headers"]
    assert headers["To"] == [TargetDepartment.IT.value]
    assert headers["Reply-To"] == [sender_email]
    assert headers["Subject"] == [f"[AI Router] {result.category}"]
