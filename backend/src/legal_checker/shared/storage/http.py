"""Read public HTTP(S) sources, verified against C01, with an atomic local cache."""

import errno
import hashlib
import math
import os
import tempfile
import time
from http.client import HTTPException
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from legal_checker.shared.contracts.assessment import SourceDocument


class SourceStorageError(Exception):
    """Base failure reading a source. Never substitute extracted/reference text."""


class SourceDownloadError(SourceStorageError):
    """Missing HTTP URL, HTTP failure, timeout or incomplete response."""


class SourceIntegrityError(SourceStorageError):
    """Downloaded bytes differ from the SHA-256 declared in C01."""


class SourceTooLargeError(SourceStorageError):
    """Source exceeds the configured byte limit."""


class SourceFormatError(SourceStorageError):
    """A declared PDF has no PDF header."""


class SourceCacheError(SourceStorageError):
    """Cannot read or atomically write the local cache."""


def _sharing_error(error: OSError) -> bool:
    """Recognize Win32 sharing errors and CRT open()'s errno-only EACCES."""
    return getattr(error, "winerror", None) in {5, 32, 33} or error.errno == errno.EACCES


def _is_http_url(value: str) -> bool:
    try:
        url = urlsplit(value)
        return (
            url.scheme.lower() in {"http", "https"}
            and bool(url.hostname)
            and url.username is None
            and url.password is None
        )
    except ValueError:
        return False


class _HttpRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _is_http_url(newurl):
            raise SourceDownloadError("Source redirect must use a public HTTP(S) URL")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class CachedHttpSourceStorage:
    """SourceStorage implementation; no DB, parser, provider key or QA dependencies.

    Cache keys are SHA-256 values, not URLs/file names. Every cache hit is verified.
    A timeout applies to individual blocking network operations, not total runtime.
    Call with trusted source URLs from the local dataset/intake, not arbitrary URLs
    submitted to a public endpoint. Network destination authorization belongs to intake.
    """

    def __init__(
        self,
        cache_dir: str | Path,
        *,
        timeout_seconds: float = 30,
        max_bytes: int = 100 * 1024 * 1024,
    ):
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be finite and positive")
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
            raise ValueError("max_bytes must be a positive integer")
        self.cache_dir = Path(cache_dir).expanduser().resolve()
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes
        self._opener = build_opener(_HttpRedirects())

    def read(self, source: SourceDocument) -> bytes:
        # Revalidate mutable Pydantic instances before using a hash as a file name.
        source = SourceDocument.model_validate(source.model_dump())
        cache_path = self.cache_dir / source.sha256
        cached = self._read_cache(cache_path, source)
        if cached is not None:
            return cached

        # object_uri is the primary source in the current Supabase dataset.
        url = next(
            (
                value
                for value in (source.object_uri, source.url_nguon)
                if value and _is_http_url(value)
            ),
            None,
        )
        if url is None:
            raise SourceDownloadError("Source needs an accessible HTTP(S) object_uri or url_nguon")
        payload = self._download(url)
        self._verify(payload, source)
        self._write_cache(cache_path, payload)
        return payload

    def _verify(self, payload: bytes, source: SourceDocument) -> None:
        if len(payload) > self.max_bytes:
            raise SourceTooLargeError("Source exceeds max_bytes")
        if hashlib.sha256(payload).hexdigest() != source.sha256:
            raise SourceIntegrityError("Source SHA-256 differs from C01; bytes were not accepted")
        mime_type = source.mime_type.partition(";")[0].strip().lower()
        if mime_type == "application/pdf" and b"%PDF-" not in payload[:1024]:
            raise SourceFormatError("Source declared as PDF has no PDF header")

    def _read_cache(self, path: Path, source: SourceDocument) -> bytes | None:
        try:
            for attempt in range(5):
                try:
                    with path.open("rb") as stream:
                        payload = stream.read(self.max_bytes + 1)
                    break
                except FileNotFoundError:
                    return None
                except OSError as error:
                    if not _sharing_error(error) or attempt == 4:
                        raise
                    time.sleep(0.01 * 2**attempt)
            try:
                self._verify(payload, source)
            except (SourceIntegrityError, SourceFormatError, SourceTooLargeError):
                for attempt in range(5):
                    try:
                        path.unlink(missing_ok=True)
                        break
                    except OSError as error:
                        if not _sharing_error(error) or attempt == 4:
                            raise
                        time.sleep(0.01 * 2**attempt)
                return None
            return payload
        except OSError:
            raise SourceCacheError("Cannot read or remove an invalid source cache entry") from None

    def _download(self, url: str) -> bytes:
        request = Request(
            url,
            headers={"User-Agent": "LegalComplianceSource/1.0", "Accept-Encoding": "identity"},
        )
        try:
            with self._opener.open(request, timeout=self.timeout_seconds) as response:
                if response.status != 200 or not _is_http_url(response.geturl()):
                    raise SourceDownloadError("Source download did not return HTTP 200")
                declared_size = response.headers.get("Content-Length")
                if declared_size is not None:
                    try:
                        declared_size = int(declared_size)
                    except ValueError:
                        raise SourceDownloadError("Invalid source Content-Length") from None
                    if declared_size < 0:
                        raise SourceDownloadError("Invalid source Content-Length")
                    if declared_size > self.max_bytes:
                        raise SourceTooLargeError("Source Content-Length exceeds max_bytes")
                pieces = []
                size = 0
                while block := response.read(min(64 * 1024, self.max_bytes + 1 - size)):
                    size += len(block)
                    if size > self.max_bytes:
                        raise SourceTooLargeError("Source download exceeds max_bytes")
                    pieces.append(block)
                if declared_size is not None and size != declared_size:
                    raise SourceDownloadError("Incomplete source download")
                return b"".join(pieces)
        except HTTPError as error:
            error.close()
            raise SourceDownloadError(f"Source download returned HTTP {error.code}") from None
        except (URLError, HTTPException, OSError, ValueError):
            # Do not include signed URL query strings or server error bodies in errors.
            raise SourceDownloadError(
                "Source request failed; check URL, access and timeout"
            ) from None

    def _write_cache(self, path: Path, payload: bytes) -> None:
        temporary = None
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                dir=self.cache_dir, prefix=".source-", delete=False
            ) as f:
                temporary = Path(f.name)
                f.write(payload)
            # Concurrent readers only see a complete, verified entry. On Windows,
            # another reader can temporarily prevent replacing that same entry.
            for attempt in range(5):
                try:
                    os.replace(temporary, path)
                    break
                except OSError as error:
                    # Another publisher may already have installed these exact
                    # verified bytes. Never accept a corrupt/different winner.
                    try:
                        with path.open("rb") as existing:
                            if existing.read(len(payload) + 1) == payload:
                                return
                    except OSError:
                        pass
                    if not _sharing_error(error) or attempt == 4:
                        raise
                    time.sleep(0.01 * 2**attempt)
        except OSError:
            raise SourceCacheError(
                "Cannot write the source cache; check directory permissions"
            ) from None
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass  # Preserve the original cache error if cleanup also fails.
