"""RankWise backend application factory."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from flask import Flask

from .api import api_blueprint, register_error_handlers
from .config import Settings
from .container import ServiceContainer, build_default_container


def create_app(
    config_overrides: dict[str, Any] | None = None,
    services: ServiceContainer | None = None,
) -> Flask:
    backend_dir = Path(__file__).resolve().parents[1]
    load_dotenv(backend_dir / ".env")
    settings = Settings.from_environment(backend_dir)

    app = Flask(
        __name__,
        static_folder=str(backend_dir / "build"),
        # Keep Flask's implicit static route away from Vite's /assets output.
        # The SPA catch-all serves files relative to the build directory.
        static_url_path="/_static",
    )
    app.config.update(
        MAX_CONTENT_LENGTH=settings.max_upload_bytes,
        SETTINGS=settings,
        TESTING=False,
    )
    if config_overrides:
        app.config.update(config_overrides)

    app.extensions["rankwise_services"] = services or build_default_container(settings)
    app.register_blueprint(api_blueprint)
    register_error_handlers(app)
    return app


__all__ = ["create_app"]
