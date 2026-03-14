"""Bisimulator: behavioral distillation engine.

API server (FastAPI) + Huey task queue consumer in background thread.
"""

import logging
import os
import threading
from contextlib import asynccontextmanager

import anthropic
from fastapi import FastAPI

from engine.config import Settings
from engine.db import DB

LOG_LEVEL = os.environ.get("LOG_LEVEL", "DEBUG").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.DEBUG),
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("bisimulator")


def _start_huey_consumer():
    """Start Huey consumer in a daemon thread (no signal handler conflicts)."""
    from huey.consumer import Consumer
    from engine.tasks import huey

    class EmbeddedConsumer(Consumer):
        def _install_signal_handlers(self):
            pass  # Skip — uvicorn handles signals

    consumer = EmbeddedConsumer(huey, workers=2, periodic=True)
    thread = threading.Thread(target=consumer.run, daemon=True, name="huey")
    thread.start()
    logger.info("Huey consumer started in background thread")
    return consumer


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    db = DB(settings.db_path)
    await db.connect()

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    app.state.db = db
    app.state.anthropic = client
    app.state.settings = settings

    _start_huey_consumer()

    logger.info("Bisimulator started — Huey handles pipeline scheduling")

    yield

    # Huey consumer thread is daemon, exits with process
    await db.close()
    logger.info("Bisimulator stopped")


app = FastAPI(title="Bisimulator", lifespan=lifespan)

from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from engine.api.routes import router  # noqa: E402

app.include_router(router)
