"""Pydantic schemas — every external input/output is validated here."""

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

EventType = Literal[
    "visible", "click_abstract", "click_pdf", "save", "dismiss", "dwell", "external_read"
]


class PaperOut(BaseModel):
    arxiv_id: str
    title: str
    abstract: str
    authors: list[dict[str, Any]]
    categories: list[str]
    primary_category: str
    published_at: datetime
    pdf_url: str | None
    citation_count: int | None


class FeedItemOut(BaseModel):
    impression_id: uuid.UUID
    position: int
    recall_source: str
    reason: str
    paper: PaperOut


class FeedResponse(BaseModel):
    request_id: uuid.UUID
    items: list[FeedItemOut]


class FeedbackIn(BaseModel):
    impression_id: uuid.UUID
    event_type: EventType
    value: float | None = None  # dwell: milliseconds


class FeedbackAck(BaseModel):
    ok: bool = True
    count: int


class SavedItemOut(BaseModel):
    saved_at: datetime
    paper: PaperOut


class SavedResponse(BaseModel):
    items: list[SavedItemOut]


class DailyMetricOut(BaseModel):
    day: date
    impressions: int | None
    clicks: int | None
    saves: int | None
    dismisses: int | None
    ctr: float | None
    profile_drift: float | None
    model_version: str | None


class ModelInfoOut(BaseModel):
    version: str
    model_type: str
    status: str
    created_at: datetime | None
    metrics: dict[str, Any] | None


class ProfileInfoOut(BaseModel):
    interaction_count: int
    updated_at: datetime | None


class StatsResponse(BaseModel):
    daily: list[DailyMetricOut]
    models: dict[str, ModelInfoOut | None]  # {'production': ..., 'staging': ...}
    profile: ProfileInfoOut


class SeedProfileIn(BaseModel):
    keywords: list[str] = Field(min_length=1, max_length=10)


class ExternalReadIn(BaseModel):
    ref: str = Field(min_length=4, max_length=300)  # arXiv id or abs/pdf URL


class ExternalReadOut(BaseModel):
    ok: bool = True
    status: Literal["recorded", "pending_embedding", "already_recorded"]
    arxiv_id: str
    title: str


class OkResponse(BaseModel):
    ok: bool = True
