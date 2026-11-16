"""Check attributable C02 facts; optional synthetic attestations are source/hash bound.

Synthetic records are study inputs, never a claim that a human/authority issued a
document. They cannot change knowledge, a PDF quote, or an unlisted criterion.
"""

import hashlib
import json
from pathlib import Path

from legal_checker.modules.compliance.criterion_reasoner import _legal_basis
from legal_checker.modules.compliance.verification import (
    CriterionVerification,
    VerifiedExternalExcerpt,
)
from legal_checker.shared.contracts.reasoning import ExternalEvidenceRegistration, Gates
from legal_checker.shared.ids import requirement_instance_id
from legal_checker.shared.storage.artifacts import store_bytes


class SourceFactVerifier:
    def verify(self, context, profile, requirements, chunks, knowledge, *, coverage=None):
        chunks_by_id = {c.doan_id: c for c in chunks}
        evidence = {}
        for row in profile.evidence:
            chunk = chunks_by_id.get(row.doan_id)
            if chunk and chunk.noi_dung[row.ky_tu_bat_dau : row.ky_tu_ket_thuc] == row.trich_dan:
                evidence[row.bang_chung_id] = row
        facts = {}
        for row in profile.facts:
            if (
                row.trang_thai != "EXTRACTED"
                or not row.evidence_ids
                or not all(key in evidence for key in row.evidence_ids)
            ):
                continue
            value = row.gia_tri_chuan_json
            if isinstance(value, (str, int, bool)) and value is not None:
                facts[row.ten_truong] = value
        results = []
        for requirement in requirements:
            if requirement.version_status != "RESOLVED":
                continue
            for criterion in knowledge.criteria_for(requirement.requirement_version_id):
                applicability = criterion.get("dieu_kien") or {}
                if isinstance(applicability, str):
                    applicability = json.loads(applicability)
                simple = not any(
                    applicability.get(k)
                    for k in ("case_facts_required", "optional_choice", "exception_ids")
                )
                results.append(
                    CriterionVerification(
                        **context.model_dump(),
                        hop_dong_id=profile.hop_dong_id,
                        yeu_cau_ca_id=requirement.yeu_cau_ca_id,
                        tieu_chi_id=criterion["tieu_chi_id"],
                        verification_reference="C02_EXACT_SOURCE_V1",
                        local_applicability="MATCH"
                        if simple and requirement.confirmed
                        else "UNKNOWN",
                        gates=Gates(
                            scope_confirmed=requirement.confirmed,
                            version_resolved=True,
                            exceptions_resolved=simple,
                        ),
                        facts=facts,
                        facts_verified=bool(facts),
                        all_pages_readable=bool(coverage and coverage.all_pages_have_text),
                    )
                )
                from legal_checker.modules.compliance.review_scope import scope_receipt

                receipt = scope_receipt(
                    requirement, context, knowledge, contract_id=profile.hop_dong_id
                )
                if receipt:
                    _verify_draft_content(
                        results[-1],
                        criterion,
                        requirement,
                        profile,
                        chunks,
                        knowledge,
                        coverage,
                        receipt,
                    )
        return results


