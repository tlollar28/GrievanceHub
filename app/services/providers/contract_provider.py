from sqlalchemy.orm import Session

from app.database.models import SourceChunk, SourceDocument
from .base_provider import BaseProvider


class ContractProvider(BaseProvider):

    name = "National Agreement"

    source_type = "CONTRACT"

    def search(self, db: Session, query_embedding, limit=5):
        distance = SourceChunk.embedding.cosine_distance(query_embedding)

        rows = (
            db.query(SourceChunk, distance.label("distance"))
            .join(SourceDocument)
            .filter(SourceDocument.source_type == self.source_type)
            .filter(SourceChunk.embedding.isnot(None))
            .order_by(distance)
            .limit(limit)
            .all()
        )

        return [(chunk, float(dist)) for chunk, dist in rows]
