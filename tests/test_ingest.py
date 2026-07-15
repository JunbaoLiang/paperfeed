from datetime import UTC

from pipelines.enrich import citation_velocity
from pipelines.ingest import clean_abstract, split_arxiv_id


def test_split_arxiv_id():
    assert split_arxiv_id("http://arxiv.org/abs/2501.12345v2") == ("2501.12345", 2)
    assert split_arxiv_id("http://arxiv.org/abs/2501.12345v1") == ("2501.12345", 1)
    assert split_arxiv_id("2501.12345") == ("2501.12345", 1)
    assert split_arxiv_id("http://arxiv.org/abs/2501.12345v12") == ("2501.12345", 12)


def test_clean_abstract_whitespace():
    assert clean_abstract("line one\n  line two\t three") == "line one line two three"


def test_clean_abstract_latex_comments():
    text = "Real content % a latex comment\nmore content"
    assert clean_abstract(text) == "Real content more content"
    # escaped percent survives
    assert clean_abstract(r"accuracy of 95\% improved") == r"accuracy of 95\% improved"


def test_citation_velocity_floor():
    from datetime import datetime, timedelta

    now = datetime(2026, 7, 14, tzinfo=UTC)
    # brand-new paper: months floored at 0.5
    assert citation_velocity(10, now - timedelta(days=1), now) == 10 / 0.5
    # ~2 months old
    two_months = now - timedelta(days=60.88)
    assert abs(citation_velocity(10, two_months, now) - 5.0) < 0.1