def _verify_draft_content(
    record, criterion, requirement, profile, chunks, knowledge, coverage, receipt
):
    """Resolve only a registered document-content target from current source facts.

    case_facts_required is a proof obligation, not a permanent UNKNOWN switch.
    Source attribution here does not attest real payments, authority or execution.
    """
    from legal_checker.modules.compliance.content_verifier import fact_sources
    from legal_checker.modules.compliance.review_scope import CONTENT_BINDINGS

    if not coverage or coverage.source_sha256 != receipt["source_sha256"]:
        raise ValueError("Draft verification source differs from C01 review receipt")
    sources = fact_sources(profile, chunks)
    target = receipt["criterion_targets"].get(criterion["tieu_chi_id"])
    if target != "CONTRACT_CONTENT":
        return
    applicability = criterion.get("dieu_kien") or {}
    if isinstance(applicability, str):
        applicability = json.loads(applicability)
    required = CONTENT_BINDINGS.get(criterion["tieu_chi_id"], ())
    present = bool(chunks) and all(c.hop_dong_id == profile.hop_dong_id for c in chunks)
    bound = present and all(name in sources for name in required)
    record.verification_reference = "C02_DRAFT_CONTENT_V2:" + receipt["receipt_sha256"]
    record.facts.update(
        {
            "assessment_mode": "DRAFT_REVIEW",
            "assessment_policy_id": receipt["policy_id"],
            "contract_source_sha256": coverage.source_sha256,
            "evaluation_target": "CONTRACT_CONTENT",
        }
    )
    # Structured money remains money; flatten only explicitly named numeric facts.
    for name, (value, _) in sources.items():
        if isinstance(value, (str, int, bool)):
            record.facts[name] = value
    record.facts_verified = bound
    record.local_applicability = (
        "MATCH"
        if bound and requirement.confirmed and not applicability.get("optional_choice")
        else "UNKNOWN"
    )
    if bound:
        record.facts["condition_triggered"] = True
    record.gates.source_verified = bool(_legal_basis(criterion, knowledge)) and (
        getattr(knowledge, "review_status", None) in {"SOURCE_CHECKED", "HUMAN_VERIFIED"}
        and criterion.get("trang_thai_nguon") in {"SOURCE_CHECKED", "VERIFIED"}
    )
    if criterion["tieu_chi_id"] == "TC_PV_HYC053_01" and all(
        name in sources for name in ("warranty_months", "warranty_unit", "warranty_start")
    ):
        from legal_checker.modules.compliance.decision_rules import load_decision_rule

        _, conditions, issues = load_decision_rule(criterion["tieu_chi_id"], "SATISFIED", knowledge)
        numeric = conditions.get("numeric_rule") or {}
        if not issues and "warranty_min_months" in numeric:
            record.facts["numeric_scope"] = numeric["scope"]
    # Resolve no exceptions only when the pinned registry declares none for this
    # criterion/article. An unknown or matching exception still needs its adapter.
    declared_exceptions = set(applicability.get("exception_ids", []))
    exceptions = [
        row
        for row in knowledge.tables.get("ngoai_le_ap_dung", [])
        if row.get("ngoai_le_id") in declared_exceptions
        or row.get("tieu_chi_id") == criterion["tieu_chi_id"]
        or (
            row.get("requirement_version_id") == criterion["requirement_version_id"]
            and not row.get("tieu_chi_id")
        )
        or (
            row.get("dieu_khoan_id") == criterion.get("source_dieu_khoan_id")
            and not row.get("tieu_chi_id")
        )
    ]
    known = {row.get("ngoai_le_id") for row in exceptions}
    exception_facts = {}
    if "warranty_subject" in sources:
        exception_facts["warranty.subject"] = sources["warranty_subject"][0]
    record.gates.exceptions_resolved = not (declared_exceptions - known) and all(
        _exception_match(row, exception_facts) is False for row in exceptions
    )
    from legal_checker.modules.compliance.source_bindings import (
        bind_maintenance_ratio,
        penalty_special_law_binding,
    )

    if penalty_special_law_binding(record, criterion, requirement, profile, knowledge, exceptions):
        record.gates.exceptions_resolved = True
    bind_maintenance_ratio(record, criterion, sources, knowledge)
    record.mandatory_confirmed = bool(
        requirement.confirmed
        and criterion.get("bat_buoc")
        and criterion.get("noi_dung_bat_buoc_trong_hd")
    )
    record.all_related_documents_received = receipt["document_set_complete"] is True
    record.facts["full_document_review_required"] = True
    from legal_checker.modules.compliance.conditional_review import condition_spec

    if spec := condition_spec(criterion["tieu_chi_id"]):
        record.facts["local_condition_policy"] = spec["policy_id"]
        record.facts["local_condition_question"] = spec["question"]
        record.facts["condition_review_required"] = True
        record.local_applicability = "UNKNOWN"
        record.facts.pop("condition_triggered", None)


def _exception_match(row, facts):
    """Three-valued condition tree; FALSE can short-circuit an irrelevant exception.

    TRUE needs an effect adapter; UNKNOWN must not be treated as an absent exception.
    """
    conditions = row.get("dieu_kien_json") or {}
    if isinstance(conditions, str):
        conditions = json.loads(conditions)
    if not isinstance(conditions, dict) or conditions.get("schema") != "CONDITION_TREE_V1":
        return None

    def evaluate(node):
        if not isinstance(node, dict):
            return None
        for key in ("all", "any"):
            if key in node:
                if not isinstance(node[key], list) or not node[key]:
                    return None
                values = [evaluate(item) for item in node[key]]
                if key == "all":
                    return (
                        False
                        if False in values
                        else True
                        if all(v is True for v in values)
                        else None
                    )
                return (
                    True if True in values else False if all(v is False for v in values) else None
                )
        if node.get("op") == "eq" and node.get("field") in facts:
            return facts[node["field"]] == node.get("value")
        return None

    return evaluate(conditions.get("match"))


