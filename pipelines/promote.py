"""Interleaving online judgment (spec §9.3), run as the last weekly step.

SPEC-GAP: the spec doesn't name a module for this ("判定由 weekly workflow
末尾一步自动执行"); it lives here as its own entry point.

Rule: once interleaved clicks ≥200 OR the staging model is ≥14 days old —
challenger click share >52% → promote to production (old production archived);
otherwise archive the challenger. Interleaving is switched off either way.
"""

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select

from packages.core.db import session_scope
from packages.core.logging import get_logger, log_event
from packages.core.models import Feedback, Impression, ModelRegistry, UserProfile

CLICK_EVENTS = ("click_abstract", "click_pdf")
MIN_CLICKS = 200
MAX_DAYS = 14
WIN_SHARE = 0.52
REPORT_PATH = "data/interleave_report.md"

logger = get_logger("pipelines.promote")


def judge(total_clicks: int, challenger_clicks: int, staging_age_days: float) -> str:
    """Returns 'promote' | 'archive' | 'wait'."""
    if total_clicks < MIN_CLICKS and staging_age_days < MAX_DAYS:
        return "wait"
    if total_clicks == 0:
        return "archive"
    share = challenger_clicks / total_clicks
    return "promote" if share > WIN_SHARE else "archive"


def write_report(path: str, **fields) -> None:
    lines = ["# Interleaving judgment report", ""]
    lines += [f"- **{k}**: {v}" for k, v in fields.items()]
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines) + "\n")


def main() -> int:
    now = datetime.now(UTC)
    with session_scope() as session:
        staging = session.scalars(
            select(ModelRegistry)
            .where(ModelRegistry.status == "staging")
            .order_by(ModelRegistry.created_at.desc())
        ).first()
        if staging is None:
            log_event(logger, "promote_skipped", reason="no_staging_model")
            return 0

        since = staging.created_at or (now - timedelta(days=MAX_DAYS))
        rows = session.execute(
            select(Impression.interleave_arm, func.count(func.distinct(Feedback.impression_id)))
            .join(Feedback, Feedback.impression_id == Impression.impression_id)
            .where(
                Impression.interleave_arm.is_not(None),
                Impression.shown_at >= since,
                Feedback.event_type.in_(CLICK_EVENTS),
            )
            .group_by(Impression.interleave_arm)
        ).all()
        clicks = {arm: int(cnt) for arm, cnt in rows}
        challenger_clicks = clicks.get("challenger", 0)
        total_clicks = challenger_clicks + clicks.get("prod", 0)
        age_days = (now - since).total_seconds() / 86400.0

        verdict = judge(total_clicks, challenger_clicks, age_days)
        share = (challenger_clicks / total_clicks) if total_clicks else None

        if verdict == "promote":
            for row in session.scalars(
                select(ModelRegistry).where(ModelRegistry.status == "production")
            ):
                row.status = "archived"
            staging.status = "production"
        elif verdict == "archive":
            staging.status = "archived"

        if verdict != "wait":
            profile = session.get(UserProfile, "default")
            if profile is not None:
                profile.config = {**(profile.config or {}), "interleaving_enabled": False}

        report = {
            "verdict": verdict,
            "staging_version": staging.version,
            "total_clicks": total_clicks,
            "challenger_clicks": challenger_clicks,
            "challenger_share": f"{share:.3f}" if share is not None else "n/a",
            "staging_age_days": f"{age_days:.1f}",
            "judged_at": now.isoformat(),
        }
        write_report(REPORT_PATH, **report)
        log_event(logger, "promote_done", **report)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        logger.exception("promote_failed")
        sys.exit(1)
