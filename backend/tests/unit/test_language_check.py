"""The "contract is in Vietnamese" criteria are decided by measurement, and only when safe."""

from copy import deepcopy

import pytest
from legal_checker.modules.compliance.backend_verification import contract_content_verifications
from legal_checker.modules.compliance.criterion_reasoner import reason
from legal_checker.modules.compliance.language_check import MARK, apply_language_check, measure
from legal_checker.modules.compliance.llm_observations import LLMObservationProvider
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.reasoning import ReasoningRequest
from legal_checker.shared.contracts.temporal import ApplicableRequirement
from test_backend_verification import CATALOGUE_CONDITIONS
from test_criterion_reasoner import reasoning_case as reasoning_case
from test_llm_observations import FakeClient, semantic

VIETNAMESE = (
    "Bên Bán có nghĩa vụ bàn giao căn hộ cho Bên Mua đúng thời hạn đã thỏa thuận trong "
    "hợp đồng này và cung cấp đầy đủ hồ sơ pháp lý liên quan đến căn hộ.\n"
) * 20
ENGLISH = (
    "The Seller shall deliver the Apartment to the Buyer within the time agreed by the "
    "Parties in this Agreement and provide all related documents.\n"
) * 20


def case(reasoning_case, text, rule="Ngôn ngữ sử dụng trong hợp đồng phải là tiếng Việt."):
    knowledge, data = reasoning_case
    knowledge.criteria["CRITERION_1"]["dieu_kien"] = deepcopy(CATALOGUE_CONDITIONS)
    knowledge.criteria["CRITERION_1"]["noi_dung"] = rule
    data["payload"]["chunks"][0]["noi_dung"] = text
    data["payload"]["observations"] = []
    return knowledge, data


def run(knowledge, data, ai=None):
    request = ReasoningRequest.model_validate(data)
    requirements = [
        ApplicableRequirement.model_validate(r) for r in data["payload"]["requirements"]
    ]
    context = Context.model_validate(request.model_dump(include=set(Context.model_fields)))
    verifications = contract_content_verifications(
        context, request.payload.hop_dong_id, requirements, knowledge
    )
    provider = LLMObservationProvider(
        FakeClient([ai]) if ai else None, automatic_draft_review=True, verifications=verifications
    )
    observations = apply_language_check(
        request, knowledge, provider.analyze(request, knowledge).observations
    )
    data = deepcopy(data)
    data["payload"]["observations"] = [o.model_dump() for o in observations]
    return reason(ReasoningRequest.model_validate(data), knowledge)[0]


def test_measure_separates_vietnamese_from_english_and_bilingual_text():
    assert measure([VIETNAMESE]).vietnamese_only
    assert not measure([ENGLISH]).vietnamese_only
    assert not measure([VIETNAMESE + ENGLISH]).vietnamese_only
    assert not measure(["Bên Bán bàn giao căn hộ."]).vietnamese_only  # too short to judge


def test_vietnamese_contract_satisfies_the_language_rule_without_ai(reasoning_case):
    result = run(*case(reasoning_case, VIETNAMESE))
    assert result.finding == "SATISFIED"
    assert MARK in result.giai_thich
    assert result.review_status == "PENDING"  # still a draft for the reviewer
    quote = result.evidence[0]
    assert VIETNAMESE[quote.ky_tu_bat_dau : quote.ky_tu_ket_thuc] == quote.trich_dan


@pytest.mark.parametrize("text", [ENGLISH, VIETNAMESE + ENGLISH], ids=["english", "bilingual"])
def test_foreign_or_bilingual_text_is_left_to_the_ai_and_reviewer(reasoning_case, text):
    assert run(*case(reasoning_case, text)).finding == "UNKNOWN"


def test_ai_disagreeing_with_the_measurement_is_not_accepted(reasoning_case):
    proposal = semantic(reasoning_case[1], proposed_finding="VIOLATED")
    knowledge, data = case(reasoning_case, VIETNAMESE)
    line = VIETNAMESE.splitlines()[0]
    ai = proposal | {"evidence": [{"doan_id": "CHUNK_1", "trich_dan": line, "ky_tu_bat_dau": 0}]}
    result = run(knowledge, data, ai)
    assert result.finding == "UNKNOWN"
    assert "không thống nhất" in (result.uncertainty_reason or result.giai_thich)


def test_judgement_criteria_about_language_are_not_measured(reasoning_case):
    rule = "Ngôn ngữ của hợp đồng giao kết với người tiêu dùng phải rõ ràng, dễ hiểu."
    assert run(*case(reasoning_case, VIETNAMESE, rule)).finding == "UNKNOWN"
