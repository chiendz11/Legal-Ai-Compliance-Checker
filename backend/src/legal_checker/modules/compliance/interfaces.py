"""Future LLM/rule proposal adapter. Backend remains the owner of trusted gates."""

from typing import Protocol

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.shared.contracts.common import Context, Finding, Model
from legal_checker.shared.contracts.document_intelligence import Chunk, Evidence
from legal_checker.shared.contracts.retrieval import RetrievalEvidence
from legal_checker.shared.contracts.temporal import ApplicableRequirement


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
