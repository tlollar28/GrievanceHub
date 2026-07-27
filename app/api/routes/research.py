"""Browser-safe, read-only Sources Research API (W6 M9 interim boundary).

These routes intentionally do NOT use require_read_principal / API keys.
The React browser must never hold GRIEVANCEHUB_API_KEY. Research reuses the
retrieval service layer in-process with a server-constructed global-corpus
authorization context.

Protected /sources routes remain API-key gated for administration.
This boundary is not production authentication (W9).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.research_schema import (
    ResearchMetaResponse,
    ResearchPassageDetail,
    ResearchSearchRequest,
    ResearchSearchResponse,
    ResearchSourceDetail,
    ResearchSourceListResponse,
)
from app.services.research_service import (
    RESEARCH_LIST_DEFAULT_LIMIT,
    RESEARCH_LIST_MAX_LIMIT,
    RESEARCH_MAX_OFFSET,
    ResearchNotFoundError,
    ResearchService,
    ResearchValidationError,
)

router = APIRouter(
    prefix="/research",
    tags=["Sources Research"],
)


def _ignore_browser_credentials(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """Accept headers if present but never treat them as research authority.

    Browser clients must not send source API keys. If a key is present it is
    ignored — privilege is not elevated and secrets are not echoed.
    """
    del authorization, x_api_key


@router.get("/meta", response_model=ResearchMetaResponse)
def research_meta(
    _: None = Depends(_ignore_browser_credentials),
) -> ResearchMetaResponse:
    return ResearchService.get_meta()


@router.get("/sources", response_model=ResearchSourceListResponse)
def list_research_sources(
    limit: int = Query(default=RESEARCH_LIST_DEFAULT_LIMIT, ge=1, le=RESEARCH_LIST_MAX_LIMIT),
    offset: int = Query(default=0, ge=0, le=RESEARCH_MAX_OFFSET),
    source_type: str | None = Query(default=None, max_length=64),
    db: Session = Depends(get_db),
    _: None = Depends(_ignore_browser_credentials),
) -> ResearchSourceListResponse:
    try:
        return ResearchService.list_sources(
            db,
            limit=limit,
            offset=offset,
            source_type=source_type,
        )
    except ResearchValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/sources/{source_document_id}",
    response_model=ResearchSourceDetail,
)
def get_research_source(
    source_document_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(_ignore_browser_credentials),
) -> ResearchSourceDetail:
    try:
        return ResearchService.get_source(db, source_document_id)
    except ResearchNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/search", response_model=ResearchSearchResponse)
def research_search(
    body: ResearchSearchRequest,
    db: Session = Depends(get_db),
    _: None = Depends(_ignore_browser_credentials),
) -> ResearchSearchResponse:
    try:
        return ResearchService.search(db, body)
    except ResearchValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Retrieval is temporarily unavailable.",
        ) from None


@router.get(
    "/passages/{source_chunk_id}",
    response_model=ResearchPassageDetail,
)
def get_research_passage(
    source_chunk_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(_ignore_browser_credentials),
) -> ResearchPassageDetail:
    try:
        return ResearchService.get_passage(db, source_chunk_id)
    except ResearchNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
