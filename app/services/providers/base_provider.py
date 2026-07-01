from abc import ABC, abstractmethod
from sqlalchemy.orm import Session


class BaseProvider(ABC):
    """
    Every knowledge source (Contract, ELM, CIM, LMOU, etc.)
    inherits from this.
    """

    name = ""
    source_type = ""

    @abstractmethod
    def search(self, db: Session, query_embedding, limit=5) -> list[tuple]:
        """
        Return list of (SourceChunk, cosine_distance) tuples ordered by
        ascending distance (best match first).
        """
        pass
