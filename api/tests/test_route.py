import asyncio

import httpx
import pytest
from httpx import ASGITransport

from app.main import app
from app.schemas import TargetDepartment
from conftest import MAILHOG_API_URL


@pytest.mark.asyncio
async def test_route_endpoint_hardware_problem_sends_email_via_mailhog():
    payload = {
        "email": "anna.kowalska@example.com",
        "message": "Drukarka w biurze jest zepsuta, nie dziala i wyswietla blad przy kazdej probie druku.",
    }

    async with httpx.AsyncClient() as mailhog_client:
        await mailhog_client.delete(f"{MAILHOG_API_URL}/v1/messages")

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/route", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["target_email"] == TargetDepartment.IT.value

    async with httpx.AsyncClient() as mailhog_client:
        mh_response = await mailhog_client.get(f"{MAILHOG_API_URL}/v2/messages")
    mh_response.raise_for_status()
    messages = mh_response.json()["items"]

    assert len(messages) == 1
    headers = messages[0]["Content"]["Headers"]
    assert headers["To"] == [TargetDepartment.IT.value]
    assert headers["Reply-To"] == [payload["email"]]


@pytest.mark.asyncio
async def test_route_endpoint_rejects_invalid_email():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/route",
            json={"email": "to-nie-jest-mail", "message": "test"},
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_route_endpoint_handles_concurrent_requests_independently():
    payload_it = {
        "email": "it.zgloszenie@example.com",
        "message": "Moj laptop sluzbowy w ogole sie nie wlacza, ekran jest czarny.",
    }
    payload_kadry = {
        "email": "kadry.zgloszenie@example.com",
        "message": "Chcialbym zlozyc wniosek o urlop wypoczynkowy od jutra.",
    }

    async with httpx.AsyncClient() as mailhog_client:
        await mailhog_client.delete(f"{MAILHOG_API_URL}/v1/messages")

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response_it, response_kadry = await asyncio.gather(
            client.post("/api/v1/route", json=payload_it),
            client.post("/api/v1/route", json=payload_kadry),
        )

    assert response_it.status_code == 200
    assert response_kadry.status_code == 200

    body_it = response_it.json()
    body_kadry = response_kadry.json()

    assert body_it["target_email"] == TargetDepartment.IT.value
    assert body_kadry["target_email"] == TargetDepartment.KADRY.value

    async with httpx.AsyncClient() as mailhog_client:
        mh_response = await mailhog_client.get(f"{MAILHOG_API_URL}/v2/messages")
    mh_response.raise_for_status()
    messages = mh_response.json()["items"]

    assert len(messages) == 2

    reply_to_addresses = {msg["Content"]["Headers"]["Reply-To"][0] for msg in messages}
    assert reply_to_addresses == {payload_it["email"], payload_kadry["email"]}

    for msg in messages:
        reply_to = msg["Content"]["Headers"]["Reply-To"][0]
        to = msg["Content"]["Headers"]["To"][0]
        if reply_to == payload_it["email"]:
            assert to == TargetDepartment.IT.value
        else:
            assert to == TargetDepartment.KADRY.value
