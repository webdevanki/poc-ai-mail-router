from fastapi import APIRouter, HTTPException
from loguru import logger

from app.agent import route_message
from app.schemas import RequestIn, RouteResult

router = APIRouter(prefix="/api/v1", tags=["routing"])


@router.post("/route", response_model=RouteResult)
async def route(request: RequestIn) -> RouteResult:
    try:
        return await route_message(sender_email=request.email, message=request.message)
    except Exception:
        logger.exception("Blad podczas routingu wiadomosci przez agenta AI")
        raise HTTPException(
            status_code=502,
            detail="Nie udalo sie przetworzyc zgloszenia przez agenta AI.",
        )
