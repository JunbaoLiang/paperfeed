"""POST /feedback — single event or batch (spec §7)."""

from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from packages.core.models import Feedback
from services.api.app.deps import DbSession
from services.api.app.schemas import FeedbackAck, FeedbackIn

router = APIRouter()


@router.post("/feedback", response_model=FeedbackAck)
def post_feedback(payload: FeedbackIn | list[FeedbackIn], session: Session = DbSession):
    items = payload if isinstance(payload, list) else [payload]
    if not items:
        return FeedbackAck(count=0)
    for item in items:
        session.add(
            Feedback(
                impression_id=item.impression_id,
                event_type=item.event_type,
                value=item.value,
            )
        )
    try:
        session.flush()
    except IntegrityError as e:
        raise HTTPException(status_code=400, detail="unknown impression_id") from e
    return FeedbackAck(count=len(items))
