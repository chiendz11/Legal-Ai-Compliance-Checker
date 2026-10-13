"""Source-aligned scenario specs exercise real 5–7 engines with independent assertions."""

from collections import Counter
from datetime import date
from pathlib import Path

import pytest
from conftest import isolated_database
from devtools.database_schema import TABLES
from devtools.synthetic_scenarios import (
    SCENARIOS,
    Scenario,
    populate_scenario,
    reference_requirements,
)
from devtools.synthetic_workbook import assert_synthetic_response, citation_reference, compile_case
from legal_checker.core.postgres import connect_postgres
from legal_checker.modules.legal_knowledge.repository import Knowledge
from legal_checker.shared.contracts.common import Context
from legal_checker.workflows.steps_5_7 import evaluate


@pytest.fixture(scope="module")
def synthetic_knowledge():
    with isolated_database() as url:
        with connect_postgres(url) as connection:
            connection.execute((Path(__file__).parents[1] / "synthetic_knowledge.sql").read_text())
            connection.execute("SET CONSTRAINTS ALL IMMEDIATE")
        yield Knowledge(url)


@pytest.fixture
def vietnamese_font():
    paths = (
        "/usr/share/fonts/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    )
    font = next((Path(p) for p in paths if Path(p).is_file()), None)
    if font is None:
        pytest.skip("Source PDF test needs a Vietnamese Unicode TrueType font")
    return font


def scenario(name):
    s = Scenario("CA90_001", "ORIGINAL_DOC", "ORIGINAL_GROUP", "DEV", name, 1)
    populate_scenario(s, 0)
    return s


@pytest.mark.parametrize("name", SCENARIOS)
def test_authored_scenario_and_grounded_handoffs(
    synthetic_knowledge, tmp_path, vietnamese_font, name
):
    knowledge = synthetic_knowledge
    data = {t.name: [] for t in TABLES}
    request, document, case, assertions = compile_case(
        scenario(name), knowledge, tmp_path, vietnamese_font, data
    )
    assert_synthetic_response(assertions, evaluate(request, knowledge))
    assert (tmp_path / "synthetic/CA90_001.pdf").read_bytes().startswith(b"%PDF")
    chunks = {c.doan_id: c.noi_dung for c in document.chunks}
    for evidence in document.contract_profile.evidence:
        assert (
            chunks[evidence.doan_id][evidence.ky_tu_bat_dau : evidence.ky_tu_ket_thuc]
            == evidence.trich_dan
        )
    assert all(not f.human_verified for f in document.contract_profile.facts)
    assert case.hop_dong_id.startswith("SYN_")
    assert all(name not in c.noi_dung for c in document.chunks)


def test_event_dates_and_half_open_temporal_boundary(synthetic_knowledge):
    knowledge = synthetic_knowledge
    s = scenario("CLEAN_DOMESTIC")
    s.markers["SIGNING"] = date(2024, 7, 31)
    s.markers["COLLECTION"] = date(2024, 8, 1)
    reqs = {r.requirement_id: r for r in reference_requirements(s, knowledge)}
    payment = reqs["FAM_FIRST_PAYMENT_CAP"]
    assert payment.requirement_version_id == "PV_GYC062"
    assert payment.moc_ap_dung == date(2024, 8, 1)
    assert payment.moc_id.endswith("COLLECTION")
    assert reqs["FAM_APT_COMMERCIAL_CONTENT"].applicability_status == "NOT_APPLICABLE"


def test_missing_dates_and_transition_do_not_become_confirmed(synthetic_knowledge):
    knowledge = synthetic_knowledge
    missing = reference_requirements(scenario("MISSING_RELEVANT_DATES"), knowledge)
    assert all(r.applicability_status == "UNKNOWN" for r in missing)
    transitioning = reference_requirements(scenario("TRANSITION_UNRESOLVED"), knowledge)
    payment = next(r for r in transitioning if r.requirement_id == "FAM_FIRST_PAYMENT_CAP")
    assert payment.applicability_status == "UNKNOWN"
    assert payment.requirement_version_id == "PV_GYC062"
    incomplete = reference_requirements(scenario("ANNEX_NOT_RECEIVED"), knowledge)
    consumer = next(r for r in incomplete if r.requirement_id == "FAM_PARTY_IDENTITY")
    assert consumer.scope_status == "UNKNOWN"
    assert consumer.version_status == "RESOLVED"
    assert consumer.applicability_status == "UNKNOWN"


def test_historical_and_resale_are_not_modern_developer_cases(synthetic_knowledge):
    knowledge = synthetic_knowledge
    old = reference_requirements(scenario("HISTORICAL_VALID"), knowledge)
    assert (
        next(r for r in old if r.requirement_id == "FAM_FIRST_PAYMENT_CAP").requirement_version_id
        == "PV_HYC034"
    )
    assert Counter(r.applicability_status for r in old) == {"CONFIRMED": 7, "NOT_APPLICABLE": 2}
    resale = reference_requirements(scenario("INDIVIDUAL_RESALE"), knowledge)
    assert all(r.scope_status == "NO_MATCH" and not r.confirmed for r in resale)


def test_conflicting_price_is_not_a_confirmed_extracted_amount():
    s = scenario("CONFLICTING_PRICE")
    assert s.profile["gia_tri_hop_dong"] is None
    assert s.numeric["contract_price"] in s.sections["price"]
    assert "các bản không xác định văn bản ưu tiên" in s.sections["price"]


@pytest.mark.parametrize(
    "variant,expected", [(0, "VALID"), (1, "STALE"), (2, "INVALID"), (3, "UNKNOWN")]
)
def test_citation_branches_and_absent_number(synthetic_knowledge, variant, expected):
    s = scenario("CLEAN_DOMESTIC")
    populate_scenario(s, variant)
    context = Context(
        ca_id=s.case_id,
        phien_ban_id="SYNTHETIC",
        run_id="RUN",
        trace_id="TRACE",
        rule_version="RULE",
        legal_knowledge_version="LEGAL",
        knowledge_snapshot_sha256=synthetic_knowledge.sha256,
    )
    extraction, finding = citation_reference(
        s,
        context,
        {
            "doan_id": "CIT_CHUNK",
            "page_start": 1,
            "page_end": 1,
            "noi_dung": s.sections["citation"],
        },
        synthetic_knowledge,
    )
    assert finding.status == expected == s.expected_citation
    if variant == 3:
        assert extraction["normalized"]["so_hieu"] is None
        assert finding.normalized_van_ban_id is None
        assert not finding.finding_verified
