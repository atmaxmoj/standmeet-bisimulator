"""Main capture loop: screenshot → hash → OCR if changed → write to DB.
Also collects OS events (shell commands, browser URLs)."""

import logging
import time
from datetime import datetime, timezone

from capture.backends import (
    capture_display,
    get_all_displays,
    get_frontmost_app,
    hash_image,
    ocr_image,
)
from capture.collectors import get_all_collectors
from capture.config import CAPTURE_INTERVAL
from capture.db import CaptureDB

logger = logging.getLogger(__name__)


def run(db: CaptureDB):
    """Main capture loop. Runs forever until interrupted."""
    last_hashes: dict[int, str] = {}

    # Initialize last_hashes from DB
    for display_id in get_all_displays():
        saved_hash = db.get_last_hash(display_id)
        if saved_hash:
            last_hashes[display_id] = saved_hash
            logger.debug("loaded last hash for display %d: %s", display_id, saved_hash[:12])

    # Initialize OS event collectors
    collectors = []
    for c in get_all_collectors():
        if c.available():
            collectors.append(c)
            logger.info("collector enabled: %s/%s", c.event_type, c.source)
        else:
            logger.debug("collector skipped (not available): %s/%s", c.event_type, c.source)

    logger.info(
        "capture daemon started: interval=%ds, displays=%d, collectors=%d",
        CAPTURE_INTERVAL,
        len(last_hashes) or len(get_all_displays()),
        len(collectors),
    )

    while True:
        try:
            cycle_start = time.monotonic()
            displays = get_all_displays()
            app_name, window_name = get_frontmost_app()
            timestamp = datetime.now(timezone.utc).isoformat()

            captured = 0
            skipped = 0

            for display_id in displays:
                image = capture_display(display_id)
                if image is None:
                    continue

                current_hash = hash_image(image)
                if current_hash == last_hashes.get(display_id):
                    skipped += 1
                    logger.debug("display %d unchanged, skipping OCR", display_id)
                    continue

                text = ocr_image(image)
                db.insert_frame(
                    timestamp=timestamp,
                    app_name=app_name,
                    window_name=window_name,
                    text=text,
                    display_id=display_id,
                    image_hash=current_hash,
                )
                last_hashes[display_id] = current_hash
                captured += 1

            # Collect OS events
            os_events = 0
            for collector in collectors:
                try:
                    entries = collector.collect()
                    for data in entries:
                        db.insert_os_event(
                            timestamp=timestamp,
                            event_type=collector.event_type,
                            source=collector.source,
                            data=data,
                        )
                        os_events += 1
                except Exception:
                    logger.exception("collector %s/%s failed", collector.event_type, collector.source)

            elapsed = time.monotonic() - cycle_start
            logger.debug(
                "cycle: captured=%d skipped=%d os_events=%d elapsed=%.1fms",
                captured, skipped, os_events, elapsed * 1000,
            )

        except Exception:
            logger.exception("error in capture cycle")

        time.sleep(CAPTURE_INTERVAL)
