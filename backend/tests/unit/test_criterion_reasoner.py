"""Pure reasoning tests with reviewed, synthetic knowledge and no database dependency."""

import json
from copy import deepcopy

import pytest

from legal_checker.modules.compliance.criterion_reasoner import reason
from legal_checker.shared.contracts.reasoning import CriterionResult, ReasoningRequest


class InMemoryKnowledge:
    """A small KnowledgeSnapshot fake; no seed annotation is promoted to legal truth."""

    def __init__(self):
        self.sha256 = "a" * 64
        self.schema_version = "test-reviewed-knowledge-v1"
        self.criteria = {
            "CRITERION_1": {
                "tieu_chi_id": "CRITERION_1",
                "requirement_version_id": "VERSION_1",
                "thu_tu": 1,
                "noi_dung": "The current criterion has been independently checked.",
                "loai_kiem_tra": "CONTRACT_CONTENT",
                "bang_chung_can_thiet": "An attributable passage for this criterion.",
                "missing_policy": "MISSING_CHI_KHI_NOI_DUNG_BAT_BUOC_VA_DA_KIEM_TRA_TOAN_BO",
                "bat_buoc": True,
                "noi_dung_bat_buoc_trong_hd": True,
                "human_verified": True,
                "trang_thai": "HUMAN_VERIFIED",
                "trang_thai_nguon": "VERIFIED",
                "source_dieu_khoan_id": "ARTICLE_1",
                "can_cu_cu_the": "Synthetic reviewed article, current criterion only.",
            }
        }
        self.versions = {
            "VERSION_1": {
                "requirement_version_id": "VERSION_1",
                "requirement_id": "REQUIREMENT_1",
                "source_van_ban_id": "DOCUMENT_1",
                "dieu_khoan_id": "ARTICLE_1",
                "trang_thai_ra_soat": "HUMAN_VERIFIED",
            }
        }
        self.articles = {
            "ARTICLE_1": {
                "dieu_khoan_id": "ARTICLE_1",
                "van_ban_id": "DOCUMENT_1",
                "noi_dung": "Synthetic legal provenance used only in a unit test.",
            }
        }
        self.documents = {"DOCUMENT_1": {"van_ban_id": "DOCUMENT_1"}}
        self.risks = {}
        self.recommendations = {}
        self.aggregations = {}
        conditions = {
            "enabled": True,
            "gate": {
                "scope_confirmed": True,
                "source_available": True,
                "version_resolved": True,
                "evidence_validated": True,
                "exceptions_resolved": True,
                "no_unresolved_conflict": True,
            },
            "predicate": "Provider attests that the passage satisfies this criterion.",
            "numeric_rule": None,
            "scope_of_facts": "CURRENT_CRITERION",
            "criterion_target_only": True,
        }
        self.tables = {
            "tieu_chi_danh_gia": list(self.criteria.values()),
            "phien_ban_yeu_cau": list(self.versions.values()),
            "dieu_khoan_phap_ly": list(self.articles.values()),
            "van_ban_phap_ly": list(self.documents.values()),
            "quy_tac_quyet_dinh": [
                {
                    "quy_tac_id": f"RULE_CRITERION_1_{finding}",
                    "tieu_chi_id": "CRITERION_1",
                    "finding": finding,
                    "dieu_kien_json": deepcopy(conditions),
                    "human_verified": True,
                    "trang_thai": "HUMAN_VERIFIED",
                    "rule_version": "RULE_TEST",
                }
                for finding in ("SATISFIED", "VIOLATED", "MISSING", "UNKNOWN")
            ],
            "nguon_phap_ly": [],
            "nguon_yeu_cau": [],
            "ngoai_le_ap_dung": [],
        }

    def criteria_for(self, version_id):
        return sorted(
            [row for row in self.criteria.values() if row["requirement_version_id"] == version_id],
            key=lambda row: (row["thu_tu"], row["tieu_chi_id"]),
        )

    def decision(self, criterion_id, finding):
        matches = [
            row
            for row in self.tables["quy_tac_quyet_dinh"]
            if row["tieu_chi_id"] == criterion_id and row["finding"] == finding
        ]
        if len(matches) != 1:
            raise ValueError(f"Expected one decision rule for {criterion_id}/{finding}")
        return matches[0]

    def legal_basis(self, criterion):
        version_id = criterion["requirement_version_id"]
        version = self.versions.get(version_id, {})
        article_id = criterion.get("source_dieu_khoan_id")
        document_id = version.get("source_van_ban_id")
        if article_id not in self.articles or document_id not in self.documents:
            return []
        return [version_id, article_id, document_id]


