from pathlib import Path
import os
import traceback

from dotenv import load_dotenv
from pypdf import PdfReader
from sqlalchemy.orm import Session
from openai import OpenAI

from app.database.models import SourceDocument, SourceChunk

load_dotenv()


MAX_CHARS = 6000


def split_text(text: str, max_chars: int = MAX_CHARS):
    text = text.strip()

    if not text:
        return []

    chunks = []

    while len(text) > max_chars:
        split_at = text.rfind(" ", 0, max_chars)

        if split_at == -1:
            split_at = max_chars

        chunks.append(text[:split_at].strip())
        text = text[split_at:].strip()

    if text:
        chunks.append(text)

    return chunks


class SourceProcessingService:
    @staticmethod
    def process_source(db: Session, source_id: int):
        try:
            source = (
                db.query(SourceDocument)
                .filter(SourceDocument.id == source_id)
                .first()
            )

            if source is None:
                return {"error": "Source not found."}

            if not source.local_path:
                return {"error": "Source has not been downloaded yet."}

            pdf_path = Path(source.local_path)

            if not pdf_path.exists():
                return {"error": f"File not found: {pdf_path}"}

            db.query(SourceChunk).filter(
                SourceChunk.source_document_id == source.id
            ).delete()

            reader = PdfReader(str(pdf_path))

            client = OpenAI(
                api_key=os.getenv("OPENAI_API_KEY")
            )

            chunk_count = 0

            for page_number, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ""

                paragraphs = [
                    p.strip()
                    for p in text.split("\n\n")
                    if p.strip()
                ]

                for paragraph in paragraphs:
                    safe_chunks = split_text(paragraph)

                    for safe_text in safe_chunks:
                        response = client.embeddings.create(
                            model="text-embedding-3-small",
                            input=safe_text,
                        )

                        embedding = response.data[0].embedding

                        chunk = SourceChunk(
                            source_document_id=source.id,
                            chunk_index=chunk_count,
                            page_number=page_number,
                            text=safe_text,
                            embedding=embedding,
                        )

                        db.add(chunk)
                        chunk_count += 1

            db.commit()

            return {
                "message": "Source processed successfully.",
                "source_id": source.id,
                "pages": len(reader.pages),
                "chunks_created": chunk_count,
            }

        except Exception as e:
            traceback.print_exc()
            return {
                "error": str(e),
                "type": type(e).__name__,
            }