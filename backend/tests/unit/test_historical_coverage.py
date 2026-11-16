"""A later source branch may be excluded only when a reviewed legacy branch covers it."""

import json
from copy import deepcopy
from datetime import date
from types import SimpleNamespace

import pytest
from legal_checker.modules.applicable_law.historical_coverage import (
    historical_exclusion_valid,
    resolve_historical_branches,
)
from legal_checker.modules.legal_knowledge import runtime_alignment
from legal_checker.modules.legal_knowledge.repository import canonical
from legal_checker.shared.contracts.temporal import ApplicableRequirement


def case():
    policy = dict(
        policy_id="LEGAL_VERSION_POLICY_V1",
        review_scope="CONTRACT_AT_CONCLUSION",
        selection_marker="SIGNING",
        transition="SOURCE_INTERVAL",
        source_article_ids=["A"],
        source_urls=["https://example.org/synthetic-unit-source"],
        criteria_ready=True,
        notes="Synthetic test only",
        historical_equivalent_family_id="LEGACY",
        historical_basis_article_ids=["A"],
    )
    versions = {
        "L": dict(
            requirement_version_id="L",
            requirement_id="LEGACY",
            hieu_luc_tu="2012-01-01",
            hieu_luc_den="2024-01-01",
        ),
        "M1": dict(
            requirement_version_id="M1",
            requirement_id="MODERN",
            hieu_luc_tu="2024-01-01",
            quy_tac_chuyen_tiep=json.dumps(policy),
        ),
        "M2": dict(
            requirement_version_id="M2",
            requirement_id="MODERN",
            hieu_luc_tu="2025-01-01",
            quy_tac_chuyen_tiep=json.dumps(policy),
        ),
    }
    k = SimpleNamespace(sha256="a" * 64, versions=versions, articles={"A": {}})
    common = dict(ca_id="CA", moc_ap_dung=date(2017, 2, 16), phien_ban_id="P")
    legacy = ApplicableRequirement(
        **common,
        yeu_cau_ca_id="R_L",
        requirement_id="LEGACY",
        requirement_version_id="L",
        scope_status="MATCH",
        version_status="RESOLVED",
        applicability_status="CONFIRMED",
    )
    modern = ApplicableRequirement(
        **common,
        yeu_cau_ca_id="R_M",
        requirement_id="MODERN",
        scope_status="UNKNOWN",
        version_status="UNKNOWN",
        applicability_status="UNKNOWN",
    )
    return k, [legacy, modern]


def test_equivalent_legacy_is_retained_and_modern_branch_excluded_with_proof():
    k, rows = case()
    before = deepcopy(rows)
    output = resolve_historical_branches(rows, k)
    assert output[0].confirmed
    assert output[1].applicability_status == "NOT_APPLICABLE"
    assert historical_exclusion_valid(output[1], k)
    assert rows == before


@pytest.mark.parametrize(
    "fault", ["unresolved", "no_policy", "missing_source", "outside_legacy", "active_modern"]
)
def test_cannot_hide_catalog_gap_without_valid_legacy_coverage(fault):
    k, rows = case()
    if fault == "unresolved":
        rows[0] = rows[0].model_copy(
            update=dict(scope_status="UNKNOWN", applicability_status="UNKNOWN")
        )
    if fault == "no_policy":
        k.versions["M1"].pop("quy_tac_chuyen_tiep")
    if fault == "missing_source":
        k.articles = {}
    if fault == "outside_legacy":
        k.versions["L"]["hieu_luc_tu"] = "2020-01-01"
    if fault == "active_modern":
        k.versions["M1"]["hieu_luc_tu"] = "2015-01-01"
    assert resolve_historical_branches(rows, k)[1].applicability_status == "UNKNOWN"


def test_forged_snapshot_pin_invalidates_coverage_proof():
    k, rows = case()
    r = resolve_historical_branches(rows, k)[1]
    r.nguon_snapshot_json["historical_coverage"]["knowledge_sha256"] = "b" * 64
    assert not historical_exclusion_valid(r, k)


def test_catalog_revision_is_additive_and_checks_exact_base(monkeypatch):
    basis = [a for _, articles in runtime_alignment.HISTORICAL.values() for a in articles]
    base = {
        "schema_version": "synthetic-test",
        "tables": {
            "dieu_khoan_phap_ly": [dict(dieu_khoan_id=a) for a in basis],
            "phien_ban_yeu_cau": [
                dict(requirement_id=family, quy_tac_chuyen_tiep="{}")
                for family in list(runtime_alignment.HISTORICAL)
                + [v[0] for v in runtime_alignment.HISTORICAL.values()]
            ],
            "pham_vi_ap_dung": [dict(requirement_id="FAM_APT_DEPOSIT", dieu_kien_json={"all": []})],
        },
    }
    import hashlib

    monkeypatch.setattr(
        runtime_alignment, "BASE_SHA", hashlib.sha256(canonical(base).encode()).hexdigest()
    )
    old = deepcopy(base)
    new = runtime_alignment.revised_content(base)
    assert base == old and new != old
    assert new["schema_version"] == base["schema_version"]
    assert new["catalog_revision"] == runtime_alignment.REVISION
    assert (
        new["tables"]["pham_vi_ap_dung"][0]["dieu_kien_json"]["all"][0]["field"]
        == "co_thoa_thuan_dat_coc"
    )
    assert runtime_alignment.revised_content(base) == new
    base["schema_version"] = "changed"
    with pytest.raises(ValueError, match="exact TEAM"):
        runtime_alignment.revised_content(base)
