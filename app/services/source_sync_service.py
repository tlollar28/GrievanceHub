import hashlib
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

from sqlalchemy.orm import Session

from app.database.models import SourceDocument


SOURCE_DIR = Path("data/sources")


class SourceSyncService:
    @staticmethod
    def calculate_sha256(file_path: Path):
        sha256 = hashlib.sha256()

        with file_path.open("rb") as file:
            for block in iter(lambda: file.read(8192), b""):
                sha256.update(block)

        return sha256.hexdigest()

    @staticmethod
    def get_local_folder_for_source(source_type: str):
        folder_map = {
            "CONTRACT": Path("uploads/contract"),
            "ELM": Path("uploads/elm"),
            "CIM": Path("uploads/cim"),
            "LMOU": Path("uploads/lmou"),
            "ARBITRATION": Path("uploads/arbitration"),
            "STEP4": Path("uploads/step4"),
            "MOU": Path("uploads/mou"),
            "SUPERVISOR_MANUAL": Path("uploads/supervisor_manual"),
        }

        return folder_map.get(source_type.upper())

    @staticmethod
    def _update_synced_file(source: SourceDocument, final_path: Path, file_hash: str):
        """Update file provenance and invalidate processing only when it changed."""
        path_changed = source.local_path != str(final_path)
        content_changed = source.sha256 != file_hash

        source.local_path = str(final_path)
        source.sha256 = file_hash

        if path_changed or content_changed:
            source.processing_status = "pending"

    @staticmethod
    def _resolve_local_pdf(
        source: SourceDocument,
        local_pdfs: list[Path],
    ) -> Path | None:
        """Resolve one source row to one local PDF without arbitrary first-file use."""
        if source.local_path:
            configured_path = Path(source.local_path)
            if configured_path.is_file() and configured_path.suffix.lower() == ".pdf":
                return configured_path
            configured_name = configured_path.name.casefold()
            for candidate in local_pdfs:
                if candidate.name.casefold() == configured_name:
                    return candidate

        metadata = (
            getattr(source, "document_metadata", None)
            if isinstance(getattr(source, "document_metadata", None), dict)
            else {}
        )
        local_filename = metadata.get("local_filename")
        if local_filename:
            expected_name = Path(str(local_filename)).name.casefold()
            for candidate in local_pdfs:
                if candidate.name.casefold() == expected_name:
                    return candidate

        if len(local_pdfs) == 1:
            return local_pdfs[0]
        return None

    @staticmethod
    def sync_source(db: Session, source_id: int):
        source = (
            db.query(SourceDocument)
            .filter(SourceDocument.id == source_id)
            .first()
        )

        if source is None:
            return {"error": "Source not found."}

        SOURCE_DIR.mkdir(parents=True, exist_ok=True)

        local_folder = SourceSyncService.get_local_folder_for_source(
            source.source_type
        )

        if local_folder and local_folder.exists():
            local_pdfs = sorted(
                local_folder.glob("*.pdf"),
                key=lambda path: path.name.casefold(),
            )

            if local_pdfs:
                final_path = SourceSyncService._resolve_local_pdf(
                    source,
                    local_pdfs,
                )
                if final_path is None:
                    return {
                        "error": (
                            "Multiple local PDFs found; configure local_path or "
                            "document_metadata.local_filename for this source."
                        ),
                        "source_id": source.id,
                        "source_type": source.source_type,
                        "available_files": [path.name for path in local_pdfs],
                    }

                file_hash = SourceSyncService.calculate_sha256(final_path)

                SourceSyncService._update_synced_file(source, final_path, file_hash)

                db.commit()
                db.refresh(source)

                return {
                    "message": "Using existing local PDF.",
                    "id": source.id,
                    "name": source.name,
                    "source_type": source.source_type,
                    "local_path": source.local_path,
                    "sha256": source.sha256,
                }

        if not source.download_url:
            return {
                "error": "No local PDF found and no download URL exists.",
                "source_id": source.id,
                "name": source.name,
                "source_type": source.source_type,
                "expected_folder": str(local_folder) if local_folder else None,
            }

        filename = source.download_url.split("/")[-1]
        download_path = SOURCE_DIR / filename

        urlretrieve(source.download_url, download_path)

        final_path = download_path

        if download_path.suffix.lower() == ".zip":
            extract_dir = SOURCE_DIR / download_path.stem
            extract_dir.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(download_path, "r") as zip_ref:
                zip_ref.extractall(extract_dir)

            pdf_files = list(extract_dir.rglob("*.pdf"))

            if not pdf_files:
                return {
                    "error": "ZIP downloaded successfully but no PDFs were found."
                }

            final_path = pdf_files[0]

        file_hash = SourceSyncService.calculate_sha256(final_path)

        SourceSyncService._update_synced_file(source, final_path, file_hash)

        db.commit()
        db.refresh(source)

        return {
            "message": "Source synced successfully. Now run /sources/{id}/process.",
            "id": source.id,
            "name": source.name,
            "source_type": source.source_type,
            "local_path": source.local_path,
            "sha256": source.sha256,
        }
