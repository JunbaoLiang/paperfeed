from services.api.app.recsys.external import parse_arxiv_ref, parse_doi_ref, resolve_ref


def test_parse_bare_id():
    assert parse_arxiv_ref("2501.12345") == "2501.12345"
    assert parse_arxiv_ref(" 2501.12345v3 ") == "2501.12345"


def test_parse_urls():
    assert parse_arxiv_ref("https://arxiv.org/abs/2501.12345") == "2501.12345"
    assert parse_arxiv_ref("https://arxiv.org/abs/2501.12345v2") == "2501.12345"
    assert parse_arxiv_ref("https://arxiv.org/pdf/2501.12345.pdf") == "2501.12345"
    assert parse_arxiv_ref("https://arxiv.org/pdf/2501.12345v1/") == "2501.12345"


def test_parse_old_style_id():
    assert parse_arxiv_ref("quant-ph/0703112") == "quant-ph/0703112"
    assert parse_arxiv_ref("https://arxiv.org/abs/cs/0703112v2") == "cs/0703112"


def test_parse_garbage():
    assert parse_arxiv_ref("not a paper") is None
    assert parse_arxiv_ref("https://example.com/foo") is None
    assert parse_arxiv_ref("10.1038/nature12345") is None  # DOI, not arXiv


def test_parse_doi():
    assert parse_doi_ref("10.1038/nature12345") == "10.1038/nature12345"
    assert parse_doi_ref("https://doi.org/10.1021/jacs.3c01234") == "10.1021/jacs.3c01234"
    assert parse_doi_ref("https://pubs.acs.org/doi/10.1021/jacs.3c01234") == "10.1021/jacs.3c01234"
    assert parse_doi_ref("DOI: 10.1073/pnas.2216805120.") == "10.1073/pnas.2216805120"
    assert parse_doi_ref("no doi here") is None


def test_resolve_ref_dispatch():
    assert resolve_ref("2501.12345") == ("arxiv", "2501.12345")
    assert resolve_ref("https://arxiv.org/abs/2501.12345v2") == ("arxiv", "2501.12345")
    assert resolve_ref("10.1038/nature12345") == ("doi", "10.1038/nature12345")
    assert resolve_ref("https://doi.org/10.1021/jacs.3c01234") == (
        "doi",
        "10.1021/jacs.3c01234",
    )
    assert resolve_ref("random text") is None
    # arXiv's DataCite DOI normalizes to the arXiv identity
    assert resolve_ref("10.48550/arXiv.1706.03762") == ("arxiv", "1706.03762")
    assert resolve_ref("https://doi.org/10.48550/arXiv.2501.12345") == ("arxiv", "2501.12345")
