import hashlib
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

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


def calculate_sha256(file_path: Path):
    sha256 = hashlib.sha256()

    with file_path.open("rb") as file:
        for block in iter(lambda: file.read(8192), b""):
            sha256.update(block)

    return sha256.hexdigest()


@router.get("/")
def get_sources(db: Session = Depends(get_db)):
    sources = db.query(SourceDocument).all()

    return {
        "count": len(sources),
        "sources": [
            {
                "id": source.id,
                "source_id": source.source_id,
                "name": source.name,
                "source_type": source.source_type,
                "official_page": source.official_page,
                "download_url": source.download_url,
                "local_path": source.local_path,
                "sha256": source.sha256,
                "is_current": source.is_current,
            }
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
):
    SOURCE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    safe_filename = file.filename.replace(" ", "_")
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
        "local_path": source.local_path,
        "sha256": source.sha256,
        "is_current": source.is_current,
    }


@router.post("/seed-official/")
def seed_official_sources(db: Session = Depends(get_db)):
    return KnowledgeBaseService.seed_official_sources(db)


@router.get("/embedded/")
def get_embedded_sources(db: Session = Depends(get_db)):
    sources = db.query(SourceDocument).all()
    embedded_sources = []

    for source in sources:
        embedded_chunks = (
            db.query(SourceChunk)
            .filter(
                SourceChunk.source_document_id == source.id,
                SourceChunk.embedding.isnot(None),
            )
            .count()
        )

        total_chunks = (
            db.query(SourceChunk)
            .filter(SourceChunk.source_document_id == source.id)
            .count()
        )

        embedded_sources.append(
            {
                "id": source.id,
                "source_id": source.source_id,
                "name": source.name,
                "source_type": source.source_type,
                "local_path": source.local_path,
                "sha256": source.sha256,
                "is_current": source.is_current,
                "total_chunks": total_chunks,
                "embedded_chunks": embedded_chunks,
                "is_embedded": embedded_chunks > 0,
            }
        )

    return {
        "count": len(embedded_sources),
        "embedded_sources": embedded_sources,
    }


@router.get("/search/")
def search_sources(
    query: str,
    limit_per_source: int = 3,
    db: Session = Depends(get_db),
):
    results = KnowledgeRetrievalService.search_all(
        db=db,
        query=query,
        limit_per_source=limit_per_source,
    )

    return {
        "query": results["query"],
        "limit_per_source": results["limit_per_source"],
        "results_by_source": results["results_by_source"],
    }


@router.get("/ask/")
def ask_sources(
    question: str,
    limit_per_source: int = 3,
    db: Session = Depends(get_db),
):
    results = KnowledgeRetrievalService.search_all(
        db=db,
        query=question,
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
):
    from fastapi import HTTPException

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

    results = KnowledgeRetrievalService.search_all(
        db=db,
        query=search_question,
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
    )


@router.post("/")
def create_source(
    source_id: str,
    name: str,
    source_type: str,
    official_page: str | None = None,
    download_url: str | None = None,
    db: Session = Depends(get_db),
):
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
        "local_path": source.local_path,
        "sha256": source.sha256,
        "is_current": source.is_current,
    }


@router.post("/{source_id}/sync")
def sync_source(
    source_id: int,
    db: Session = Depends(get_db),
):
    try:
        return SourceSyncService.sync_source(db, source_id)
    except Exception as e:
        return {
            "error": str(e),
            "type": type(e).__name__,
        }


@router.post("/{source_id}/download")
def download_source(
    source_id: int,
    db: Session = Depends(get_db),
):
    return SourceService.download_source(db, source_id)


@router.post("/{source_id}/process")
def process_source(
    source_id: int,
    db: Session = Depends(get_db),
):
    return SourceProcessingService.process_source(db, source_id)


@router.get("/{source_id}/chunks/{chunk_index}")
def get_chunk(
    source_id: int,
    chunk_index: int,
    db: Session = Depends(get_db),
):
    chunk = (
        db.query(SourceChunk)
        .filter(
            SourceChunk.source_document_id == source_id,
            SourceChunk.chunk_index == chunk_index,
        )
        .first()
    )

    if chunk is None:
        return {"error": "Chunk not found."}

    return AnalysisService.chunk_to_source_dict(chunk)