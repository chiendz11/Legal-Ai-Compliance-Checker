"""Seeded scope clauses nest `any` inside `all` (e.g. che_do_giao_dich alternatives)."""

from legal_checker.modules.applicable_law.scope_resolver import evaluate_clause
from legal_checker.shared.contracts.document_intelligence import ContractProfile

CLAUSE = {
    "pham_vi_id": "SCOPE_TEST",
    "nhom_phien_ban": "TEST",
    "dieu_kien_json": {
        "all": [
            {"field": "doi_tuong", "op": "EQ", "value": "NHA_O"},
            {
                "any": [
                    {"field": "che_do_giao_dich", "op": "EQ", "value": "LUAT_NHA_O"},
                    {"field": "che_do_giao_dich", "op": "EQ", "value": "BAN_LAI_CA_NHAN"},
                ]
            },
        ]
    },
}


def status_for(**fields):
    profile = ContractProfile(hop_dong_id="HD_TEST", profile=fields)
    return evaluate_clause(CLAUSE, profile, {}).status


def test_nested_any_matches_when_one_alternative_matches():
    assert status_for(doi_tuong="NHA_O", che_do_giao_dich="BAN_LAI_CA_NHAN") == "MATCH"


def test_nested_any_is_no_match_only_when_every_alternative_fails():
    assert status_for(doi_tuong="NHA_O", che_do_giao_dich="KINH_DOANH_BDS") == "NO_MATCH"


def test_unknown_alternative_keeps_the_clause_unknown():
    assert status_for(doi_tuong="NHA_O") == "UNKNOWN"
