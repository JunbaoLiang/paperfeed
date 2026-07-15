"""Training sample construction (spec §9.1). Unit = impression.

Labels: save/click_pdf → 2; click_abstract or dwell≥20s → 1; visible but no
interaction → 0; impressions WITHOUT a visible event are dropped (never truly
seen). Features come verbatim from the impressions.features snapshot —
recomputation is forbidden; only `position` is replaced by the real shown
position (the snapshot holds the inference constant, spec §9.2).
"""

import argparse
import sys
from pathlib import Path

from sqlalchemy import select

from packages.core.features import FEATURE_ORDER
from packages.core.logging import get_logger, log_event

DWELL_LABEL_MS = 20_000.0
DEFAULT_OUT = "data/dataset.parquet"

logger = get_logger("pipelines.build_dataset")


def label_for_events(event_types: set[str], max_dwell_ms: float | None) -> int | None:
    """Spec §9.1 label rules; None = drop the impression."""
    if "visible" not in event_types:
        return None
    if "save" in event_types or "click_pdf" in event_types:
        return 2
    if "click_abstract" in event_types or (max_dwell_ms or 0.0) >= DWELL_LABEL_MS:
        return 1
    return 0


def build_rows(impression_rows, feedback_rows) -> list[dict]:
    """impression_rows: (impression_id, request_id, features, position, shown_at,
    interleave_arm); feedback_rows: (impression_id, event_type, value)."""
    events: dict = {}
    for impression_id, event_type, value in feedback_rows:
        agg = events.setdefault(impression_id, {"types": set(), "dwell": None})
        agg["types"].add(event_type)
        if event_type == "dwell" and value is not None:
            agg["dwell"] = max(agg["dwell"] or 0.0, float(value))

    rows = []
    for impression_id, request_id, features, position, shown_at, arm in impression_rows:
        agg = events.get(impression_id, {"types": set(), "dwell": None})
        label = label_for_events(agg["types"], agg["dwell"])
        if label is None:
            continue
        row = {name: float(features.get(name, 0.0)) for name in FEATURE_ORDER}
        row["position"] = float(position)  # real position, training-only signal
        row.update(
            label=label,
            request_id=str(request_id),
            shown_at=shown_at,
            impression_id=str(impression_id),
            interleave_arm=arm,
        )
        rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args()

    import pandas as pd

    from packages.core.db import session_scope
    from packages.core.models import Feedback, Impression

    with session_scope() as session:
        impression_rows = session.execute(
            select(
                Impression.impression_id,
                Impression.request_id,
                Impression.features,
                Impression.position,
                Impression.shown_at,
                Impression.interleave_arm,
            )
        ).all()
        feedback_rows = session.execute(
            select(Feedback.impression_id, Feedback.event_type, Feedback.value)
        ).all()

    rows = build_rows(impression_rows, feedback_rows)
    df = pd.DataFrame(rows)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    log_event(
        logger,
        "dataset_built",
        impressions=len(impression_rows),
        samples=len(df),
        positives=int((df["label"] > 0).sum()) if len(df) else 0,
        out=str(out),
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        logger.exception("build_dataset_failed")
        sys.exit(1)
