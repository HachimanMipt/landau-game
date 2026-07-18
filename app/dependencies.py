from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import BASE_DIR, get_settings
from app.database import get_db_session

templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


def build_static_asset_url(request: Request, path: str) -> str:
    static_path = BASE_DIR / "app" / "static" / Path(path)
    version = static_path.stat().st_mtime_ns if static_path.exists() else 0
    return f"{request.url_for('static', path=path)}?v={version}"


def get_db() -> Generator[Session, None, None]:
    yield from get_db_session()


def build_template_context(request: Request, **kwargs: object) -> dict[str, object]:
    return {
        "request": request,
        "settings": get_settings(),
        "asset_url": lambda path: build_static_asset_url(request, path),
        **kwargs,
    }
