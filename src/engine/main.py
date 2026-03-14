"""Bisimulator: behavioral distillation engine."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

import anthropic
from fastapi import FastAPI

from engine.config import Settings
from engine.db import DB
from engine.pipeline.collector import Frame, poll_native_capture, poll_screenpipe
from engine.pipeline.episode import process_window
from engine.pipeline.filter import WindowAccumulator

LOG_LEVEL = os.environ.get("LOG_LEVEL", "DEBUG").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.DEBUG),
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("bisimulator")


async def pipeline_loop(
    settings: Settings,
    client: anthropic.AsyncAnthropic,
    db: DB,
):
    """
    Main pipeline: collectors → noise filter → time window → Haiku.

    All collectors push into the same queue.
    WindowAccumulator merges signals from all sources by time,
    then Haiku sees the full picture (screen + tools + whatever else)
    when identifying tasks.
    """
    frame_queue: asyncio.Queue[list[Frame]] = asyncio.Queue()
    accumulator = WindowAccumulator(
        window_minutes=30,
        idle_threshold_seconds=settings.idle_threshold_seconds,
    )

    # Start all collectors — each pushes to the same queue.
    # Both collectors gracefully wait if their DB doesn't exist.
    collectors = [
        asyncio.create_task(
            poll_native_capture(
                db=db,
                capture_db_path=settings.capture_db_path,
                interval=settings.poll_interval_seconds,
                on_frames=frame_queue,
            )
        ),
        asyncio.create_task(
            poll_screenpipe(
                db=db,
                screenpipe_db_path=settings.screenpipe_db_path,
                interval=settings.poll_interval_seconds,
                on_frames=frame_queue,
            )
        ),
    ]

    logger.debug("pipeline loop started with %d collectors", len(collectors))

    try:
        while True:
            frames = await frame_queue.get()
            logger.debug("pipeline received %d frames from collector", len(frames))
            completed_windows = accumulator.feed(frames)

            for window_frames in completed_windows:
                logger.info(
                    "window complete: %d frames, sending to haiku",
                    len(window_frames),
                )
                await process_window(client, db, window_frames)
    except asyncio.CancelledError:
        logger.info("pipeline loop cancelled, flushing remaining buffer")
        remaining = accumulator.flush()
        if remaining:
            logger.info("flushing %d remaining frames to haiku", len(remaining))
            await process_window(client, db, remaining)
        for task in collectors:
            task.cancel()
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    db = DB(settings.db_path)
    await db.connect()

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    app.state.db = db
    app.state.anthropic = client
    app.state.settings = settings

    pipeline_task = asyncio.create_task(pipeline_loop(settings, client, db))

    logger.info(
        "Bisimulator started — polling %s every %ds, window=30min",
        settings.screenpipe_db_path,
        settings.poll_interval_seconds,
    )

    yield

    pipeline_task.cancel()
    try:
        await pipeline_task
    except asyncio.CancelledError:
        pass
    await db.close()
    logger.info("Bisimulator stopped")


app = FastAPI(title="Bisimulator", lifespan=lifespan)

from engine.api.routes import router  # noqa: E402

app.include_router(router)
