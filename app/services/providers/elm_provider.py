from sqlalchemy.orm import Session

from .base_provider import BaseProvider


class ELMProvider(BaseProvider):

    name = "Employee & Labor Relations Manual"

    source_type = "ELM"

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
