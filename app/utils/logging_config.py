"""Configure concise application logging without logging document contents."""

import logging


def configure_logging() -> None:
    """Set a consistent log format for the API and services."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
