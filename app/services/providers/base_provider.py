from abc import ABC, abstractmethod

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.database.models import SourceChunk, SourceDocument


class BaseProvider(ABC):
    """
    Every knowledge source (Contract, ELM, CIM, LMOU, etc.)
    inherits from this.
    """

    name = ""
    source_type = ""

    @abstractmethod
    def search(
        self,
        db: Session,
        query_embedding,
        limit=5,
        *,
        authorization=None,
    ) -> list[tuple]:
        """
        Return list of (SourceChunk, cosine_distance) tuples ordered by
        ascending distance (best match first).
        """
        pass

    def _authorization_predicates(self, authorization) -> list:
        """Translate trusted scope into SQL predicates.

        When authorization is omitted, providers fail closed to global corpus
        only so legacy callers cannot accidentally scan organization-owned rows.
        """
        if authorization is None:
            return [SourceDocument.organization_id.is_(None)]

        if (
            getattr(authorization, "is_admin", False)
            and getattr(authorization, "allow_all_organizations", False)
        ):
            return []

        predicates = []
        if getattr(authorization, "allow_global_sources", False):
            predicates.append(SourceDocument.organization_id.is_(None))
        allowed_orgs = getattr(authorization, "allowed_organization_ids", None) or ()
        if allowed_orgs:
            predicates.append(
                SourceDocument.organization_id.in_(sorted(allowed_orgs))
            )
        if not predicates:
            # Explicit empty scope: match nothing.
            predicates.append(SourceDocument.id.is_(None))
        return predicates

    def vector_search(
        self,
        db: Session,
        query_embedding,
        limit=5,
        *,
        authorization=None,
    ) -> list[tuple]:
        distance = SourceChunk.embedding.cosine_distance(query_embedding)
        query = (
            db.query(SourceChunk, distance.label("distance"))
            .options(joinedload(SourceChunk.source_document))
            .join(SourceDocument)
            .filter(SourceDocument.source_type == self.source_type)
            .filter(SourceChunk.embedding.isnot(None))
        )
        predicates = self._authorization_predicates(authorization)
        if len(predicates) == 1:
            query = query.filter(predicates[0])
        elif predicates:
            query = query.filter(or_(*predicates))

        rows = query.order_by(distance).limit(limit).all()
        return [(chunk, float(dist)) for chunk, dist in rows]
