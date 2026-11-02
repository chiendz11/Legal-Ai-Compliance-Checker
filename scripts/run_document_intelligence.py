"""Chạy Document Intelligence (nhóm A, bước 2) trên ca có trong DB và tùy chọn ghi kết quả.

PDF đọc qua CachedHttpSourceStorage. Khi URL nguồn không truy cập được, nạp PDF local vào
cache trước bằng ``python -m scripts.seed_source_cache data/private/pdf``.

    python -m scripts.run_document_intelligence --case CA360_001
    python -m scripts.run_document_intelligence --split DEV --limit 20
    python -m scripts.run_document_intelligence --case CA360_001 --save
"""

import argparse

from legal_checker.core.config import Settings
from legal_checker.core.postgres import connect_postgres
from legal_checker.modules.documents.repository import DocumentRepository
from legal_checker.modules.documents.service import PdfDocumentIntelligence
from legal_checker.shared.storage.http import CachedHttpSourceStorage

SPLIT_CASES = """
SELECT case_id FROM qa.case_manifest
WHERE case_kind = 'CORPUS' AND split = %(split)s
ORDER BY case_id LIMIT %(limit)s
"""
SUMMARY_FIELDS = (
    "loai_hop_dong_id",
    "ngay_giao_ket",
    "gia_tri_hop_dong",
    "ngay_ban_giao_du_kien",
    "tinh_trang_tai_san",
    "quan_he_chu_the",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", nargs="*", default=[])
    parser.add_argument("--split", choices=["DEV", "VALIDATION"])
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--save", action="store_true", help="Ghi kết quả vào DB")
    parser.add_argument("--replace-profile", action="store_true")
    args = parser.parse_args()

    settings = Settings.from_env()
    cases = list(args.case)
    if args.split:
        with connect_postgres(settings.database_url) as conn:
            rows = conn.execute(SPLIT_CASES, {"split": args.split, "limit": args.limit})
            cases += [r["case_id"] for r in rows.fetchall()]
    if not cases:
        parser.error("Cần --case hoặc --split")

    repository = DocumentRepository(settings.database_url)
    service = PdfDocumentIntelligence(
        CachedHttpSourceStorage(settings.source_cache_dir, timeout_seconds=10)
    )
    failures = 0
    for case_id in cases:
        try:
            extraction = service.run(repository.load_case(case_id))
        except Exception as exc:  # báo lỗi từng ca, chạy tiếp ca sau
            failures += 1
            print(f"{case_id}: LỖI {type(exc).__name__}: {exc}")
            continue
        profile = extraction.result.contract_profile
        known = {
            k: v
            for k, v in profile.profile.model_dump(mode="json").items()
            if k in SUMMARY_FIELDS and v is not None
        }
        conflicts = [f.ten_truong for f in profile.facts if f.trang_thai == "CONFLICT"]
        print(
            f"{case_id}: {len(extraction.document.pages)} trang"
            f" | {len(extraction.chunks)} chunks | {len(extraction.citations)} viện dẫn"
            f" | {len(profile.facts)} facts | {len(profile.subjects)} chủ thể"
            + (f" | trang lỗi {extraction.unreadable_pages}" if extraction.unreadable_pages else "")
            + (f" | CONFLICT {conflicts}" if conflicts else "")
        )
        print(f"    {known}")
        if args.save:
            report = repository.save(extraction, replace_profile=args.replace_profile)
            print(f"    đã ghi version {report.version}: {report.profile_note}")
    print(f"\n{len(cases) - failures}/{len(cases)} ca chạy xong")


if __name__ == "__main__":
    main()
