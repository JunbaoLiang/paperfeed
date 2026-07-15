"""Admin endpoints (spec §7): model reload, interleaving toggle, seed profile."""

from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy.orm import Session

from packages.core.models import UserProfile
from services.api.app.deps import DbSession
from services.api.app.recsys.scoring import model_manager
from services.api.app.schemas import OkResponse, SeedProfileIn

router = APIRouter(prefix="/admin")


def _update_config(session: Session, **kv) -> None:
    profile = session.get(UserProfile, "default")
    if profile is None:
        profile = UserProfile(profile_id="default", interaction_count=0)
        session.add(profile)
    profile.config = {**(profile.config or {}), **kv}
    profile.updated_at = datetime.now(UTC)


@router.post("/reload-model")
def reload_model(session: Session = DbSession):
    versions = model_manager.reload(session)
    return {"ok": True, "loaded": versions}


@router.post("/interleave", response_model=OkResponse)
def toggle_interleave(on: bool, session: Session = DbSession):
    _update_config(session, interleaving_enabled=on)
    return OkResponse()


@router.post("/seed-profile")
def seed_profile(payload: SeedProfileIn, session: Session = DbSession):
    """Store onboarding keywords; the next daily profile_update run (offline,
    has SPECTER2) encodes them into the initial profile vector (spec §7 冷启动)."""
    keywords = [k.strip() for k in payload.keywords if k.strip()]
    _update_config(session, seed_keywords=keywords)
    return {"ok": True, "note": "个性化推荐将于明日生效"}