class SyntheticScenarioEvidence(SourceFactVerifier):
    """Trusted composition-root opt-in, restricted to one source and snapshot.

    The scenario file is itself the stored synthetic source. Its bytes are hashed;
    each registered excerpt is a literal JSON claim at a declared JSON pointer.
    Nothing is inferred from another contract or auto-marked human reviewed.
    """

    def __init__(self, path: Path, *, artifact_dir: Path | None = None):
        self.path = Path(path)
        raw = self.path.read_bytes()
        self.sha256 = hashlib.sha256(raw).hexdigest()
        self.scenario = json.loads(raw)
        if self.scenario.get("kind") != "SYNTHETIC_SCENARIO_V1":
            raise ValueError("Not a synthetic scenario")
        self.source_sha256 = self.scenario["source_sha256"]
        self.artifact = store_bytes(artifact_dir, raw) if artifact_dir else None

    def _matches(self, sha256, knowledge):
        if hashlib.sha256(self.path.read_bytes()).hexdigest() != self.sha256:
            raise ValueError("Synthetic scenario changed after composition")
        return (
            sha256 == self.source_sha256
            and knowledge.sha256 == self.scenario["knowledge_snapshot_sha256"]
        )

    def diagnostic(self, source_sha256, knowledge):
        if not self._matches(source_sha256, knowledge):
            return None
        return {
            "module": "C07",
            "code": "SYNTHETIC_SCENARIO_USED",
            "scenario_id": self.scenario["scenario_id"],
            "scenario_sha256": self.sha256,
            "source_sha256": source_sha256,
            "evidence_kind": "SYNTHETIC",
            "not_real_documents": True,
        }

    def load(self, context, case, knowledge):
        if not self._matches(case.source.sha256, knowledge):
            return []
        rows = []
        for criterion_id, item in self.scenario["criteria"].items():
            if not item.get("external_text"):
                continue
            criterion = knowledge.criteria[criterion_id]
            version = knowledge.versions[criterion["requirement_version_id"]]
            rows.append(
                ExternalEvidenceRegistration(
                    **context.model_dump(),
                    hop_dong_id=case.hop_dong_id,
                    yeu_cau_ca_id=requirement_instance_id(context.ca_id, version["requirement_id"]),
                    tieu_chi_id=criterion_id,
                    bang_chung_id=f"SYNTHETIC_{self.sha256[:12]}_{criterion_id}",
                    object_uri=f"synthetic://{self.scenario['scenario_id']}/{self.sha256}.json",
                    sha256=self.sha256,
                    verified=True,
                    verification_reference=f"SYNTHETIC_SCENARIO_V1:{self.sha256}",
                )
            )
        return rows

    def verify(self, context, profile, requirements, chunks, knowledge, *, coverage=None):
        rows = super().verify(context, profile, requirements, chunks, knowledge, coverage=coverage)
        if not coverage or not self._matches(coverage.source_sha256, knowledge):
            return rows
        for record in rows:
            item = self.scenario["criteria"].get(record.tieu_chi_id)
            if item is None:
                continue
            criterion = knowledge.criteria[record.tieu_chi_id]
            record.verification_reference = f"SYNTHETIC_SCENARIO_V1:{self.sha256}"
            record.local_applicability = item["local_applicability"]
            record.facts = {**record.facts, **item.get("facts", {}), "synthetic_evaluation": True}
            if item.get("full_document_review") is True:
                record.facts["full_document_review_required"] = True
            record.facts_verified = True
            record.gates.source_verified = bool(_legal_basis(criterion, knowledge))
            record.gates.exceptions_resolved = item.get("exceptions_checked") is True
            record.mandatory_confirmed = bool(
                criterion.get("bat_buoc") and criterion.get("noi_dung_bat_buoc_trong_hd")
            )
            # Reading text pages does not prove absence of prohibited/missing content.
            record.all_related_documents_received = item.get("document_set_complete") is True
            visual = item.get("visual_absence_review")
            if visual and (
                visual.get("source_sha256") == coverage.source_sha256
                and visual.get("method") == "SOURCE_PINNED_VISUAL_INSPECTION"
                and visual.get("content_absent") is True
                and visual.get("pages")
                and all(type(p) is int and 1 <= p <= coverage.page_count for p in visual["pages"])
                and record.all_related_documents_received
                and coverage.all_pages_have_text
                and criterion.get("loai_kiem_tra") in {"CONTRACT_CONTENT", "NOI_DUNG_BAT_BUOC"}
            ):
                record.facts["visual_absence_reviewed"] = True
                record.gates.coverage_complete = True
                record.gates.absence_verified = True
            if item.get("external_text"):
                record.external_excerpts = [
                    VerifiedExternalExcerpt(
                        bang_chung_id=f"SYNTHETIC_{self.sha256[:12]}_{record.tieu_chi_id}",
                        sha256=self.sha256,
                        text=item["external_text"],
                        source_locator=f"/criteria/{record.tieu_chi_id}/external_text",
                    )
                ]
        return rows
