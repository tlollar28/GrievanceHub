import hashlib
import re
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.auth import AuthenticatedPrincipal, require_admin_principal, require_read_principal
from app.database.session import get_db
from app.database.models import SourceDocument, SourceChunk
from app.services.source_service import SourceService
from app.services.source_processing_service import SourceProcessingService
from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.knowledge_retrieval_service import KnowledgeRetrievalService
from app.services.analysis_service import AnalysisService
from app.services.source_sync_service import SourceSyncService
from app.services.case_service import CaseNotFoundError, CaseService


router = APIRouter(
    prefix="/sources",
    tags=["Sources"],
)


SOURCE_UPLOAD_DIR = Path("data/sources")
_SAFE_UPLOAD_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,179}$")


def calculate_sha256(file_path: Path):
    sha256 = hashlib.sha256()

    with file_path.open("rb") as file:
        for block in iter(lambda: file.read(8192), b""):
            sha256.update(block)

    return sha256.hexdigest()


def _safe_upload_filename(filename: str | None) -> str:
    raw = Path(filename or "upload.pdf").name.replace(" ", "_")
    if not _SAFE_UPLOAD_NAME.match(raw):
        raise HTTPException(status_code=400, detail="Invalid upload filename.")
    if ".." in raw or "/" in raw or "\\" in raw:
        raise HTTPException(status_code=400, detail="Invalid upload filename.")
    return raw


def _public_source_dict(source: SourceDocument, *, include_local_path: bool) -> dict:
    payload = {
        "id": source.id,
        "source_id": source.source_id,
        "name": source.name,
        "source_type": source.source_type,
        "official_page": source.official_page,
        "download_url": source.download_url,
        "sha256": source.sha256,
        "is_current": source.is_current,
    }
    if include_local_path:
        payload["local_path"] = source.local_path
    return payload


@router.get("/")
def get_sources(
    db: Session = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(require_read_principal),
):
    sources = db.query(SourceDocument).all()
    include_paths = principal.is_admin

    return {
        "count": len(sources),
        "sources": [
            _public_source_dict(source, include_local_path=include_paths)
            for source in sources
        ],
    }


@router.post("/upload-pdf/")
def upload_pdf_source(
    source_id: str = Form(...),
    name: str = Form(...),
    source_type: str = Form(...),
    official_page: str | None = Form(None),
    is_current: bool = Form(True),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(require_admin_principal),
):
    del principal  # authorization side effect only
    SOURCE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    safe_filename = _safe_upload_filename(file.filename)
    saved_path = SOURCE_UPLOAD_DIR / safe_filename

    with saved_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    file_hash = calculate_sha256(saved_path)

    source = SourceDocument(
        source_id=source_id,
        name=name,
        source_type=source_type,
        official_page=official_page,
        download_url=None,
        local_path=str(saved_path),
        sha256=file_hash,
        is_current=is_current,
    )

    db.add(source)
    db.commit()
    db.refresh(source)

    return {
        "message": "PDF uploaded successfully. Now run /sources/{source_id}/process to embed it.",
        "id": source.id,
        "source_id": source.source_id,
        "name": source.name,
        "source_type": source.source_type,
        "sha256": source.sha256,
        "is_current": source.is_current,
    }


@router.post("/seed-official/")
def seed_official_sources(
    db: Session = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(require_admin_principal),
):
    del principal
    return KnowledgeBaseService.seed_official_sources(db)


@router.get("/embedded/")
def get_embedded_sources(
    db: Session = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(require_read_principal),
):
    include_paths = principal.is_admin
    sources = db.query(SourceDocument).all()
    if not sources:
        return {"count": 0, "embedded_sources": []}

    source_ids = [source.id for source in sources]
    counts = (
        db.query(
            SourceChunk.source_document_id,
            func.count(SourceChunk.id).label("total_chunks"),
            func.count(SourceChunk.embedding).label("embedded_chunks"),
        )
        .filter(SourceChunk.source_document_id.in_(source_ids))
        .group_by(SourceChunk.source_document_id)
        .all()
    )
    count_map = {
        row.source_document_id: (
            int(row.total_chunks or 0),
            int(row.embedded_chunks or 0),
        )
        for row in counts
    }

    embedded_sources = []
    for source in sources:
        total_chunks, embedded_chunks = count_map.get(source.id, (0, 0))
        item = {
            "id": source.id,
            "source_id": source.source_id,
            "name": source.name,
            "source_type": source.source_type,
            "sha256": source.sha256,
            "is_current": source.is_current,
            "total_chunks": total_chunks,
            "embedded_chunks": embedded_chunks,
            "is_embedded": embedded_chunks > 0,
        }
        if include_paths:
            item["local_path"] = source.local_path
        embedded_sources.append(item)

    return {
        "count": len(embedded_sources),
        "embedded_sources": embedded_sources,
    }


