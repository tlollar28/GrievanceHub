"""Contract and contract-related evidence retriever."""

from sqlalchemy import and_, or_

from app.database.models import SourceDocument
from app.services.retrieval.base_agent import SqlVectorRetrievalAgent
from app.services.retrieval.models import AgentIdentity


CONTRACT_SOURCE_TYPES = frozenset(
    {
        "ARBITRATION",
        "CIM",
        "CONTRACT",
        "ELM",
        "LMOU",
    }
)

CONTRACT_EVIDENCE_ROLES = {
    "ARBITRATION": "arbitral_persuasive_support",
    "CIM": "contract_interpretation",
    "CONTRACT": "contract_controlling",
    "ELM": "employment_labor_rule",
    "LMOU": "local_contract_provision",
}


class ContractAgent(SqlVectorRetrievalAgent):
    """Retrieve authoritative or contract-related evidence only.

    `pending` rows are normally ineligible. A narrow pre-W5 compatibility arm
    admits current contract-domain rows that have a SHA plus persisted embedded
    chunks but no W5 processed SHA/error metadata. The chunk embedding predicate
    remains in SQL, so genuinely unprocessed rows do not qualify.
    """

    identity = AgentIdentity(
        name="ContractAgent",
        domain="contract",
        supported_source_types=CONTRACT_SOURCE_TYPES,
    )

    @property
    def default_evidence_role(self) -> str:
        return "contract_related_evidence"

    def evidence_role_for(self, source_type: str) -> str:
        return CONTRACT_EVIDENCE_ROLES.get(
            source_type,
            self.default_evidence_role,
        )

    def processing_predicate(self):
        completed_current = and_(
            SourceDocument.processing_status == "completed",
            SourceDocument.processed_sha256.isnot(None),
            or_(
                SourceDocument.sha256.is_(None),
                SourceDocument.processed_sha256 == SourceDocument.sha256,
            ),
        )
        legacy_pre_w5_index = and_(
            SourceDocument.processing_status == "pending",
            SourceDocument.processed_sha256.is_(None),
            SourceDocument.processing_error.is_(None),
            SourceDocument.sha256.isnot(None),
        )
        return or_(completed_current, legacy_pre_w5_index)
