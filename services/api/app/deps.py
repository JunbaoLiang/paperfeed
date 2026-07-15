"""FastAPI dependencies: bearer auth (spec A11) and per-request DB session."""

from collections.abc import Iterator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from packages.core.config import get_settings
from packages.core.db import get_session_factory


def require_auth(request: Request) -> None:
    expected = f"Bearer {get_settings().api_token}"
    if request.headers.get("Authorization") != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")


def get_db() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


DbSession = Depends(get_db)
AuthDep = Depends(require_auth)
