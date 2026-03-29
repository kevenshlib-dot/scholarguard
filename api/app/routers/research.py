"""
Research routes for ScholarGuard (demo / placeholder).

Endpoints for literature search and summarisation. These are scaffolded for
future integration with citation databases and summarisation pipelines.
"""

from __future__ import annotations

import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.middleware.auth import UserContext, get_current_active_user
from app.middleware.rate_limiter import rate_limit
from app.schemas.common import APIResponse, Meta

router = APIRouter(prefix="/research", tags=["Research (Demo)"])


# ── Schemas (co-located since they are demo-only) ──────────────────────


class ResearchQueryRequest(BaseModel):
    """Request body for a literature search query."""

    query: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Natural-language research question or keyword query",
    )
    max_results: int = Field(10, ge=1, le=50, description="Maximum results to return")
    databases: Optional[list[str]] = Field(
        None,
        description="Restrict to specific databases (e.g. 'arxiv', 'pubmed')",
    )


class ResearchResult(BaseModel):
    """A single literature search result."""

    title: str
    authors: list[str] = Field(default_factory=list)
    abstract: Optional[str] = None
    url: Optional[str] = None
    source: str = "placeholder"
    year: Optional[int] = None


class ResearchQueryResponse(BaseModel):
    """Response containing literature search results."""

    results: list[ResearchResult] = Field(default_factory=list)
    total_found: int = 0


class SummarizeRequest(BaseModel):
    """Request body for summarising a set of texts or references."""

    texts: list[str] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Texts or abstracts to summarise",
    )
    style: str = Field(
        "concise",
        description="Summary style: 'concise', 'detailed', or 'bullet_points'",
    )


class SummarizeResponse(BaseModel):
    """Response containing the generated summary."""

    summary: str = Field(..., description="Generated summary text")
    source_count: int = Field(..., description="Number of sources summarised")


# ── Routes ──────────────────────────────────────────────────────────────


@router.post(
    "/query",
    response_model=APIResponse[ResearchQueryResponse],
    dependencies=[Depends(rate_limit())],
    summary="Search academic literature",
)
async def literature_search(
    body: ResearchQueryRequest,
    user: UserContext = Depends(get_current_active_user),
    settings: Settings = Depends(get_settings),
) -> APIResponse[ResearchQueryResponse]:
    """Search academic literature across configured databases.

    This is a demo endpoint.  In production it integrates with external
    APIs (arXiv, PubMed, Semantic Scholar) to return real results.
    Currently returns an empty result set.
    """
    start = time.perf_counter()
    request_id = str(uuid.uuid4())

    # TODO: Integrate with external academic search APIs.
    result = ResearchQueryResponse(results=[], total_found=0)

    elapsed = (time.perf_counter() - start) * 1000
    return APIResponse(
        data=result,
        meta=Meta(request_id=request_id, processing_time_ms=round(elapsed, 2)),
    )


@router.post(
    "/summarize",
    response_model=APIResponse[SummarizeResponse],
    dependencies=[Depends(rate_limit())],
    summary="Summarise academic texts (placeholder)",
)
async def summarize_texts(
    body: SummarizeRequest,
    user: UserContext = Depends(get_current_active_user),
    settings: Settings = Depends(get_settings),
) -> APIResponse[SummarizeResponse]:
    """Generate a summary of the supplied texts or abstracts.

    This is a placeholder endpoint.  In production it invokes an LLM
    summarisation pipeline.  Currently returns a stub summary.
    """
    start = time.perf_counter()
    request_id = str(uuid.uuid4())

    # TODO: Invoke LLM summarisation pipeline.
    result = SummarizeResponse(
        summary="[Placeholder] Summary generation not yet implemented.",
        source_count=len(body.texts),
    )

    elapsed = (time.perf_counter() - start) * 1000
    return APIResponse(
        data=result,
        meta=Meta(request_id=request_id, processing_time_ms=round(elapsed, 2)),
    )
