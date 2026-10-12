"""Future LLM/rule proposal adapter. Backend remains the owner of trusted gates."""

from typing import Protocol

from app.application.ports.knowledge import KnowledgeSnapshot
from app.contracts.common import Context, Finding, Model
from app.contracts.document_intelligence import Chunk, Evidence
from app.contracts.retrieval import RetrievalEvidence
from app.contracts.temporal import ApplicableRequirement


class CriterionProposal(Model):
    tieu_chi_id: str
    finding: Finding
    giai_thich: str
    evidence: list[Evidence]
    # No provider-owned scope/source/coverage/absence verification flags.


class CriterionProposalProvider(Protocol):
    def propose(
        self,
        context: Context,
        requirement: ApplicableRequirement,
        criterion_id: str,
        retrieval: list[RetrievalEvidence],
        chunks: list[Chunk],
        knowledge: KnowledgeSnapshot,
    ) -> CriterionProposal: ...
