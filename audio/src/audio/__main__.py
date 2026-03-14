"""Entry point: python -m audio"""

import logging
import signal
import sys

from audio.config import DB_PATH, LOG_LEVEL
from audio.daemon import run
from audio.db import AudioDB
from audio.recorder import AudioRecorder

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.DEBUG),
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("audio")


def main():
    db = AudioDB(DB_PATH)
    db.connect()

    recorder = AudioRecorder()

    def shutdown(sig, frame):
        logger.info("shutting down (signal %d)", sig)
        recorder.stop()
        db.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        run(db, recorder)
    except KeyboardInterrupt:
        logger.info("interrupted")
    finally:
        recorder.stop()
        db.close()


if __name__ == "__main__":
    main()
