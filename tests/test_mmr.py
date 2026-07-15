import numpy as np

from services.api.app.recsys.rerank import (
    ScoredItem,
    apply_explore_slot,
    mmr_rerank,
)


def item(key, score, emb, cat="cs.LG", source="vector"):
    return ScoredItem(
        key=key,
        score=score,
        embedding=np.asarray(emb, dtype=np.float64) if emb is not None else None,
        primary_category=cat,
        recall_source=source,
    )


def test_mmr_prefers_diverse_over_near_duplicate():
    # b is a near-duplicate of a with a slightly lower score; c is orthogonal —
    # MMR should pick c second despite b's higher raw score. (d anchors the
    # min-max normalization floor.)
    items = [
        item("a", 1.00, [1.0, 0.0]),
        item("b", 0.95, [1.0, 0.0]),
        item("c", 0.90, [0.0, 1.0]),
        item("d", 0.10, [0.5, 0.5]),
    ]
    out = mmr_rerank(items, k=2)
    assert [it.key for it in out] == ["a", "c"]


def test_mmr_respects_k_and_handles_none_embeddings():
    items = [item(f"p{i}", 1.0 - i * 0.1, None) for i in range(5)]
    out = mmr_rerank(items, k=3)
    assert len(out) == 3


def test_category_run_constraint():
    # three top-scored items share a category; 4th place is another category.
    items = [
        item("a", 1.00, [1.0, 0.0, 0.0], cat="cs.LG"),
        item("b", 0.99, [0.0, 1.0, 0.0], cat="cs.LG"),
        item("c", 0.98, [0.0, 0.0, 1.0], cat="cs.LG"),
        item("d", 0.10, [1.0, 1.0, 0.0], cat="cs.CL"),
    ]
    out = mmr_rerank(items, k=4)
    cats = [it.primary_category for it in out]
    # no run of 3 consecutive same-category items
    for i in range(len(cats) - 2):
        assert not (cats[i] == cats[i + 1] == cats[i + 2])


def test_category_run_relaxed_when_unavoidable():
    items = [item(f"p{i}", 1.0 - i * 0.01, [1.0, float(i)], cat="cs.LG") for i in range(4)]
    out = mmr_rerank(items, k=4)
    assert len(out) == 4  # falls back rather than starving the feed


def test_explore_slot_inserted():
    selected = [item(f"p{i}", 1.0, [1.0, 0.0]) for i in range(20)]
    explore = [item("x", 0.5, [0.0, 1.0], source="explore")]
    out = apply_explore_slot(selected, explore)
    assert len(out) == 20
    window = out[12:17]  # positions 13..17
    assert any(it.recall_source == "explore" for it in window)


def test_explore_slot_skipped_when_present_or_short():
    short = [item(f"p{i}", 1.0, None) for i in range(5)]
    assert apply_explore_slot(short, [item("x", 0.5, None, source="explore")]) == short
    with_explore = [item(f"p{i}", 1.0, None) for i in range(12)]
    with_explore.append(item("e", 0.9, None, source="explore"))  # position 13
    with_explore += [item(f"q{i}", 0.8, None) for i in range(7)]
    out = apply_explore_slot(with_explore, [item("x", 0.5, None, source="explore")])
    assert [it.key for it in out] == [it.key for it in with_explore]
