"""Identity uses observed year/explicit references, never the latest active law."""

from copy import deepcopy
from datetime import date
from types import SimpleNamespace

import pytest
from legal_checker.modules.citation_validation.service import CatalogCitationValidator
from test_citation_validator import CONTEXT, DOCUMENTS, KNOWLEDGE, citation, profile


def validate(items, *, documents=None, signed=date(2020, 1, 1)):
    knowledge = SimpleNamespace(
        documents=documents or DOCUMENTS,
        tables=KNOWLEDGE.tables,
        sha256=CONTEXT.knowledge_snapshot_sha256,
    )
    return CatalogCitationValidator().validate(CONTEXT, profile(signed), items, knowledge)


def test_title_year_identifies_historical_version_without_choosing_current_law():
    item = citation(title="Luật Nhà ở")
    item.normalized.nam = 2014
    [result] = validate([item], signed=date(2025, 1, 1))
    assert result.normalized_van_ban_id == "LNO_2014" and result.status == "STALE"
    assert not result.source_snapshot_json["catalog_number_matched"]
    assert (
        result.source_snapshot_json["checks"]["identity"]["reason_code"]
        == "CATALOG_TITLE_YEAR_MATCH"
    )
    assert item.normalized.so_hieu is None


@pytest.mark.parametrize("year", [1990, 2022])
def test_unknown_title_year_cannot_borrow_a_nearby_year(year):
    item = citation(title="Luật Nhà ở")
    item.normalized.nam = year
    [result] = validate([item])
    assert result.status == "UNKNOWN" and result.normalized_van_ban_id is None


def test_multiple_title_year_candidates_stay_unknown():
    docs = deepcopy(DOCUMENTS)
    docs["OTHER"] = {
        **docs["LNO_2014"],
        "van_ban_id": "OTHER",
        "so_hieu": "1/2014/QH13",
        "so_hieu_chuan": "1/2014/QH13",
    }
    item = citation(title="Luật Nhà ở")
    item.normalized.nam = 2014
    [result] = validate([item], documents=docs)
    assert result.status == "UNKNOWN"


def test_static_reference_uses_unique_explicit_number_in_same_contract():
    anchor = citation("65/2014/QH13", "Luật Nhà ở", vien_dan_id="ANCHOR")
    short = citation(title="Luật Nhà ở", status="AMBIGUOUS", vien_dan_id="SHORT")
    [_, result] = validate([anchor, short])
    assert result.status == "VALID" and result.finding_verified
    assert result.normalized_van_ban_id == "LNO_2014"
    assert result.source_snapshot_json["checks"]["identity"]["anchor_citation_ids"] == ["ANCHOR"]
    assert short.normalized.so_hieu is None and short.extraction.status == "AMBIGUOUS"
    assert not result.source_snapshot_json["catalog_number_matched"]


def test_competing_explicit_versions_cannot_be_selected_by_signing_date():
    old = citation("65/2014/QH13", "Luật Nhà ở", vien_dan_id="OLD")
    new = citation("27/2023/QH15", "Luật Nhà ở", vien_dan_id="NEW")
    short = citation(title="Luật Nhà ở", status="AMBIGUOUS", vien_dan_id="SHORT")
    assert validate([old, new, short])[-1].status == "UNKNOWN"


@pytest.mark.parametrize(
    "raw", ["Luật Nhà ở hiện hành", "Luật Nhà ở và các văn bản thay thế từng thời điểm"]
)
def test_dynamic_reference_is_not_rebound_to_a_static_number(raw):
    anchor = citation("65/2014/QH13", "Luật Nhà ở", vien_dan_id="ANCHOR")
    short = citation(title="Luật Nhà ở", status="AMBIGUOUS", vien_dan_id="SHORT")
    short.raw_text = raw
    assert validate([anchor, short])[-1].status == "UNKNOWN"


def test_unverified_anchor_or_partial_catalog_does_not_attest_identity():
    docs = {"LNO_2014": {**DOCUMENTS["LNO_2014"], "identity_verified": False}}
    anchor = citation("65/2014/QH13", "Luật Nhà ở", vien_dan_id="ANCHOR")
    short = citation(title="Luật Nhà ở", status="AMBIGUOUS", vien_dan_id="SHORT")
    assert validate([anchor, short], documents=docs)[-1].status == "UNKNOWN"
    assert validate([short], documents={"LNO_2014": DOCUMENTS["LNO_2014"]})[0].status == "UNKNOWN"


def test_number_year_conflict_is_not_silently_corrected():
    item = citation("65/2014/QH13", "Luật Nhà ở")
    item.normalized.nam = 2023
    [result] = validate([item])
    assert result.status == "INVALID" and result.reason_code == "NUMBER_YEAR_MISMATCH"


def test_reviewed_title_alias_can_match_an_observed_year_but_not_an_unrelated_title():
    docs = {
        "CONSUMER": {
            **DOCUMENTS["LNO_2014"],
            "van_ban_id": "CONSUMER",
            "so_hieu": "59/2010/QH12",
            "so_hieu_chuan": "59/2010/QH12",
            "ten_van_ban": "Luật Bảo vệ quyền lợi người tiêu dùng",
            "linh_vuc": "BVNTD_2010",
            "hieu_luc_tu": "2011-07-01",
            "hieu_luc_den": "2024-07-01",
        }
    }
    item = citation(title="Luật Bảo vệ người tiêu dùng")
    item.normalized.nam = 2010
    assert validate([item], documents=docs)[0].normalized_van_ban_id == "CONSUMER"
    item.normalized.ten_van_ban = "Luật Bảo vệ"
    assert validate([item], documents=docs)[0].status == "UNKNOWN"
