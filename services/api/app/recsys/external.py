"""Externally-read papers → training-ready events (spec v1.2).

Materializing = creating an impression with recall_source='external' whose
feature snapshot is computed by the ONE shared implementation at that moment,
plus an 'external_read' feedback event. Used by both the API endpoint (when
the paper's embedding already exists) and the nightly pipeline (for papers
that had to wait for embed.py). Single implementation — pipelines import from
here rather than duplicating.
"""

import re
import uuid
from datetime import datetime

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from packages.core.features import INFERENCE_POSITION
from packages.core.models import Feedback, Impression, Paper
from services.api.app.recsys.features import compute_candidate_features, load_online_context

# New-style (2501.12345) or old-style (quant-ph/0703112) arXiv ids.
_ARXIV_ID_RE = re.compile(r"(\d{4}\.\d{4,5})(v\d+)?$|([a-z-]+(?:\.[A-Z]{2})?/\d{7})(v\d+)?$")
# DOI anywhere in the string (bare, doi.org URL, or publisher URL).
_DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"'<>]+)", re.IGNORECASE)

# Sentinel model_version for impressions that no model produced.
EXTERNAL_MODEL_VERSION = "external"

# Non-arXiv papers (journals etc., spec v1.2) are keyed 'doi:<doi>' in
# papers.arxiv_id — the column doubles as a generic paper key for them.
DOI_KEY_PREFIX = "doi:"


def parse_arxiv_ref(text: str) -> str | None:
    """'2501.12345' | 'https://arxiv.org/abs/2501.12345v2' | pdf URL -> bare id."""
    text = text.strip().removesuffix(".pdf").rstrip("/")
    if "doi.org/" in text.lower() or _DOI_RE.match(text):
        return None  # it's a DOI-shaped ref, not arXiv
    m = _ARXIV_ID_RE.search(text)
    if not m:
        return None
    return m.group(1) or m.group(3)


def parse_doi_ref(text: str) -> str | None:
    """Bare DOI, doi.org URL, or publisher URL containing one -> normalized DOI."""
    m = _DOI_RE.search(text.strip())
    if not m:
        return None
    return m.group(1).rstrip(".,;)]}").lower()


def resolve_ref(text: str) -> tuple[str, str] | None:
    """-> ('arxiv', id) | ('doi', doi) | None."""
    arxiv_id = parse_arxiv_ref(text)
    if arxiv_id is not None:
        return ("arxiv", arxiv_id)
    doi = parse_doi_ref(text)
    if doi is not None:
        # arXiv's own DataCite DOIs (10.48550/arXiv.<id>) encode the arXiv id
        # directly — and S2 doesn't index them, so normalize here.
        m = re.match(r"10\.48550/arxiv\.(.+)$", doi)
        if m:
            return ("arxiv", m.group(1))
        return ("doi", doi)
    return None


def already_recorded(session: Session, arxiv_id: str) -> bool:
    return bool(
        session.scalar(
            select(
                exists().where(
                    Impression.paper_id == arxiv_id,
                    Impression.recall_source == "external",
                )
            )
        )
    )


def materialize_external_read(session: Session, paper: Paper, now: datetime) -> uuid.UUID:
    """Create the impression (real feature snapshot, snapshotted NOW) and the
    external_read event. Caller ensures paper.embedding is present."""
    octx = load_online_context(session)
    features = compute_candidate_features(paper, octx.ctx, "external", now)
    impression_id = uuid.uuid4()
    session.add(
        Impression(
            impression_id=impression_id,
            request_id=uuid.uuid4(),  # its own singleton group in training
            paper_id=paper.arxiv_id,
            # No display position exists; store the inference constant so the
            # training row matches what serving-time snapshots look like.
            position=int(INFERENCE_POSITION),
            recall_source="external",
            model_version=EXTERNAL_MODEL_VERSION,
            score=0.0,
            features=features,
            interleave_arm=None,
        )
    )
    # No relationship() links these models, so flush to guarantee the
    # impression row exists before the FK-dependent feedback insert.
    session.flush()
    session.add(Feedback(impression_id=impression_id, event_type="external_read"))
    return impression_id
