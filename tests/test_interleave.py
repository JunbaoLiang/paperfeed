import random
from collections import Counter

from services.api.app.recsys.interleave import team_draft


def test_no_duplicates_and_k():
    prod = [f"p{i}" for i in range(30)]
    chal = [f"p{i}" for i in range(29, -1, -1)]
    out = team_draft(prod, chal, k=20, rng=random.Random(42))
    keys = [it.key for it in out]
    assert len(keys) == 20
    assert len(set(keys)) == 20


def test_both_arms_represented_fairly():
    prod = [f"a{i}" for i in range(20)] + [f"c{i}" for i in range(20)]
    chal = [f"b{i}" for i in range(20)] + [f"c{i}" for i in range(20)]
    out = team_draft(prod, chal, k=20, rng=random.Random(7))
    arms = Counter(it.arm for it in out)
    assert arms["prod"] == 10
    assert arms["challenger"] == 10


def test_top_items_of_each_arm_survive():
    prod = ["p1", "p2", "x"]
    chal = ["c1", "c2", "x"]
    out = team_draft(prod, chal, k=4, rng=random.Random(0))
    keys = {it.key for it in out}
    assert "p1" in keys
    assert "c1" in keys


def test_exhaustion_stops_cleanly():
    out = team_draft(["a", "b"], ["a", "b"], k=10, rng=random.Random(1))
    assert len(out) == 2
    assert {it.key for it in out} == {"a", "b"}


def test_shared_item_attributed_once():
    out = team_draft(["s"], ["s"], k=2, rng=random.Random(3))
    assert len(out) == 1
    assert out[0].key == "s"