@pytest.fixture
def reasoning_case():
    knowledge = InMemoryKnowledge()
    quote = "Bên bán và bên mua đã được xác định."
    prefix = "Điều 1. "
    data = {
        "ca_id": "CASE_1",
        "phien_ban_id": "DEPLOYMENT_TEST",
        "rule_version": "RULE_TEST",
        "legal_knowledge_version": "LEGAL_TEST",
        "knowledge_snapshot_sha256": knowledge.sha256,
        "run_id": "RUN_1",
        "trace_id": "TRACE_1",
        "payload": {
            "hop_dong_id": "CONTRACT_1",
            "requirements": [
                {
                    "yeu_cau_ca_id": "CASE_REQUIREMENT_1",
                    "ca_id": "CASE_1",
                    "requirement_id": "REQUIREMENT_1",
                    "requirement_version_id": "VERSION_1",
                    "scope_status": "MATCH",
                    "version_status": "RESOLVED",
                    "applicability_status": "CONFIRMED",
                    "moc_ap_dung": "2026-01-15",
                    "phien_ban_id": "DEPLOYMENT_TEST",
                }
            ],
            "chunks": [
                {
                    "doan_id": "CHUNK_1",
                    "hop_dong_id": "CONTRACT_1",
                    "noi_dung": prefix + quote + " Điều khoản tiếp theo.",
                    "page_start": 2,
                    "page_end": 2,
                }
            ],
            "retrieval": [
                {
                    "truy_xuat_id": "RETRIEVAL_1",
                    "yeu_cau_ca_id": "CASE_REQUIREMENT_1",
                    "tieu_chi_id": "CRITERION_1",
                    "doan_id": "CHUNK_1",
                    "giai_doan": "FINAL",
                    "thu_hang": 1,
                    "duoc_chon": True,
                    "retrieval_version": "RETRIEVAL_TEST",
                    "index_version": "INDEX_TEST",
                    "lan_chay_id": "RUN_1",
                }
            ],
            "observations": [
                {
                    "tieu_chi_id": "CRITERION_1",
                    "proposed_finding": "SATISFIED",
                    "giai_thich": "The verified provider matched this passage to this criterion.",
                    "gates": {
                        "evidence_validated": True,
                        "source_verified": True,
                        "scope_confirmed": True,
                        "version_resolved": True,
                        "exceptions_resolved": True,
                        "evidence_conflict": False,
                    },
                    "evidence": [
                        {
                            "doan_id": "CHUNK_1",
                            "trich_dan": quote,
                            "ky_tu_bat_dau": len(prefix),
                            "ky_tu_ket_thuc": len(prefix) + len(quote),
                        }
                    ],
                    "local_applicability": "MATCH",
                    "mandatory_confirmed": True,
                    "all_pages_readable": True,
                    "all_related_documents_received": True,
                    "model_version": "PROVIDER_TEST_V1",
                    "prompt_version": "PROMPT_TEST_V1",
                }
            ],
        },
    }
    return knowledge, data


def only_result(knowledge, data):
    results = reason(ReasoningRequest.model_validate(data), knowledge)
    assert len(results) == 1
    result = results[0]
    assert isinstance(result, CriterionResult)
    return result


def assert_unknown(result, *concepts):
    assert result.finding == "UNKNOWN"
    assert result.uncertainty_reason and result.uncertainty_reason.strip()
    if concepts:
        assert any(concept in result.uncertainty_reason.lower() for concept in concepts)


@pytest.mark.parametrize("json_text", [False, True], ids=["jsonb", "json-text"])
def test_satisfied_requires_structured_proposal_and_verified_attributable_evidence(
    reasoning_case, json_text
):
    knowledge, data = reasoning_case
    if json_text:
        rule = knowledge.decision("CRITERION_1", "SATISFIED")
        rule["dieu_kien_json"] = json.dumps(rule["dieu_kien_json"])

    result = only_result(knowledge, data)

    assert result.finding == "SATISFIED"
    assert result.uncertainty_reason is None
    assert result.gates.reliable()
    # Absence gates are not prerequisites for a positive, evidenced finding.
    assert not result.gates.coverage_complete
    assert not result.gates.absence_verified
    assert result.legal_basis_ids == ["VERSION_1", "ARTICLE_1", "DOCUMENT_1"]


