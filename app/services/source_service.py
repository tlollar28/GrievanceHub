from pathlib import Path
import hashlib
import requests

from sqlalchemy.orm import Session

from app.database.models import SourceDocument
from app.config import DATA_DIR


DOWNLOAD_DIR = DATA_DIR / "sources"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


class SourceService:
    @staticmethod
    def download_source(db: Session, source_id: int):
        source = db.query(SourceDocument).filter(SourceDocument.id == source_id).first()

        if source is None:
            return {"error": "Source not found."}

        if not source.download_url:
            return {"error": "Source has no download URL."}

        filename = Path(source.download_url).name or f"source_{source.id}.pdf"
        destination = DOWNLOAD_DIR / filename

        try:
            response = requests.get(
                source.download_url,
                timeout=15,
                headers={
                    "User-Agent": "Mozilla/5.0 GrievanceHub Source Manager"
                },
            )
            response.raise_for_status()
        except requests.RequestException as error:
            return {
                "error": "Download failed.",
                "detail": str(error),
                "url": source.download_url,
            }

        destination.write_bytes(response.content)

        sha256 = hashlib.sha256(response.content).hexdigest()

        source.local_path = str(destination)
        source.sha256 = sha256
        source.final_url = response.url
        source.content_type = response.headers.get("content-type")

        db.commit()
        db.refresh(source)

        return {
            "message": "Download complete.",
            "source_id": source.id,
            "file": str(destination),
            "sha256": sha256,
            "content_type": source.content_type,
            "final_url": source.final_url,
        }