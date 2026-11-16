"""Finite content checks need real source facts and the exact run/criterion handoff."""

import json

import pytest
from legal_checker.modules.compliance.content_verifier import RECIPES, admit_content
from legal_checker.modules.compliance.criterion_reasoner import reason
from legal_checker.modules.compliance.verification import CriterionVerification
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.document_intelligence import ContractProfile
from legal_checker.shared.contracts.reasoning import ReasoningRequest
from test_criterion_reasoner import reasoning_case as reasoning_case

VALUES = {
    "maintenance_account_number": "TEST-MAINT-070",
    "maintenance_account_holder": "Công ty Mô Phỏng - kinh phí bảo trì",
    "maintenance_bank": "Ngân hàng mô phỏng",
    "dien_tich": "62.4",
    "gross_area_m2": "67.4",
    "land_address": "Ô đất TEST-01, Dự án Mô Phỏng, Hà Nội",
    "land_parcel_no": "TEST-001",
    "land_map_sheet": "TEST-TB-07",
    "land_area_m2": "10000",
    "dia_chi_ben_ban": "01 Đường Mô Phỏng, Hà Nội",
    "dia_chi_ben_mua": "80 Đường Mô Phỏng, Hà Nội",
    "maintenance_amount": "39936000",
    "maintenance_percent": "2",
    "warranty_months": "60",
    "warranty_start": "COMPLETION_AND_ACCEPTANCE_INTO_USE",
    "warranty_start_date": "2017-12-30",
    "acceptance_date": "2017-12-30",
    "ngay_ban_giao_du_kien": "2017-12-30",
}


def prepare(case, key):
    k, data = case
    version, names = RECIPES[key]
    c = k.criteria.pop("CRITERION_1")
    c.update(tieu_chi_id=key, requirement_version_id=version)
    k.criteria[key] = c
    v = k.versions.pop("VERSION_1")
    v["requirement_version_id"] = version
    k.versions[version] = v
    for row in k.tables["quy_tac_quyet_dinh"]:
        row["tieu_chi_id"] = key
    data = json.loads(json.dumps(data).replace("CRITERION_1", key).replace("VERSION_1", version))
    data["payload"]["observations"] = []
    labels = {
        "maintenance_account_number": "Tài khoản bảo trì",
        "maintenance_account_holder": "Tên tài khoản bảo trì",
        "maintenance_bank": "Ngân hàng tài khoản bảo trì",
        "dien_tich": "Diện tích sử dụng",
        "gross_area_m2": "Diện tích sàn xây dựng căn hộ",
        "land_address": "Vị trí thửa đất",
        "land_parcel_no": "Số thửa đất",
        "land_map_sheet": "Tờ bản đồ số",
        "land_area_m2": "Diện tích thửa đất",
        "dia_chi_ben_ban": "Địa chỉ bên bán",
        "dia_chi_ben_mua": "Địa chỉ bên mua",
        "maintenance_amount": "Số tiền kinh phí bảo trì",
        "maintenance_percent": "Tỷ lệ kinh phí bảo trì",
        "warranty_start_date": "Ngày bắt đầu bảo hành",
        "acceptance_date": "Ngày nghiệm thu hoàn thành đưa vào sử dụng",
        "ngay_ban_giao_du_kien": "Ngày bàn giao dự kiến",
    }
    lines = [
        labels[n] + ": " + VALUES[n]
        if n in labels
        else (
            "Thời gian bảo hành nhà ở là 60 tháng"
            if n == "warranty_months"
            else "tính từ ngày ký biên bản nghiệm thu đưa nhà ở vào sử dụng"
        )
        for n in names
    ]
    text = "\n".join(lines)
    data["payload"]["chunks"][0]["noi_dung"] = text
    request = ReasoningRequest.model_validate(data)
    facts = []
    evidence = []
    for n, line in zip(names, lines, strict=True):
        start = text.index(line)
        eid = "E_" + n
        facts.append(
            dict(
                trich_xuat_id="F_" + n,
                ten_truong=n,
                gia_tri_chuan_json=VALUES[n],
                trang_thai="EXTRACTED",
                phuong_phap="LITERAL",
                evidence_ids=[eid],
            )
        )
        evidence.append(
            dict(
                bang_chung_id=eid,
                doan_id="CHUNK_1",
                trich_dan=line,
                ky_tu_bat_dau=start,
                ky_tu_ket_thuc=start + len(line),
            )
        )
    profile = ContractProfile(
        hop_dong_id=request.payload.hop_dong_id, profile={}, facts=facts, evidence=evidence
    )
    record = CriterionVerification(
        **{
            n: getattr(request, n)
            for n in CriterionVerification.model_fields
            if n in Context.model_fields
        },
        hop_dong_id=profile.hop_dong_id,
        yeu_cau_ca_id=request.payload.requirements[0].yeu_cau_ca_id,
        tieu_chi_id=key,
        verification_reference="TEST_REVIEWED_SOURCE",
        local_applicability="MATCH",
        facts_verified=True,
        facts={"evaluation_target": "CONTRACT_CONTENT"},
        gates=dict(
            source_verified=True,
            scope_confirmed=True,
            version_resolved=True,
            exceptions_resolved=True,
        ),
    )
    return k, request, profile, [record]


