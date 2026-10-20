"""Start Uvicorn using the configured API host and port."""

import uvicorn

from app.config import get_settings


def main() -> None:
    """Run the FastAPI application with validated local settings."""
    settings = get_settings()
    uvicorn.run("app.main:app", host=settings.api_host, port=settings.api_port)


if __name__ == "__main__":
    main()