def test_result_preserves_provenance_and_does_not_mutate_inputs(reasoning_case):
    knowledge, data = reasoning_case
    request = ReasoningRequest.model_validate(data)
    request_before = request.model_dump(mode="json")
    knowledge_before = deepcopy(vars(knowledge))

    result = reason(request, knowledge)[0]

    assert request.model_dump(mode="json") == request_before
    assert vars(knowledge) == knowledge_before
    assert result.ca_id == request.ca_id
    assert result.yeu_cau_ca_id == "CASE_REQUIREMENT_1"
    assert result.tieu_chi_id == "CRITERION_1"
    assert result.lan_chay_id == request.run_id
    assert result.pham_vi_ket_luan == "CURRENT_CRITERION"
    assert result.review_status == "PENDING"
    assert result.mandatory is True
    assert result.excluded is False
    assert result.evidence == request.payload.observations[0].evidence
    assert result.giai_thich == request.payload.observations[0].giai_thich
    assert result.model_version == "PROVIDER_TEST_V1"
    assert result.prompt_version == "PROMPT_TEST_V1"
    assert all(
        result.tieu_chi_snapshot_json[key] == value
        for key, value in knowledge.criteria["CRITERION_1"].items()
    )
    assert result.ket_qua_id
    assert reason(request, knowledge)[0].ket_qua_id == result.ket_qua_id

    result.tieu_chi_snapshot_json["noi_dung"] = "Changed result snapshot"
    result.gates.scope_confirmed = False
    result.evidence[0].trich_dan = "Changed result evidence"
    assert vars(knowledge) == knowledge_before
    assert request.model_dump(mode="json") == request_before


def test_rule_release_can_differ_from_the_request_deployment_version(reasoning_case):
    knowledge, data = reasoning_case
    knowledge.decision("CRITERION_1", "SATISFIED")["rule_version"] = "INDEPENDENT_RULE_RELEASE"

    assert only_result(knowledge, data).finding == "SATISFIED"


def test_absent_numeric_rule_is_supported_for_contract_content(reasoning_case):
    knowledge, data = reasoning_case
    knowledge.decision("CRITERION_1", "SATISFIED")["dieu_kien_json"].pop("numeric_rule")

    assert only_result(knowledge, data).finding == "SATISFIED"


def test_each_expected_criterion_has_an_independent_stable_result_even_without_observation(
    reasoning_case,
):
    knowledge, data = reasoning_case
    second = deepcopy(knowledge.criteria["CRITERION_1"])
    second.update(tieu_chi_id="CRITERION_2", thu_tu=2, noi_dung="A second independent criterion.")
    knowledge.criteria["CRITERION_2"] = second
    knowledge.tables["tieu_chi_danh_gia"].append(second)
    request = ReasoningRequest.model_validate(data)

    results = reason(request, knowledge)
    repeated = reason(request, knowledge)

    assert {result.tieu_chi_id for result in results} == {"CRITERION_1", "CRITERION_2"}
    assert len({result.ket_qua_id for result in results}) == 2
    assert {result.tieu_chi_id: result.ket_qua_id for result in results} == {
        result.tieu_chi_id: result.ket_qua_id for result in repeated
    }
    by_criterion = {result.tieu_chi_id: result for result in results}
    assert by_criterion["CRITERION_1"].finding == "SATISFIED"
    assert_unknown(by_criterion["CRITERION_2"])
    assert by_criterion["CRITERION_2"].evidence == []
    assert all(
        by_criterion["CRITERION_2"].tieu_chi_snapshot_json[key] == value
        for key, value in second.items()
    )


@pytest.mark.parametrize(
    "gate,value,concepts",
    [
        ("scope_confirmed", False, ("scope", "phạm vi")),
        ("source_verified", False, ("source", "nguồn")),
        ("version_resolved", False, ("version", "phiên bản")),
        ("evidence_validated", False, ("evidence", "bằng chứng")),
        ("exceptions_resolved", False, ("exception", "ngoại lệ")),
        ("evidence_conflict", True, ("conflict", "mâu thuẫn")),
    ],
)
def test_each_unresolved_observation_gate_has_a_concrete_unknown_reason(
    reasoning_case, gate, value, concepts
):
    knowledge, data = reasoning_case
    data["payload"]["observations"][0]["gates"][gate] = value

    assert_unknown(only_result(knowledge, data), *concepts)


