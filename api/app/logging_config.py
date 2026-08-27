import logging
import sys

from loguru import logger

from app.config import settings


class InterceptHandler(logging.Handler):
    """Przechwytuje logi ze standardowego `logging` (np. uvicorn) i przekazuje je do loguru,
    dzięki czemu cała aplikacja ma jeden, spójny, strukturalny format logów."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame.f_back and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logging() -> None:
    logger.remove()
    logger.add(
        sys.stdout,
        level=settings.log_level,
        serialize=True,
        backtrace=False,
        diagnose=False,
    )

    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = [InterceptHandler()]
        uvicorn_logger.propagate = False