@router.get("/search/")
def search_sources(
    query: str,
    limit_per_source: int = 3,
    domain: str = "auto",
    db: Session = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(require_read_principal),
):
    results = KnowledgeRetrievalService.search_with_agents(
        db=db,
        query=query,
        authorization=principal.retrieval_authorization(),
        limit_per_source=limit_per_source,
        domain=domain,
    )

    return {
        "query": results["query"],
        "limit_per_source": results["limit_per_source"],
        "results_by_source": results["results_by_source"],
        "retrieval_status": results["retrieval_status"],
        "partial": results["partial"],
        "failures": results["failures"],
    }


@router.get("/ask/")
def ask_sources(
    question: str,
    limit_per_source: int = 3,
    db: Session = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(require_read_principal),
):
    # Retains issue-decomposition via search_all for AnalysisService parity.
    results = KnowledgeRetrievalService.search_all(
        db=db,
        query=question,
        authorization=principal.retrieval_authorization(),
        limit_per_source=limit_per_source,
    )

    return AnalysisService.answer_question(
        question=question,
        chunks=results["all_chunks"],
        issue_analysis=results.get("issue_analysis"),
        issue_keywords=results.get("issue_keywords"),
    )


@router.get("/report/")
def generate_report(
    question: str | None = None,
    limit_per_source: int = 3,
    case_uuid: str | None = None,
    db: Session = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(require_read_principal),
):
    if not question and not case_uuid:
        raise HTTPException(
            status_code=400,
            detail="Provide question and/or case_uuid.",
        )

    case_context = None
    known_facts = None
    search_question = question or ""

    if case_uuid:
        try:
            case = CaseService.get_case(db, case_uuid)
        except CaseNotFoundError:
            raise HTTPException(status_code=404, detail="Case not found")
        case_context = CaseService.build_case_context(case)
        known_facts = case.known_facts
        search_question = CaseService.build_analysis_question(case)
    elif search_question:
        search_question = question

    # Retains issue-decomposition, gaps, and coverage audit for report builders.
    results = KnowledgeRetrievalService.search_all(
        db=db,
        query=search_question,
        authorization=principal.retrieval_authorization(),
        limit_per_source=limit_per_source,
        known_facts=known_facts,
    )

    return AnalysisService.generate_report(
        question=search_question,
        chunks=results["all_chunks"],
        issue_analysis=results.get("issue_analysis"),
        issue_keywords=results.get("issue_keywords"),
        case_context=case_context,
        all_chunks=results.get("all_chunks"),
        retrieval_gaps_list=results.get("retrieval_gaps"),
        indexed_source_types=results.get("indexed_source_types"),
        source_coverage_audit=results.get("source_coverage_audit"),
    )


@router.post("/")
def create_source(
    source_id: str,
    name: str,
    source_type: str,
    official_page: str | None = None,
    download_url: str | None = None,
    db: Session = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(require_admin_principal),
):
    del principal
    source = SourceDocument(
        source_id=source_id,
        name=name,
        source_type=source_type,
        official_page=official_page,
        download_url=download_url,
        is_current=True,
    )

    db.add(source)
    db.commit()
    db.refresh(source)

    return {
        "id": source.id,
        "source_id": source.source_id,
        "name": source.name,
        "source_type": source.source_type,
        "official_page": source.official_page,
        "download_url": source.download_url,
        "sha256": source.sha256,
        "is_current": source.is_current,
    }


@router.post("/{source_id}/sync")
def sync_source(
    source_id: int,
    db: Session = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(require_admin_principal),
):
    del principal
    try:
        return SourceSyncService.sync_source(db, source_id)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Source synchronization failed.",
        )


@router.post("/{source_id}/download")
def download_source(
    source_id: int,
    db: Session = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(require_admin_principal),
):
    del principal
    return SourceService.download_source(db, source_id)


@router.post("/{source_id}/process")
def process_source(
    source_id: int,
    db: Session = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(require_admin_principal),
):
    del principal
    return SourceProcessingService.process_source(db, source_id)


@router.get("/{source_id}/chunks/{chunk_index}")
def get_chunk(
    source_id: int,
    chunk_index: int,
    db: Session = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(require_read_principal),
):
    del principal
    chunk = (
        db.query(SourceChunk)
        .filter(
            SourceChunk.source_document_id == source_id,
            SourceChunk.chunk_index == chunk_index,
        )
        .first()
    )

    if chunk is None:
        raise HTTPException(status_code=404, detail="Chunk not found.")

    payload = AnalysisService.chunk_to_source_dict(chunk)
    # Never expose local filesystem paths through chunk serialization.
    if isinstance(payload, dict):
        payload.pop("local_path", None)
        metadata = payload.get("retrieval_metadata")
        if isinstance(metadata, dict):
            metadata.pop("local_path", None)
    return payload
