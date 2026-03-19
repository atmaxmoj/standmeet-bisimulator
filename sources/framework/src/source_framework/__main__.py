"""Entry point: python -m source_framework <source_dir>

Usage:
    python -m source_framework sources/builtin/zsh
    python -m source_framework /path/to/my_source --engine-url http://host:5001
"""

import argparse
import logging
import signal
import sys

from source_framework.runner import run_source


def main():
    parser = argparse.ArgumentParser(description="Run an Observer source plugin")
    parser.add_argument("source_dir", help="Path to source directory containing manifest.json")
    parser.add_argument("--engine-url", default=None, help="Engine API URL (default: $ENGINE_URL or http://localhost:5001)")
    parser.add_argument("--log-level", default="DEBUG", help="Log level (default: DEBUG)")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.DEBUG),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    def shutdown(sig, frame):
        logging.getLogger(__name__).info("shutting down (signal %d)", sig)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    run_source(args.source_dir, engine_url=args.engine_url)


if __name__ == "__main__":
    main()
