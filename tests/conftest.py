from copy import deepcopy
from dataclasses import replace

import pytest

from app.contracts.pipeline import PipelineRequest
from app.core.config import Settings
from app.infrastructure.knowledge.snapshot import Knowledge
from app.main import create_app


@pytest.fixture
def app_factory(tmp_path):
    def build(*, settings=None, services=None):
        if settings is None:
            settings = replace(Settings.from_env(), database_path=tmp_path / "runtime.sqlite3")
        return create_app(settings=settings, services=services)

    return build


@pytest.fixture(scope="session")
def knowledge():
    return Knowledge()


def make_request(knowledge, version_id="PV_GYC005", finding="SATISFIED"):
    version = knowledge.versions[version_id]
    text = "Bằng chứng đã đối chiếu cho tiêu chí hiện tại."
    criteria = knowledge.criteria_for(version_id)
    data = {
        "ca_id": "CA_TEST",
        "phien_ban_id": "DEPLOY_TEST",
        "rule_version": "RULE_TEST",
        "legal_knowledge_version": "LEGAL_TEST",
        "knowledge_snapshot_sha256": knowledge.sha256,
        "run_id": "RUN_TEST",
        "trace_id": "TRACE_TEST",
        "payload": {
            "hop_dong_id": "HD_TEST",
            "requirements": [
                {
                    "yeu_cau_ca_id": "YCCA_TEST",
                    "ca_id": "CA_TEST",
                    "requirement_id": version["requirement_id"],
                    "requirement_version_id": version_id,
                    "scope_status": "MATCH",
                    "version_status": "RESOLVED",
                    "applicability_status": "CONFIRMED",
                    "moc_ap_dung": "2026-01-15",
                    "phien_ban_id": "DEPLOY_TEST",
                }
            ],
            "chunks": [
                {
                    "doan_id": "D_TEST",
                    "hop_dong_id": "HD_TEST",
                    "noi_dung": text,
                    "page_start": 1,
                    "page_end": 1,
                }
            ],
            "retrieval": [],
            "observations": [],
            "citations": [],
        },
    }
    for index, criterion in enumerate(criteria):
        cid = criterion["tieu_chi_id"]
        data["payload"]["retrieval"].append(
            {
                "truy_xuat_id": f"RTX_{index}",
                "yeu_cau_ca_id": "YCCA_TEST",
                "tieu_chi_id": cid,
                "doan_id": "D_TEST",
                "thu_hang": 1,
                "duoc_chon": True,
                "retrieval_version": "RET_TEST",
                "index_version": "IDX_TEST",
                "lan_chay_id": "RUN_TEST",
            }
        )
        data["payload"]["observations"].append(
            {
                "tieu_chi_id": cid,
                "proposed_finding": finding,
                "giai_thich": "Fixture observation",
                "gates": {
                    "coverage_complete": True,
                    "absence_verified": True,
                    "evidence_validated": True,
                    "source_verified": True,
                    "scope_confirmed": True,
                    "version_resolved": True,
                    "evidence_conflict": False,
                    "exceptions_resolved": True,
                },
                "evidence": [
                    {
                        "doan_id": "D_TEST",
                        "trich_dan": text,
                        "ky_tu_bat_dau": 0,
                        "ky_tu_ket_thuc": len(text),
                    }
                ],
                "local_applicability": "MATCH",
                "mandatory_confirmed": True,
                "all_pages_readable": True,
                "all_related_documents_received": True,
            }
        )
    return data


@pytest.fixture
def request_factory(knowledge):
    def build(version_id="PV_GYC005", finding="SATISFIED", mutate=None):
        data = deepcopy(make_request(knowledge, version_id, finding))
        if mutate:
            mutate(data)
        return PipelineRequest.model_validate(data)

    return build
