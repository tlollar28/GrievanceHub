from sqlalchemy.orm import Session

from .base_provider import BaseProvider


class LMOUProvider(BaseProvider):
    name = "Local Memorandum of Understanding"
    source_type = "LMOU"

    def search(
        self,
        db: Session,
        query_embedding,
        limit=5,
        *,
        authorization=None,
    ):
        return self.vector_search(
            db,
            query_embedding,
            limit=limit,
            authorization=authorization,
        )
