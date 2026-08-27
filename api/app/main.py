from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from loguru import logger

from app.logging_config import setup_logging
from app.routers import v1

setup_logging()

app = FastAPI(
    title="AI Mail Router",
    docs_url="/api/v1/docs",
    openapi_url="/api/v1/openapi.json",
)
app.include_router(v1.router)

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/health")
async def health() -> dict:
    logger.info("Health check OK")
    return {"status": "ok"}


@app.get("/panel")
async def panel() -> FileResponse:
    return FileResponse(STATIC_DIR / "panel.html")
