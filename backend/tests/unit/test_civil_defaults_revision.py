"""Independent statutory defaults must not become prohibited-clause rules."""

from copy import deepcopy

import pytest
from legal_checker.modules.legal_knowledge.content_defaults_revision import TARGETS, revised_content


def base_content():
    return {
        "schema_version": "test",
        "tables": {
            "van_ban_phap_ly": [{"van_ban_id": "LAW", "so_hieu": "91/2015/QH13"}],
            "dieu_khoan_phap_ly": [
                {"dieu_khoan_id": p["article"], "van_ban_id": "LAW"} for p in TARGETS.values()
            ],
            "tieu_chi_danh_gia": [
                {"tieu_chi_id": k, "source_dieu_khoan_id": p["article"], "human_verified": True}
                for k, p in TARGETS.items()
            ],
            "quy_tac_quyet_dinh": [
                {
                    "tieu_chi_id": k,
                    "finding": f,
                    "human_verified": True,
                    "dieu_kien_json": {"enabled": True, "predicate": "old"},
                }
                for k in TARGETS
                for f in ("SATISFIED", "VIOLATED")
            ],
        },
    }


def test_revision_is_additive_and_never_invents_human_review():
    source = base_content()
    original = deepcopy(source)
    result = revised_content(source)
    assert source == original
    assert len(result["parent_snapshot_sha256"]) == 64
    for rule in result["tables"]["quy_tac_quyet_dinh"]:
        assert rule["human_verified"] is False
        assert rule["trang_thai"] == "SOURCE_CHECKED"
        conditions = rule["dieu_kien_json"]
        assert conditions["conclusion_scope_required"]
        assert conditions["performance_requires_receipt_evidence"]
        if rule["finding"] == "VIOLATED":
            assert conditions["allowed_evaluation_targets"] == ["PERFORMANCE"]
        else:
            assert conditions["allowed_evaluation_targets"] == ["CONTRACT_CONTENT", "PERFORMANCE"]


def test_revision_refuses_different_law_even_when_ids_match():
    source = base_content()
    source["tables"]["van_ban_phap_ly"][0]["so_hieu"] = "OTHER_LAW"
    with pytest.raises(ValueError, match="legal basis"):
        revised_content(source)
