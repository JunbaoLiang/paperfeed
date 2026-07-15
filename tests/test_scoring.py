import math

from packages.core.scoring import rule_score


def test_rule_score_formula():
    f = {"cos_profile": 0.8, "hours_since_pub": 72.0, "log_citations": math.log1p(100)}
    expected = 0.60 * 0.8 + 0.25 * math.exp(-1.0) + 0.15 * 1.0
    assert abs(rule_score(f) - expected) < 1e-9


def test_rule_score_citation_cap():
    f = {"cos_profile": 0.0, "hours_since_pub": 1e9, "log_citations": math.log1p(100000)}
    assert abs(rule_score(f) - 0.15) < 1e-9  # citation term capped at 1.0


def test_rule_score_cold_start_default():
    # missing cos_profile falls back to the 0.5 constant (spec §8.1)
    f = {"hours_since_pub": 0.0, "log_citations": 0.0}
    assert abs(rule_score(f) - (0.60 * 0.5 + 0.25)) < 1e-9
