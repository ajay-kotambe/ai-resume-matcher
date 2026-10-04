"""Convenience launcher:  python run.py

Equivalent to `uvicorn app.main:app --reload` but reads host/port from .env.
"""

import uvicorn

from app.core.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD,
    )