@pytest.mark.parametrize(
    "updates",
    [
        {"scope_status": "UNKNOWN", "applicability_status": "UNKNOWN"},
        {"version_status": "UNKNOWN", "applicability_status": "UNKNOWN"},
        {"applicability_status": "UNKNOWN"},
    ],
)
def test_unconfirmed_c05_cannot_be_overridden_by_reliable_observation(reasoning_case, updates):
    knowledge, data = reasoning_case
    data["payload"]["requirements"][0].update(updates)

    if updates.get("version_status") == "UNKNOWN":
        assert reason(ReasoningRequest.model_validate(data), knowledge) == []
    else:
        assert_unknown(only_result(knowledge, data))


@pytest.mark.parametrize("local_applicability", ["NO_MATCH", "UNKNOWN"])
def test_local_applicability_must_match_the_current_criterion(reasoning_case, local_applicability):
    knowledge, data = reasoning_case
    data["payload"]["observations"][0]["local_applicability"] = local_applicability

    assert_unknown(only_result(knowledge, data))


def test_missing_observation_still_returns_a_criterion_result(reasoning_case):
    knowledge, data = reasoning_case
    data["payload"]["observations"] = []

    assert_unknown(only_result(knowledge, data), "observation", "quan sát", "nhận định")


def test_no_keyword_or_prose_matching_without_a_satisfied_proposal(reasoning_case):
    knowledge, data = reasoning_case
    data["payload"]["observations"][0].update(
        proposed_finding="UNKNOWN",
        giai_thich="SATISFIED: all words match and the text says it meets the criterion.",
    )
    knowledge.criteria["CRITERION_1"]["noi_dung"] = data["payload"]["chunks"][0]["noi_dung"]

    assert_unknown(only_result(knowledge, data))


@pytest.mark.parametrize("proposal", ["VIOLATED", "MISSING"])
def test_reviewed_violated_and_missing_proposals_use_their_own_rule(reasoning_case, proposal):
    knowledge, data = reasoning_case
    observation = data["payload"]["observations"][0]
    observation["proposed_finding"] = proposal
    observation["gates"].update(coverage_complete=True, absence_verified=True)

    result = only_result(knowledge, data)
    assert result.finding == proposal
    assert result.tieu_chi_snapshot_json["decision_rule_snapshot_json"]["finding"] == proposal


def test_evidence_is_required_even_with_all_reliability_gates(reasoning_case):
    knowledge, data = reasoning_case
    data["payload"]["observations"][0]["evidence"] = []

    assert_unknown(only_result(knowledge, data), "evidence", "bằng chứng")


def test_unicode_and_newlines_use_exact_original_character_offsets(reasoning_case):
    knowledge, data = reasoning_case
    prefix = "Điều 1.\n😀 "
    quote = "Bên bán: Công ty Ánh Dương.\nBên mua: Nguyễn Thị Hà."
    data["payload"]["chunks"][0]["noi_dung"] = prefix + quote + "\n\nĐiều 2."
    data["payload"]["observations"][0]["evidence"][0].update(
        trich_dan=quote,
        ky_tu_bat_dau=len(prefix),
        ky_tu_ket_thuc=len(prefix) + len(quote),
    )

    result = only_result(knowledge, data)

    assert result.finding == "SATISFIED"
    assert result.evidence[0].trich_dan == quote
    assert result.evidence[0].ky_tu_bat_dau == len(prefix)
    assert result.evidence[0].ky_tu_ket_thuc == len(prefix) + len(quote)


@pytest.mark.parametrize(
    "updates,concept",
    [
        ({"facts": {"identity": None}, "facts_verified": True}, "fact"),
        ({"facts": {"identity": "unverified"}, "facts_verified": False}, "fact"),
        ({"template_field_unfilled": True}, "template"),
    ],
)
def test_unresolved_current_criterion_facts_or_template_fields_are_unknown(
    reasoning_case, updates, concept
):
    knowledge, data = reasoning_case
    data["payload"]["observations"][0].update(updates)

    assert_unknown(only_result(knowledge, data), concept)


