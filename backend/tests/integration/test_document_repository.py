"""Group A step 2: Q10 → C01, ghi kết quả DI trong một transaction, chạy lại không nhân đôi."""

import hashlib

import pytest
from legal_checker.core.postgres import connect_postgres
from legal_checker.modules.documents.repository import LOAI_DU_LIEU, DocumentRepository
from legal_checker.modules.documents.service import PdfDocumentIntelligence
from unit.test_document_parser_chunker import _minimal_pdf

PDF = _minimal_pdf(
    [
        "HOP DONG MUA BAN\nCan cu Nghi dinh 99/2015/ND-CP\nNgay giao ket: 2017-02-16",
        "Dieu 1. Doi tuong\nBen A ban can ho so 12A cho Ben B",
    ]
)
SHA = hashlib.sha256(PDF).hexdigest()
TABLES = (
    "doan_hop_dong",
    "trich_xuat_truong",
    "bang_chung_truong",
    "bang_chung_ho_so",
    "chu_the_hop_dong",
    "moc_thoi_gian_hop_dong",
    "vien_dan_phap_ly_hop_dong",
    "bang_chung_vien_dan",
    "ho_so_hop_dong",
)


class FakeStorage:
    def read(self, source) -> bytes:
        return PDF


@pytest.fixture
def repository(database_url):
    pytest.importorskip("pypdf")
    with connect_postgres(database_url) as conn, conn.transaction():
        conn.execute(
            "INSERT INTO knowledge.phien_ban_trien_khai (phien_ban_id) VALUES ('DEPLOY_DI')"
        )
        # hop_dong.tep_nguon_id ↔ tep_nguon.hop_dong_id: FK deferred, kiểm tra lúc commit.
        conn.execute(
            "INSERT INTO runtime.hop_dong (hop_dong_id, tep_nguon_id) VALUES ('HD_DI', 'TEP_DI')"
        )
        conn.execute(
            """INSERT INTO runtime.tep_nguon (tep_id, hop_dong_id, vai_tro, object_uri,
                   mime_type, sha256)
               VALUES ('TEP_DI', 'HD_DI', 'BAN_GOC', 'x://HD_DI.pdf', 'application/pdf', %s)""",
            (SHA.upper(),),  # mapper phải chuẩn hóa về chữ thường
        )
        conn.execute(
            """INSERT INTO runtime.ca_danh_gia (ca_id, hop_dong_id, ngay_danh_gia, phien_ban_id,
                   rule_version, legal_knowledge_version, tenant_id, created_by)
               VALUES ('CA_DI', 'HD_DI', '2026-11-03T00:00:00Z', 'DEPLOY_DI',
                   'RULE_DI', 'LEGAL_DI', 'TENANT_DI', 'dev')"""
        )
    return DocumentRepository(database_url)


def _counts(database_url) -> dict[str, int]:
    with connect_postgres(database_url) as conn:
        return {
            t: conn.execute(f"SELECT count(*) AS n FROM runtime.{t}").fetchone()["n"]
            for t in TABLES
        }


def test_load_case_save_and_rerun_is_idempotent(repository, database_url):
    case = repository.load_case("CA_DI")
    assert (case.hop_dong_id, case.source.tep_id, case.source.sha256) == ("HD_DI", "TEP_DI", SHA)
    extraction = PdfDocumentIntelligence(FakeStorage()).run(case)

    first = repository.save(extraction)
    after_first = _counts(database_url)
    assert first.profile_written
    assert after_first["doan_hop_dong"] == first.chunks > 0
    assert after_first["trich_xuat_truong"] == first.facts
    assert after_first["vien_dan_phap_ly_hop_dong"] == first.citations == 1
    assert after_first["bang_chung_vien_dan"] == first.citation_positions
    assert after_first["moc_thoi_gian_hop_dong"] == first.markers
    assert after_first["ho_so_hop_dong"] == 1

    again = repository.save(extraction)
    assert not again.profile_written  # đã có profile → giữ nguyên
    assert _counts(database_url) == after_first

    with connect_postgres(database_url) as conn:
        rows = conn.execute(
            "SELECT DISTINCT loai_du_lieu FROM runtime.doan_hop_dong"
            " UNION SELECT loai_du_lieu FROM runtime.ho_so_hop_dong"
        ).fetchall()
    assert {r["loai_du_lieu"] for r in rows} == {LOAI_DU_LIEU}


def test_failed_save_leaves_no_partial_rows(repository, database_url, monkeypatch):
    extraction = PdfDocumentIntelligence(FakeStorage()).run(repository.load_case("CA_DI"))

    def broken(*args, **kwargs):
        raise RuntimeError("profile write failed")

    monkeypatch.setattr(DocumentRepository, "_save_profile", broken)
    with pytest.raises(RuntimeError):
        repository.save(extraction)
    assert set(_counts(database_url).values()) == {0}  # chunks/facts đã ghi bị rollback


def test_missing_case_is_reported(repository):
    with pytest.raises(LookupError):
        repository.load_case("CA_ABSENT")