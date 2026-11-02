"""Group A step 1: kiểm tra upload và lưu bytes theo SHA-256, không cần DB."""

import hashlib

import pytest
from legal_checker.modules.documents.intake import (
    LocalSourceStore,
    UploadRejectedError,
    validate_upload,
)
from legal_checker.shared.contracts.assessment import SourceDocument
from legal_checker.shared.storage.http import CachedHttpSourceStorage

PDF = b"%PDF-1.4\n1 0 obj\n<< >>\nendobj\n%%EOF"


def test_valid_pdf_returns_lowercase_sha256():
    assert (
        validate_upload(PDF, "application/pdf; charset=binary") == hashlib.sha256(PDF).hexdigest()
    )


@pytest.mark.parametrize(
    ("content", "mime"),
    [
        (PDF, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        (PDF, ""),
        (b"", "application/pdf"),
        (b"PK\x03\x04 not a pdf", "application/pdf"),
    ],
)
def test_unsupported_or_broken_upload_is_rejected(content, mime):
    with pytest.raises(UploadRejectedError):
        validate_upload(content, mime)


def test_oversized_upload_is_rejected():
    with pytest.raises(UploadRejectedError):
        validate_upload(PDF, "application/pdf", max_bytes=len(PDF) - 1)


def test_stored_bytes_are_read_back_by_shared_storage(tmp_path):
    sha = validate_upload(PDF, "application/pdf")
    store = LocalSourceStore(tmp_path)
    uri = store.put(PDF, sha)
    assert store.put(PDF, sha) == uri  # tải lại cùng file: không ghi đè, cùng URI
    assert [p.name for p in tmp_path.iterdir()] == [sha]  # không sót file .tmp
    source = SourceDocument(tep_id="TEP", object_uri=uri, mime_type="application/pdf", sha256=sha)
    assert CachedHttpSourceStorage(tmp_path).read(source) == PDF