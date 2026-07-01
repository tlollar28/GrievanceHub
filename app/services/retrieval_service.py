from sqlalchemy.orm import Session

from app.database.models import SourceChunk
from app.services.embedding_service import EmbeddingService
from app.services.query_expansion_service import QueryExpansionService


class RetrievalService:
    @staticmethod
    def get_relevant_chunks(
        db: Session,
        query: str,
        limit: int = 5,
    ):
        expanded_queries = QueryExpansionService.expand(query)

        all_chunks = []

        for expanded_query in expanded_queries:
            query_embedding = EmbeddingService.create_embedding(expanded_query)

            chunks = (
                db.query(SourceChunk)
                .filter(SourceChunk.embedding.isnot(None))
                .order_by(SourceChunk.embedding.cosine_distance(query_embedding))
                .limit(limit)
                .all()
            )

            all_chunks.extend(chunks)

        unique_chunks = {}

        for chunk in all_chunks:
            key = (chunk.source_document_id, chunk.chunk_index)
            unique_chunks[key] = chunk

        return list(unique_chunks.values())