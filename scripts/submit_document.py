"""Nhận một PDF (nhóm A, bước 1): lưu bytes theo SHA-256 và tạo hop_dong/tep_nguon/ca_danh_gia.

Deployment pin, tenant và người tạo được chép từ một ca có sẵn (mặc định CA360_001), để ca
mới chạy được bước 2 ngay:

    python -m scripts.submit_document data/private/pdf/HD360_001.pdf
    python -m scripts.run_document_intelligence --case CA_UP_xxxx --save
"""

import argparse
from datetime import date
from pathlib import Path

from legal_checker.core.config import Settings
from legal_checker.modules.documents.intake import CaseRequest, LocalSourceStore, PostgresIntake
from legal_checker.modules.documents.repository import DocumentRepository


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--like-case", default="CA360_001", help="Ca lấy deployment pin")
    parser.add_argument("--ngay-danh-gia", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()

    settings = Settings.from_env()
    template = DocumentRepository(settings.database_url).load_case(args.like_case)
    request = CaseRequest(
        tenant_id=template.tenant_id,
        created_by=template.created_by,
        deployment=template.deployment,
        ngay_danh_gia=args.ngay_danh_gia,
    )
    intake = PostgresIntake(settings.database_url, LocalSourceStore(settings.source_cache_dir))
    case = intake.submit(
        args.pdf.read_bytes(), file_name=args.pdf.name, mime_type="application/pdf", request=request
    )
    print(f"Đã tạo {case.ca_id} (hợp đồng {case.hop_dong_id}, tệp {case.source.tep_id})")
    print(f"SHA-256 {case.source.sha256}")
    print(f"Bước 2: python -X utf8 -m scripts.run_document_intelligence --case {case.ca_id} --save")


if __name__ == "__main__":
    main()