@pytest.mark.parametrize("retrieval_state", ["absent", "not-selected", "not-final"])
def test_only_selected_final_retrieval_can_support_the_current_criterion(
    reasoning_case, retrieval_state
):
    knowledge, data = reasoning_case
    retrieval = data["payload"]["retrieval"]
    if retrieval_state == "absent":
        retrieval.clear()
    elif retrieval_state == "not-selected":
        retrieval[0]["duoc_chon"] = False
    else:
        retrieval[0]["giai_doan"] = "CANDIDATE"

    assert_unknown(
        only_result(knowledge, data), "retrieval", "c06", "selected", "truy xuất", "evidence"
    )


@pytest.mark.parametrize(
    "updates",
    [
        {"trich_dan": "This quote does not occur in the source."},
        {"ky_tu_bat_dau": 0},
        {"ky_tu_ket_thuc": 10000},
        {"doan_id": "UNKNOWN_CHUNK"},
    ],
    ids=["wrong-quote", "wrong-start-offset", "out-of-bounds-end", "unknown-chunk"],
)
def test_invalid_evidence_provenance_is_rejected(reasoning_case, updates):
    knowledge, data = reasoning_case
    data["payload"]["observations"][0]["evidence"][0].update(updates)

    with pytest.raises(ValueError):
        only_result(knowledge, data)


@pytest.mark.parametrize(
    "collection,field,value",
    [
        ("requirements", "ca_id", "OTHER_CASE"),
        ("requirements", "phien_ban_id", "OTHER_DEPLOYMENT"),
        ("requirements", "requirement_id", "OTHER_REQUIREMENT"),
        ("chunks", "hop_dong_id", "OTHER_CONTRACT"),
        ("observations", "tieu_chi_id", "UNKNOWN_CRITERION"),
        ("retrieval", "yeu_cau_ca_id", "UNKNOWN_CASE_REQUIREMENT"),
        ("retrieval", "tieu_chi_id", "UNKNOWN_CRITERION"),
        ("retrieval", "doan_id", "UNKNOWN_CHUNK"),
        ("retrieval", "lan_chay_id", "OTHER_RUN"),
    ],
)
def test_foreign_context_and_dangling_payload_identifiers_are_rejected(
    reasoning_case, collection, field, value
):
    knowledge, data = reasoning_case
    data["payload"][collection][0][field] = value

    with pytest.raises(ValueError):
        only_result(knowledge, data)


def test_snapshot_hash_must_match_the_supplied_knowledge(reasoning_case):
    knowledge, data = reasoning_case
    data["knowledge_snapshot_sha256"] = "b" * 64

    with pytest.raises(ValueError):
        only_result(knowledge, data)


def test_unresolved_legal_basis_is_unknown(reasoning_case):
    knowledge, data = reasoning_case
    knowledge.articles.clear()

    assert_unknown(only_result(knowledge, data), "legal", "source", "căn cứ", "nguồn")


def test_legal_article_must_belong_to_the_resolved_document(reasoning_case):
    knowledge, data = reasoning_case
    knowledge.documents["OTHER_DOCUMENT"] = {"van_ban_id": "OTHER_DOCUMENT"}
    knowledge.articles["ARTICLE_1"]["van_ban_id"] = "OTHER_DOCUMENT"

    assert_unknown(only_result(knowledge, data))


def test_performance_criterion_without_execution_documents_stays_unknown(reasoning_case):
    knowledge, data = reasoning_case
    knowledge.criteria["CRITERION_1"]["loai_kiem_tra"] = "PERFORMANCE_WITH_DOCUMENTS"

    assert_unknown(only_result(knowledge, data))


def test_review_flags_are_preserved_without_marking_draft_human_approved(reasoning_case):
    knowledge, data = reasoning_case
    knowledge.criteria["CRITERION_1"]["human_verified"] = False
    knowledge.decision("CRITERION_1", "SATISFIED")["human_verified"] = False

    result = only_result(knowledge, data)

    assert result.tieu_chi_snapshot_json["human_verified"] is False
    assert result.tieu_chi_snapshot_json["decision_rule_snapshot_json"]["human_verified"] is False
    assert knowledge.criteria["CRITERION_1"]["human_verified"] is False
    assert knowledge.decision("CRITERION_1", "SATISFIED")["human_verified"] is False
    assert result.review_status == "PENDING"


