from sqlalchemy.orm import Session

from .base_provider import BaseProvider


class CIMProvider(BaseProvider):
    name = "Contract Interpretation Manual"
    source_type = "CIM"

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
