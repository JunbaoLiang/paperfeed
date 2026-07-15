"""PaperFeed online API (FastAPI @ HF Spaces).

Single container, no torch (spec A4/§14): recall is pure pgvector queries
against the precomputed profile vector; scoring is rule or LightGBM inference.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from packages.core.config import get_settings
from packages.core.db import session_scope
from services.api.app.deps import AuthDep
from services.api.app.recsys.scoring import model_manager
from services.api.app.routers import admin, feed, feedback

logger = logging.getLogger("api.main")


def _reload_models() -> None:
    with session_scope() as session:
        model_manager.reload(session)


async def _registry_poll_loop() -> None:
    """Check model_registry every 10 minutes; hot-swap on version change."""
    interval = get_settings().registry_poll_seconds
    while True:
        await asyncio.sleep(interval)
        try:
            await asyncio.to_thread(_reload_models)
        except Exception:
            logger.exception("registry poll failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await asyncio.to_thread(_reload_models)
    except Exception:
        # DB may be briefly unreachable at boot; serve rule-v0 until the poll succeeds.
        logger.exception("initial model load failed; serving rule-v0 fallback")
    poll_task = asyncio.create_task(_registry_poll_loop())
    yield
    poll_task.cancel()


app = FastAPI(title="PaperFeed API", version="0.1.0", lifespan=lifespan)

app.include_router(feed.router, dependencies=[AuthDep])
app.include_router(feedback.router, dependencies=[AuthDep])
app.include_router(admin.router, dependencies=[AuthDep])


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
