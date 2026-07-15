import uuid
from datetime import UTC, datetime

from pipelines.build_dataset import build_rows, label_for_events


def test_label_rules():
    assert label_for_events({"visible", "save"}, None) == 2
    assert label_for_events({"visible", "click_pdf"}, None) == 2
    assert label_for_events({"visible", "click_abstract"}, None) == 1
    assert label_for_events({"visible", "dwell"}, 25_000) == 1
    assert label_for_events({"visible", "dwell"}, 10_000) == 0
    assert label_for_events({"visible"}, None) == 0
    # no visible event -> dropped
    assert label_for_events({"click_abstract"}, None) is None
    assert label_for_events(set(), None) is None


def test_save_dominates_click():
    assert label_for_events({"visible", "click_abstract", "save"}, None) == 2


def test_build_rows_drops_unseen_and_overrides_position():
    imp_seen, imp_unseen = uuid.uuid4(), uuid.uuid4()
    req = uuid.uuid4()
    shown = datetime(2026, 7, 1, tzinfo=UTC)
    features = {"cos_profile": 0.7, "position": 5.0}  # snapshot has inference constant
    impressions = [
        (imp_seen, req, features, 3, shown, None),
        (imp_unseen, req, features, 4, shown, "prod"),
    ]
    feedback = [
        (imp_seen, "visible", None),
        (imp_seen, "dwell", 30_000.0),
        # imp_unseen has interactions but was never visible -> dropped
        (imp_unseen, "click_abstract", None),
    ]
    rows = build_rows(impressions, feedback)
    assert len(rows) == 1
    row = rows[0]
    assert row["label"] == 1
    assert row["position"] == 3.0  # real position, not the snapshot constant
    assert row["cos_profile"] == 0.7
