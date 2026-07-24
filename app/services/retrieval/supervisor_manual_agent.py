"""Supervisor Manual evidence retriever."""

from sqlalchemy import and_, or_

from app.database.models import SourceDocument
from app.services.retrieval.base_agent import SqlVectorRetrievalAgent
from app.services.retrieval.models import AgentIdentity


class SupervisorManualAgent(SqlVectorRetrievalAgent):
    """Retrieve non-controlling supervisory guidance from completed manuals."""

    identity = AgentIdentity(
        name="SupervisorManualAgent",
        domain="supervisor_manual",
        supported_source_types=frozenset({"SUPERVISOR_MANUAL"}),
    )

    @property
    def default_evidence_role(self) -> str:
        return "supervisory_guidance_non_controlling"

    def processing_predicate(self):
        return and_(
            SourceDocument.processing_status == "completed",
            SourceDocument.processed_sha256.isnot(None),
            or_(
                SourceDocument.sha256.is_(None),
                SourceDocument.processed_sha256 == SourceDocument.sha256,
            ),
        )