def test_missing_decision_rule_fails_closed_as_unknown(reasoning_case):
    knowledge, data = reasoning_case
    knowledge.tables["quy_tac_quyet_dinh"] = []

    assert_unknown(only_result(knowledge, data), "rule", "quy tắc")


def test_duplicate_satisfied_rules_are_ambiguous(reasoning_case):
    knowledge, data = reasoning_case
    duplicate = deepcopy(knowledge.decision("CRITERION_1", "SATISFIED"))
    duplicate["quy_tac_id"] = "SECOND_SATISFIED_RULE"
    knowledge.tables["quy_tac_quyet_dinh"].append(duplicate)

    assert_unknown(only_result(knowledge, data), "rule")


def test_unknown_top_level_rule_conditions_are_not_silently_ignored(reasoning_case):
    knowledge, data = reasoning_case
    knowledge.decision("CRITERION_1", "SATISFIED")["dieu_kien_json"]["extra_condition"] = True

    assert_unknown(only_result(knowledge, data), "unsupported")


def test_evidence_selected_for_another_valid_criterion_cannot_be_reused(reasoning_case):
    knowledge, data = reasoning_case
    second = deepcopy(knowledge.criteria["CRITERION_1"])
    second.update(tieu_chi_id="CRITERION_2", thu_tu=2)
    knowledge.criteria["CRITERION_2"] = second
    knowledge.tables["tieu_chi_danh_gia"].append(second)
    data["payload"]["retrieval"][0]["tieu_chi_id"] = "CRITERION_2"

    # Ownership mismatch is malformed input, not merely missing retrieval.
    with pytest.raises(ValueError, match="another criterion"):
        reason(ReasoningRequest.model_validate(data), knowledge)


@pytest.mark.parametrize(
    "conditions",
    [None, "{invalid json", "[]", [], True, 1, {}, {"enabled": False}],
    ids=["null", "bad-json", "json-array", "array", "bool", "number", "empty", "disabled"],
)
def test_missing_disabled_or_malformed_rule_conditions_are_unknown(reasoning_case, conditions):
    knowledge, data = reasoning_case
    knowledge.decision("CRITERION_1", "SATISFIED")["dieu_kien_json"] = conditions

    assert_unknown(only_result(knowledge, data), "rule", "quy tắc", "condition", "điều kiện")


@pytest.mark.parametrize(
    "field,value",
    [
        ("numeric_rule", {"operator": "eval", "expression": "1 / 0"}),
        ("scope_of_facts", "ENTIRE_CONTRACT"),
        ("criterion_target_only", False),
        ("enabled", "true"),
        ("gate", {"unsupported_gate": True}),
        ("gate", {"scope_confirmed": "true"}),
        ("gate", {"scope_confirmed": 1}),
        ("gate", {"scope_confirmed": None}),
    ],
)
def test_unsupported_rule_shapes_are_unknown_without_execution(reasoning_case, field, value):
    knowledge, data = reasoning_case
    knowledge.decision("CRITERION_1", "SATISFIED")["dieu_kien_json"][field] = value

    assert_unknown(only_result(knowledge, data))


def test_free_text_predicate_is_never_executed(reasoning_case, monkeypatch):
    knowledge, data = reasoning_case
    conditions = knowledge.decision("CRITERION_1", "SATISFIED")["dieu_kien_json"]
    conditions["predicate"] = "__import__('builtins').criterion_reasoner_eval_probe()"

    def forbidden_execution():
        pytest.fail("Rule prose must never be evaluated as Python")

    monkeypatch.setattr(
        "builtins.criterion_reasoner_eval_probe", forbidden_execution, raising=False
    )

    assert only_result(knowledge, data).finding == "SATISFIED"


def test_unverified_external_evidence_cannot_bypass_reliability(reasoning_case):
    knowledge, data = reasoning_case
    data["payload"]["observations"][0]["external_evidence"] = [
        {
            "bang_chung_id": "EXTERNAL_1",
            "object_uri": "memory://fixture",
            "sha256": "c" * 64,
            "verified": False,
        }
    ]

    assert_unknown(only_result(knowledge, data), "external", "verified", "ngoài", "xác minh")
