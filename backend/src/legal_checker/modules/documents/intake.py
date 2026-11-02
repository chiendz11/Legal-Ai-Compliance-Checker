"""Step 1 / BR-01: nhận tệp upload, lưu bytes theo SHA-256 và tạo C01 có deployment pin.

- Chỉ nhận PDF (DOCX chưa có parser): kiểm tra MIME, kích thước, header và tính SHA-256.
- Bytes lưu vào thư mục cache của ``CachedHttpSourceStorage`` (tên file = SHA-256), nên
  bước 2 đọc lại bằng đúng storage dùng chung, có kiểm tra hash mỗi lần đọc.
- ``hop_dong`` + ``tep_nguon`` + ``ca_danh_gia`` ghi trong MỘT transaction vì
  ``hop_dong.tep_nguon_id`` ↔ ``tep_nguon.hop_dong_id`` là vòng FK (deferred).
- Mỗi upload tạo ID mới, không tái dùng metadata mẫu của seed.
"""

import hashlib
import os
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Protocol

from legal_checker.core.postgres import connect_postgres
from legal_checker.modules.documents.repository import DocumentRepository
from legal_checker.shared.contracts.assessment import AssessmentCase
from legal_checker.shared.contracts.common import DeploymentPin


class IntakeService(Protocol):
    def register(self, case: AssessmentCase) -> AssessmentCase: ...


SUPPORTED_MIME_TYPES = {"application/pdf"}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
LOAI_DU_LIEU = "DI_UPLOAD"
LOAI_NGUON = "USER_UPLOAD"
VAI_TRO_TEP_CHINH = "SOURCE_UPLOADED_PDF"
TRANG_THAI_BAN_GOC = "EXACT_UPLOADED_BYTES"
TRANG_THAI_XU_LY = "RECEIVED_PENDING_EXTRACTION"
TRANG_THAI_CA = "SOURCE_RECEIVED_PENDING_REVIEW"
OBJECT_URI_PREFIX = "local-cache:sha256:"


class UploadRejectedError(ValueError):
    """Tệp không hợp lệ: dừng trước khi ghi storage hoặc DB."""


class UnknownDeploymentError(LookupError):
    """``phien_ban_id`` không có trong knowledge.phien_ban_trien_khai."""


def validate_upload(content: bytes, mime_type: str, *, max_bytes: int = MAX_UPLOAD_BYTES) -> str:
    """Trả SHA-256 (hex thường) nếu tệp được nhận."""
    mime = mime_type.partition(";")[0].strip().lower()
    if mime not in SUPPORTED_MIME_TYPES:
        raise UploadRejectedError(f"Unsupported MIME type: {mime or 'missing'}")
    if not content:
        raise UploadRejectedError("Empty file")
    if len(content) > max_bytes:
        raise UploadRejectedError(f"File exceeds {max_bytes} bytes")
    if b"%PDF-" not in content[:1024]:
        raise UploadRejectedError("File declared as PDF has no PDF header")
    return hashlib.sha256(content).hexdigest()


class LocalSourceStore:
    """Ghi bytes vào cache dir theo SHA-256; ``CachedHttpSourceStorage`` đọc lại được."""

    def __init__(self, cache_dir: str | Path) -> None:
        self.cache_dir = Path(cache_dir).expanduser().resolve()

    def put(self, content: bytes, sha256: str) -> str:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        target = self.cache_dir / sha256
        if not target.exists():
            tmp = target.with_name(f"{sha256}.{uuid.uuid4().hex}.tmp")
            tmp.write_bytes(content)
            os.replace(tmp, target)  # không để lại file ghi dở dưới tên SHA
        return f"{OBJECT_URI_PREFIX}{sha256}"


@dataclass(frozen=True)
class CaseRequest:
    tenant_id: str
    created_by: str
    deployment: DeploymentPin
    ngay_danh_gia: date
    moc_ap_dung: date | None = None
    loai_moc_ap_dung: str | None = None


def _new_id() -> str:
    return uuid.uuid4().hex[:16].upper()


class PostgresIntake:
    """IntakeService: ``submit`` tạo ca mới từ upload, ``register`` xác nhận C01 đã lưu."""

    def __init__(
        self,
        database_url: str,
        store: LocalSourceStore,
        *,
        new_id: Callable[[], str] = _new_id,
        max_bytes: int = MAX_UPLOAD_BYTES,
    ) -> None:
        self.database_url = database_url
        self.store = store
        self.new_id = new_id
        self.max_bytes = max_bytes

    def submit(
        self, content: bytes, *, file_name: str, mime_type: str, request: CaseRequest
    ) -> AssessmentCase:
        sha256 = validate_upload(content, mime_type, max_bytes=self.max_bytes)
        pin = request.deployment
        with connect_postgres(self.database_url) as conn:
            known = conn.execute(
                "SELECT 1 FROM knowledge.phien_ban_trien_khai WHERE phien_ban_id = %s",
                (pin.phien_ban_id,),
            ).fetchone()
        if known is None:
            raise UnknownDeploymentError(f"Unknown deployment {pin.phien_ban_id}")

        suffix = self.new_id()
        hd, tep, ca = f"HD_UP_{suffix}", f"TEP_UP_{suffix}", f"CA_UP_{suffix}"
        now = datetime.now(timezone.utc)
        object_uri = self.store.put(content, sha256)  # bytes trước, DB sau
        with connect_postgres(self.database_url) as conn, conn.transaction():
            conn.execute(
                """INSERT INTO runtime.hop_dong (hop_dong_id, ten_tai_lieu, loai_nguon,
                       sha256_tep_nguon, ngay_thu_thap, trang_thai_xu_ly, tep_nguon_id,
                       loai_du_lieu)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (hd, file_name, LOAI_NGUON, sha256, now, TRANG_THAI_XU_LY, tep, LOAI_DU_LIEU),
            )
            conn.execute(
                """INSERT INTO runtime.tep_nguon (tep_id, hop_dong_id, vai_tro, object_uri,
                       mime_type, sha256, ngay_thu_thap, trang_thai_ban_goc, ghi_chu,
                       loai_du_lieu)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    tep,
                    hd,
                    VAI_TRO_TEP_CHINH,
                    object_uri,
                    "application/pdf",
                    sha256,
                    now,
                    TRANG_THAI_BAN_GOC,
                    f"upload: {file_name}",
                    LOAI_DU_LIEU,
                ),
            )
            conn.execute(
                """INSERT INTO runtime.ca_danh_gia (ca_id, hop_dong_id, moc_ap_dung,
                       ngay_danh_gia, trang_thai, phien_ban_id, loai_moc_ap_dung,
                       loai_du_lieu, rule_version, legal_knowledge_version,
                       tenant_id, created_by)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    ca,
                    hd,
                    request.moc_ap_dung,
                    datetime.combine(request.ngay_danh_gia, datetime.min.time(), timezone.utc),
                    TRANG_THAI_CA,
                    pin.phien_ban_id,
                    request.loai_moc_ap_dung,
                    LOAI_DU_LIEU,
                    pin.rule_version,
                    pin.legal_knowledge_version,
                    request.tenant_id,
                    request.created_by,
                ),
            )
        # Đọc lại bằng Q10 để C01 trả ra đúng là cái bước 2 sẽ đọc.
        return DocumentRepository(self.database_url).load_case(ca)

    def register(self, case: AssessmentCase) -> AssessmentCase:
        stored = DocumentRepository(self.database_url).load_case(case.ca_id)
        if stored != case:
            raise ValueError("Assessment case differs from the stored C01")
        return case