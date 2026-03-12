"""Command line entry point."""

from __future__ import annotations

import logging

from .app import PushToTalkApp
from .config import AppConfig, ConfigError


def configure_logging() -> None:
    """Set up simple console logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


def main() -> int:
    """Run the application."""
    configure_logging()

    try:
        config = AppConfig.from_env()
    except ConfigError as exc:
        logging.error("%s", exc)
        return 1

    app = PushToTalkApp(config)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
