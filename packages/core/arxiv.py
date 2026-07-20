"""arXiv Atom-entry parsing — shared by the daily ingest pipeline AND the
online API (POST /external-read fetches single papers). Lives in core because
the API image ships only packages/ + services/, never pipelines/.
"""

import re
from datetime import UTC, datetime

ARXIV_API = "https://export.arxiv.org/api/query"  # spec §6.1 (https since 2026)

_VERSION_RE = re.compile(r"v(\d+)$")
# Unescaped % starts a LaTeX comment; \% is a literal percent sign.
_LATEX_COMMENT_RE = re.compile(r"(?<!\\)%.*?$", re.MULTILINE)


def split_arxiv_id(raw: str) -> tuple[str, int]:
    """'http://arxiv.org/abs/2501.12345v2' -> ('2501.12345', 2)."""
    tail = raw.rsplit("/", 1)[-1]
    m = _VERSION_RE.search(tail)
    if m:
        return tail[: m.start()], int(m.group(1))
    return tail, 1


def clean_abstract(text: str) -> str:
    """Strip LaTeX comment residue, newlines, and redundant whitespace."""
    text = _LATEX_COMMENT_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_entry(entry) -> dict:
    """feedparser entry -> papers row dict."""
    arxiv_id, version = split_arxiv_id(entry.id)
    pdf_url = next(
        (link.href for link in entry.get("links", []) if link.get("type") == "application/pdf"),
        f"https://arxiv.org/pdf/{arxiv_id}",
    )
    categories = [t["term"] for t in entry.get("tags", [])]
    primary = entry.get("arxiv_primary_category", {}).get("term") or (
        categories[0] if categories else "unknown"
    )
    return {
        "arxiv_id": arxiv_id,
        "version": version,
        "title": clean_abstract(entry.title),
        "abstract": clean_abstract(entry.summary),
        "authors": [{"name": a.name} for a in entry.get("authors", [])],
        "categories": categories,
        "primary_category": primary,
        "published_at": datetime(*entry.published_parsed[:6], tzinfo=UTC),
        "arxiv_updated_at": datetime(*entry.updated_parsed[:6], tzinfo=UTC),
        "pdf_url": pdf_url,
    }
