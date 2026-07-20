"""Daily metrics rollup (spec §6.6): aggregates yesterday's impressions and
feedback into metrics_daily; drift = 1 − cos(profile today, profile 30d ago).
"""

import sys
from datetime import UTC, date, datetime, time, timedelta

import numpy as np
from sqlalchemy import func, select

from packages.core.db import session_scope
from packages.core.features import cosine
from packages.core.logging import get_logger, log_event
from packages.core.models import (
    Feedback,
    Impression,
    MetricsDaily,
    ProfileHistory,
    UserProfile,
)

CLICK_EVENTS = ("click_abstract", "click_pdf")
DRIFT_LOOKBACK_DAYS = 30

logger = get_logger("pipelines.metrics_rollup")


def day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=UTC)
    return start, start + timedelta(days=1)


def _distinct_impressions_with(session, day: date, event_types: tuple[str, ...]) -> int:
    start, end = day_bounds(day)
    return int(
        session.scalar(
            select(func.count(func.distinct(Feedback.impression_id)))
            .join(Impression, Impression.impression_id == Feedback.impression_id)
            .where(
                Feedback.event_type.in_(event_types),
                Feedback.created_at >= start,
                Feedback.created_at < end,
                # external reads are not real exposures — keep CTR honest
                Impression.recall_source != "external",
            )
        )
        or 0
    )


def rollup_day(session, day: date) -> MetricsDaily:
    start, end = day_bounds(day)
    impressions = int(
        session.scalar(
            select(func.count())
            .select_from(Impression)
            .where(
                Impression.shown_at >= start,
                Impression.shown_at < end,
                Impression.recall_source != "external",
            )
        )
        or 0
    )
    # SPEC-GAP: 'clicks' = distinct impressions with a click event that day
    # (bounds CTR at 1.0); spec doesn't pin the definition.
    clicks = _distinct_impressions_with(session, day, CLICK_EVENTS)
    saves = _distinct_impressions_with(session, day, ("save",))
    dismisses = _distinct_impressions_with(session, day, ("dismiss",))
    ctr = (clicks / impressions) if impressions > 0 else None

    model_version = session.scalar(
        select(Impression.model_version)
        .where(
            Impression.shown_at >= start,
            Impression.shown_at < end,
            Impression.recall_source != "external",
        )
        .group_by(Impression.model_version)
        .order_by(func.count().desc())
        .limit(1)
    )

    profile = session.get(UserProfile, "default")
    old_snapshot = session.scalars(
        select(ProfileHistory)
        .where(ProfileHistory.day <= day - timedelta(days=DRIFT_LOOKBACK_DAYS))
        .order_by(ProfileHistory.day.desc())
        .limit(1)
    ).first()
    drift = None
    if (
        profile is not None
        and profile.embedding is not None
        and old_snapshot is not None
        and old_snapshot.embedding is not None
    ):
        sim = cosine(
            np.asarray(profile.embedding, dtype=np.float32),
            np.asarray(old_snapshot.embedding, dtype=np.float32),
        )
        drift = (1.0 - sim) if sim is not None else None

    row = session.get(MetricsDaily, day)
    if row is None:
        row = MetricsDaily(day=day)
        session.add(row)
    row.impressions = impressions
    row.clicks = clicks
    row.saves = saves
    row.dismisses = dismisses
    row.ctr = ctr
    row.profile_drift = drift
    row.model_version = model_version
    return row


def main() -> int:
    yesterday = (datetime.now(UTC) - timedelta(days=1)).date()
    with session_scope() as session:
        row = rollup_day(session, yesterday)
        log_event(
            logger,
            "rollup_done",
            day=str(yesterday),
            impressions=row.impressions,
            clicks=row.clicks,
            ctr=row.ctr,
            drift=row.profile_drift,
        )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        logger.exception("metrics_rollup_failed")
        sys.exit(1)
