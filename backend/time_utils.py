from __future__ import annotations

from datetime import datetime

try:
    from .config import TAIPEI
except ImportError:  # pragma: no cover - supports `uvicorn app:app` from backend/.
    from config import TAIPEI


def now() -> datetime:
    return datetime.now(TAIPEI)