@pytest.mark.parametrize("key", list(RECIPES))
def test_source_content_produces_draft_without_model_or_fake_human_review(reasoning_case, key):
    k, r, p, v = prepare(reasoning_case, key)
    r.payload.observations = admit_content(r, p, k, v)
    assert len(r.payload.observations) == 1
    result = reason(r, k)[0]
    assert result.finding == "SATISFIED", result.uncertainty_reason
    assert result.review_status == "PENDING"
    assert all(not f.human_verified for f in p.facts)


@pytest.mark.parametrize(
    "fault", ["missing", "conflict", "offset", "unselected", "run", "condition"]
)
def test_incomplete_or_wrong_context_does_not_produce_content_finding(reasoning_case, fault):
    k, r, p, v = prepare(reasoning_case, "TC_PV_HYC040_02")
    if fault == "missing":
        p.facts.pop()
    if fault == "conflict":
        p.facts[0].trang_thai = "CONFLICT"
    if fault == "offset":
        p.evidence[0].ky_tu_bat_dau += 1
    if fault == "unselected":
        r.payload.retrieval[0].duoc_chon = False
    if fault == "run":
        r.payload.retrieval[0].lan_chay_id = "OTHER"
    if fault == "condition":
        v[0].gates.exceptions_resolved = False
    assert admit_content(r, p, k, v) == []


def test_foreign_verifier_rejected(reasoning_case):
    k, r, p, v = prepare(reasoning_case, "TC_PV_HYC039_02")
    v[0].run_id = "OTHER"
    with pytest.raises(ValueError, match="context mismatch"):
        admit_content(r, p, k, v)


def test_c02_normalized_value_must_actually_match_the_quote(reasoning_case):
    k, r, p, v = prepare(reasoning_case, "TC_PV_HYC040_02")
    p.facts[0].gia_tri_chuan_json = "A fabricated address absent from the source"
    assert admit_content(r, p, k, v) == []


@pytest.mark.parametrize(
    "fault", ["payment_account_label", "missing_bank", "placeholder", "conflict"]
)
def test_account_content_requires_dedicated_attributable_nonempty_fields(reasoning_case, fault):
    k, r, p, v = prepare(reasoning_case, "TC_ACCOUNT_2015_03")
    if fault == "payment_account_label":
        p.evidence[0].trich_dan = p.evidence[0].trich_dan.replace(
            "Tài khoản bảo trì", "Tài khoản thanh toán"
        )
    elif fault == "missing_bank":
        p.facts.pop()
    elif fault == "conflict":
        p.facts[-1].trang_thai = "CONFLICT"
    else:
        p.facts[-1].gia_tri_chuan_json = "Chưa được cung cấp"
        old_quote = p.evidence[-1].trich_dan
        new_quote = "Ngân hàng tài khoản bảo trì: Chưa được cung cấp"
        r.payload.chunks[0].noi_dung = r.payload.chunks[0].noi_dung.replace(old_quote, new_quote)
        p.evidence[-1].trich_dan = new_quote
        p.evidence[-1].ky_tu_ket_thuc = p.evidence[-1].ky_tu_bat_dau + len(new_quote)
    assert admit_content(r, p, k, v) == []


def test_matching_gtc_phrases_do_not_automatically_make_a_semantic_finding(reasoning_case):
    from legal_checker.modules.compliance.content_verifier import content_candidates

    k, data = reasoning_case
    key = "TC_PV_HYC015_02"
    criterion = k.criteria.pop("CRITERION_1")
    criterion.update(
        tieu_chi_id=key, requirement_version_id="PV_HYC015", source_dieu_khoan_id="ART_VBPL008_18"
    )
    k.criteria[key] = criterion
    data = json.loads(
        json.dumps(data).replace("CRITERION_1", key).replace("VERSION_1", "PV_HYC015")
    )
    data["payload"]["observations"] = []
    data["payload"]["chunks"][0]["noi_dung"] = (
        "Kèm theo 01 (một) bản nội quy quản lý sử dụng nhà chung cư.\n"
        "Bản nội quy là một phần không thể tách rời của Hợp đồng mua bán căn hộ.\n"
        "Bản nội quy này có hiệu lực kể từ ngày được Chủ đầu tư ký ban hành."
    )
    r = ReasoningRequest.model_validate(data)
    p = ContractProfile(
        hop_dong_id=r.payload.hop_dong_id,
        profile=dict(
            loai_hop_dong_id="MB_CAN_HO_CHUNG_CU", muc_dich_giao_dich="TIEU_DUNG_KHONG_THUONG_MAI"
        ),
    )
    assert not content_candidates(p, r.payload.requirements, r.payload.chunks, k)
    assert admit_content(r, p, k, []) == []
