"""Local, content-addressed storage for uploaded contracts, behind the SourceStorage protocol.

Uploaded files are stored once per SHA-256 as `<sha256>.<ext>` and referenced by
`upload://<sha256>.<ext>`. RoutingSourceStorage lets document intelligence and the evidence
viewer read uploads and HTTP(S) sources through one SourceStorage.
"""

import hashlib
import io
import os
import zipfile
from dataclasses import dataclass
from pathlib import Path

from legal_checker.shared.contracts.assessment import SourceDocument
from legal_checker.shared.storage.http import (
    SourceFormatError,
    SourceIntegrityError,
    SourceStorageError,
    SourceTooLargeError,
)
from legal_checker.shared.storage.source import SourceStorage

UPLOAD_SCHEME = "upload://"
PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
EXTENSIONS = {PDF: "pdf", DOCX: "docx"}


@dataclass(frozen=True)
class StoredUpload:
    object_uri: str
    sha256: str
    mime_type: str
    size_bytes: int


def sniff_mime_type(payload: bytes) -> str:
    """Trust the bytes, not the client's filename or Content-Type."""
    if payload.startswith(b"%PDF-"):
        return PDF
    if payload.startswith(b"PK"):
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                if "word/document.xml" in archive.namelist():
                    return DOCX
        except zipfile.BadZipFile:
            pass
    raise SourceFormatError("Only PDF or DOCX contracts are accepted")


class LocalUploadStorage:
    def __init__(self, root: Path, *, max_bytes: int):
        self.root = Path(root)
        self.max_bytes = max_bytes

    def save(self, payload: bytes) -> StoredUpload:
        if not payload:
            raise SourceFormatError("The uploaded file is empty")
        if len(payload) > self.max_bytes:
            raise SourceTooLargeError(f"File exceeds {self.max_bytes} bytes")
        mime_type = sniff_mime_type(payload)
        sha = hashlib.sha256(payload).hexdigest()
        name = f"{sha}.{EXTENSIONS[mime_type]}"
        path = self.root / name
        if not path.exists():
            self.root.mkdir(parents=True, exist_ok=True)
            partial = path.with_suffix(f".{os.getpid()}.part")
            partial.write_bytes(payload)
            os.replace(partial, path)  # atomic: readers never see a partial file
        return StoredUpload(UPLOAD_SCHEME + name, sha, mime_type, len(payload))

    def read(self, source: SourceDocument) -> bytes:
        if not source.object_uri or not source.object_uri.startswith(UPLOAD_SCHEME):
            raise SourceStorageError("Not an uploaded source")
        name = source.object_uri.removeprefix(UPLOAD_SCHEME)
        if "/" in name or "\\" in name or name.startswith("."):
            raise SourceStorageError("Invalid upload reference")
        try:
            payload = (self.root / name).read_bytes()
        except FileNotFoundError as error:
            raise SourceStorageError("Uploaded source file is missing") from error
        if hashlib.sha256(payload).hexdigest() != source.sha256:
            raise SourceIntegrityError("Uploaded source does not match its SHA-256")
        return payload


class RoutingSourceStorage:
    """`upload://` sources from local storage, everything else from the HTTP(S) cache."""

    def __init__(self, uploads: LocalUploadStorage, remote: SourceStorage):
        self.uploads = uploads
        self.remote = remote

    def read(self, source: SourceDocument) -> bytes:
        if source.object_uri and source.object_uri.startswith(UPLOAD_SCHEME):
            return self.uploads.read(source)
        return self.remote.read(source)
