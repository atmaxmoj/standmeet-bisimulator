"""Audio capture daemon: record → chunk → transcribe → write to DB."""

import logging
import os
import threading
import time

from audio.db import AudioDB
from audio.recorder import AudioRecorder
from audio.transcriber import transcribe

logger = logging.getLogger(__name__)


def run(db: AudioDB, recorder: AudioRecorder, keep_chunks: bool = False):
    """
    Main daemon loop:
    1. Recorder runs in background, producing WAV chunks every N minutes
    2. When a chunk is ready, transcribe it with whisper
    3. Write transcription segments to DB as audio_frames
    4. Optionally delete the WAV chunk to save disk space
    """
    pending_chunks: list[tuple[str, str, float]] = []  # (path, timestamp, duration)
    lock = threading.Lock()

    def on_chunk_ready(chunk_path: str, start_timestamp: str, duration: float):
        """Called from recorder thread when a chunk is complete."""
        logger.debug(
            "chunk ready: %s (started=%s, duration=%.1fs)",
            chunk_path, start_timestamp, duration,
        )
        with lock:
            pending_chunks.append((chunk_path, start_timestamp, duration))

    # Start recording in a background thread
    record_thread = threading.Thread(
        target=recorder.record,
        args=(on_chunk_ready,),
        daemon=True,
    )
    record_thread.start()
    logger.info("recorder thread started")

    # Main loop: process pending chunks
    while True:
        try:
            # Grab pending chunks
            with lock:
                to_process = list(pending_chunks)
                pending_chunks.clear()

            for chunk_path, start_timestamp, duration in to_process:
                logger.info("processing chunk: %s", chunk_path)

                try:
                    result = transcribe(chunk_path)
                except Exception:
                    logger.exception("transcription failed for %s", chunk_path)
                    continue

                text = result["text"]
                language = result["language"]

                if not text.strip():
                    logger.debug("empty transcription for %s, skipping DB write", chunk_path)
                else:
                    db.insert_audio_frame(
                        timestamp=start_timestamp,
                        duration_seconds=duration,
                        text=text,
                        language=language,
                        chunk_path=chunk_path if keep_chunks else "",
                    )

                # Clean up chunk file
                if not keep_chunks:
                    try:
                        os.remove(chunk_path)
                        logger.debug("deleted chunk: %s", chunk_path)
                    except OSError:
                        logger.warning("failed to delete chunk: %s", chunk_path)

        except Exception:
            logger.exception("error in audio daemon main loop")

        time.sleep(2)
