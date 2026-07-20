"""POST /feedback — single event or batch; POST /external-read (spec §7, v1.2)."""

from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, HTTPException
from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from packages.core.config import get_settings
from packages.core.models import ExternalRead, Feedback, Paper
from services.api.app.deps import DbSession
from services.api.app.recsys.external import (
    DOI_KEY_PREFIX,
    already_recorded,
    materialize_external_read,
    resolve_ref,
)
from services.api.app.schemas import ExternalReadIn, ExternalReadOut, FeedbackAck, FeedbackIn

ARXIV_API = "https://export.arxiv.org/api/query"
S2_PAPER_API = "https://api.semanticscholar.org/graph/v1/paper"
S2_FIELDS = (
    "title,abstract,authors,externalIds,citationCount,"
    "publicationDate,year,openAccessPdf,fieldsOfStudy"
)

router = APIRouter()


@router.post("/feedback", response_model=FeedbackAck)
def post_feedback(payload: FeedbackIn | list[FeedbackIn], session: Session = DbSession):
    items = payload if isinstance(payload, list) else [payload]
    if not items:
        return FeedbackAck(count=0)
    for item in items:
        session.add(
            Feedback(
                impression_id=item.impression_id,
                event_type=item.event_type,
                value=item.value,
            )
        )
    try:
        session.flush()
    except IntegrityError as e:
        raise HTTPException(status_code=400, detail="unknown impression_id") from e
    return FeedbackAck(count=len(items))


def _fetch_paper_from_arxiv(arxiv_id: str) -> Paper:
    """Single-id metadata fetch. Reuses the shared parser (one implementation).

    NOTE: must import from packages.core, never pipelines — the API image
    ships only packages/ + services/ (this caused a prod-only 500 once).
    """
    import feedparser

    from packages.core.arxiv import parse_entry

    try:
        resp = httpx.get(
            ARXIV_API, params={"id_list": arxiv_id}, timeout=15.0, follow_redirects=True
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail="arxiv fetch failed") from e
    entries = feedparser.parse(resp.text).entries
    if not entries or not entries[0].get("title"):
        raise HTTPException(status_code=404, detail=f"arXiv paper not found: {arxiv_id}")
    r = parse_entry(entries[0])
    return Paper(
        arxiv_id=r["arxiv_id"],
        latest_version=r["version"],
        title=r["title"],
        abstract=r["abstract"],
        authors=r["authors"],
        categories=r["categories"],
        primary_category=r["primary_category"],
        published_at=r["published_at"],
        arxiv_updated_at=r["arxiv_updated_at"],
        pdf_url=r["pdf_url"],
    )


def _fetch_paper_from_s2(doi: str) -> tuple[Paper, str | None]:
    """Journal/non-arXiv paper (spec v1.2): metadata via Semantic Scholar.

    Returns (paper, arxiv_id_alias). Keyed 'doi:<doi>' in papers.arxiv_id.
    Abstract may be missing for some publishers — the paper is then embedded
    from its title alone (weaker but valid SPECTER2 signal).
    """
    settings = get_settings()
    headers = {"x-api-key": settings.s2_api_key} if settings.s2_api_key else {}
    try:
        resp = httpx.get(
            f"{S2_PAPER_API}/DOI:{doi}",
            params={"fields": S2_FIELDS},
            headers=headers,
            timeout=15.0,
        )
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail="Semantic Scholar fetch failed") from e
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=f"DOI not found on Semantic Scholar: {doi}")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Semantic Scholar error {resp.status_code}")
    item = resp.json()
    if not item.get("title"):
        raise HTTPException(status_code=404, detail=f"no metadata for DOI: {doi}")

    published = item.get("publicationDate") or (
        f"{item['year']}-01-01" if item.get("year") else None
    )
    published_at = (
        datetime.fromisoformat(published).replace(tzinfo=UTC) if published else datetime.now(UTC)
    )
    fields_of_study = item.get("fieldsOfStudy") or []
    pdf = (item.get("openAccessPdf") or {}).get("url") or f"https://doi.org/{doi}"
    now = datetime.now(UTC)
    months = max((now - published_at).total_seconds() / (30.44 * 86400), 0.5)
    citation_count = item.get("citationCount") or 0
    paper = Paper(
        arxiv_id=f"{DOI_KEY_PREFIX}{doi}",
        title=item["title"],
        abstract=item.get("abstract") or "",
        authors=[{"name": a.get("name", "")} for a in item.get("authors") or []],
        categories=fields_of_study,
        primary_category=fields_of_study[0] if fields_of_study else "external",
        published_at=published_at,
        arxiv_updated_at=published_at,
        pdf_url=pdf,
        s2_paper_id=item.get("paperId"),
        citation_count=citation_count,
        citation_velocity=citation_count / months,
    )
    arxiv_alias = (item.get("externalIds") or {}).get("ArXiv")
    return paper, arxiv_alias


@router.post("/external-read", response_model=ExternalReadOut)
def external_read(payload: ExternalReadIn, session: Session = DbSession):
    """Record a paper the user read outside the feed (spec v1.2).

    Accepts arXiv ids/URLs, DOIs, or publisher URLs containing a DOI.
    Embedding present -> materialize the impression + event now; otherwise
    queue it and the nightly pipeline finishes the job after embed.py runs.
    """
    resolved = resolve_ref(payload.ref)
    if resolved is None:
        raise HTTPException(
            status_code=400,
            detail="not a recognizable arXiv id/URL or DOI — 试试粘贴 DOI(10.xxxx/…)",
        )
    kind, ref_id = resolved

    if kind == "arxiv":
        paper = session.get(Paper, ref_id)
        if paper is None:
            paper = _fetch_paper_from_arxiv(ref_id)
            session.add(paper)
            session.flush()
    else:
        paper = session.get(Paper, f"{DOI_KEY_PREFIX}{ref_id}")
        if paper is None:
            fetched, arxiv_alias = _fetch_paper_from_s2(ref_id)
            if arxiv_alias:
                # S2 says this DOI is an arXiv paper — prefer the arXiv
                # identity so it dedups with the feed corpus.
                paper = session.get(Paper, arxiv_alias)
                if paper is None:
                    paper = _fetch_paper_from_arxiv(arxiv_alias)
            else:
                paper = fetched
            if session.get(Paper, paper.arxiv_id) is None:
                session.add(paper)
                session.flush()

    if already_recorded(session, paper.arxiv_id):
        return ExternalReadOut(
            status="already_recorded", arxiv_id=paper.arxiv_id, title=paper.title
        )

    if paper.embedding is not None:
        materialize_external_read(session, paper, datetime.now(UTC))
        return ExternalReadOut(status="recorded", arxiv_id=paper.arxiv_id, title=paper.title)

    pending = session.scalar(
        select(
            exists().where(
                ExternalRead.arxiv_id == paper.arxiv_id, ExternalRead.processed_at.is_(None)
            )
        )
    )
    if not pending:
        session.add(ExternalRead(arxiv_id=paper.arxiv_id))
    return ExternalReadOut(status="pending_embedding", arxiv_id=paper.arxiv_id, title=paper.title)
