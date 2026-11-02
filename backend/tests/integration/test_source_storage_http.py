"""Exercise the real HTTP reader against local servers; no Supabase/DB required."""

import errno
import hashlib
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from legal_checker.api.dependencies import build_services
from legal_checker.core.config import PROJECT_ROOT, Settings
from legal_checker.shared.contracts.assessment import SourceDocument
from legal_checker.shared.storage.http import (
    CachedHttpSourceStorage,
    SourceCacheError,
    SourceDownloadError,
    SourceFormatError,
    SourceIntegrityError,
    SourceTooLargeError,
)
from pydantic import ValidationError

# A header-bearing test payload, not a parser/OCR quality fixture.
PDF = b"%PDF-1.7\nsynthetic source bytes\n%%EOF\n"
SHA = hashlib.sha256(PDF).hexdigest()


@pytest.fixture
def http_source():
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            if self.path == "/missing":
                self.send_error(404)
                return
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "/source.pdf")
                self.end_headers()
                return
            if self.path == "/unsafe-redirect":
                self.send_response(302)
                self.send_header("Location", "file:///etc/hosts")
                self.end_headers()
                return
            if self.path == "/slow":
                time.sleep(0.1)
            body = b"<html>login</html>" if self.path == "/html" else PDF
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            if self.path == "/truncated":
                self.send_header("Content-Length", str(len(body) + 10))
            elif self.path == "/large-header":
                self.send_header("Content-Length", "10000000")
            elif self.path != "/without-length":
                self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def source(url, **changes):
    return SourceDocument.model_validate(
        dict(tep_id="TEP_TEST", object_uri=url, mime_type="application/pdf", sha256=SHA) | changes
    )


def test_download_preserves_bytes_and_cache_is_shared_by_hash(tmp_path, http_source):
    base, requests = http_source
    storage = CachedHttpSourceStorage(tmp_path)
    assert storage.read(source(base + "/source.pdf")) == PDF
    assert (tmp_path / SHA).read_bytes() == PDF
    # Same bytes, different ID/expired URL: a validated cache hit needs no network.
    assert storage.read(source(base + "/missing", tep_id="ANOTHER_FILE")) == PDF
    assert requests == ["/source.pdf"]
    assert list(tmp_path.iterdir()) == [tmp_path / SHA]


def test_corrupt_cache_is_replaced_using_verified_download(tmp_path, http_source):
    base, requests = http_source
    (tmp_path / SHA).write_bytes(b"corrupted")
    assert CachedHttpSourceStorage(tmp_path).read(source(base + "/source.pdf")) == PDF
    assert (tmp_path / SHA).read_bytes() == PDF
    assert requests == ["/source.pdf"]


def test_wrong_hash_is_rejected_without_leaving_cache(tmp_path, http_source):
    base, _ = http_source
    with pytest.raises(SourceIntegrityError):
        CachedHttpSourceStorage(tmp_path).read(source(base + "/source.pdf", sha256="a" * 64))
    assert list(tmp_path.iterdir()) == []


def test_html_cannot_be_accepted_as_pdf_even_with_matching_hash(tmp_path, http_source):
    base, _ = http_source
    with pytest.raises(SourceFormatError):
        CachedHttpSourceStorage(tmp_path).read(
            source(base + "/html", sha256=hashlib.sha256(b"<html>login</html>").hexdigest())
        )
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("path", ["/source.pdf", "/without-length", "/large-header"])
def test_byte_limit_with_or_without_content_length(tmp_path, http_source, path):
    base, _ = http_source
    with pytest.raises(SourceTooLargeError):
        CachedHttpSourceStorage(tmp_path, max_bytes=10).read(source(base + path))
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("path", ["/missing", "/truncated", "/unsafe-redirect"])
def test_failed_download_never_returns_or_caches_partial_bytes(tmp_path, http_source, path):
    base, _ = http_source
    with pytest.raises(SourceDownloadError):
        CachedHttpSourceStorage(tmp_path).read(source(base + path))
    assert list(tmp_path.iterdir()) == []


def test_timeout_is_reported_as_download_error(tmp_path, http_source):
    base, _ = http_source
    with pytest.raises(SourceDownloadError):
        CachedHttpSourceStorage(tmp_path, timeout_seconds=0.02).read(source(base + "/slow"))
    assert list(tmp_path.iterdir()) == []


def test_http_redirect_and_source_url_fallback(tmp_path, http_source):
    base, requests = http_source
    assert (
        CachedHttpSourceStorage(tmp_path).read(
            source("s3://not-supported/source.pdf", url_nguon=base + "/redirect")
        )
        == PDF
    )
    assert requests == ["/redirect", "/source.pdf"]


def test_object_uri_is_preferred_to_source_page_url(tmp_path, http_source):
    base, requests = http_source
    assert (
        CachedHttpSourceStorage(tmp_path).read(
            source(base + "/source.pdf", url_nguon=base + "/html")
        )
        == PDF
    )
    assert requests == ["/source.pdf"]


def test_concurrent_downloads_leave_one_complete_cache_entry(tmp_path, http_source):
    base, _ = http_source
    storage = CachedHttpSourceStorage(tmp_path)
    document = source(base + "/source.pdf")
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(storage.read, [document] * 8)) == [PDF] * 8
    assert list(tmp_path.iterdir()) == [tmp_path / SHA]
    assert (tmp_path / SHA).read_bytes() == PDF


def test_cache_write_failure_is_explicit_and_cleans_temporary_file(
    tmp_path, http_source, monkeypatch
):
    base, _ = http_source

    def fail(*args):
        raise PermissionError("disk error")

    monkeypatch.setattr("legal_checker.shared.storage.http.os.replace", fail)
    with pytest.raises(SourceCacheError):
        CachedHttpSourceStorage(tmp_path).read(source(base + "/source.pdf"))
    assert list(tmp_path.iterdir()) == []


def sharing_violation():
    error = PermissionError("Destination is in use")
    error.winerror = 32
    return error


def test_windows_cache_publication_retries_transient_sharing_errors(tmp_path, monkeypatch):
    replace = os.replace
    calls = []
    delays = []

    def busy_then_replace(temporary, destination):
        calls.append(destination)
        if len(calls) < 3:
            raise sharing_violation()
        replace(temporary, destination)

    monkeypatch.setattr("legal_checker.shared.storage.http.os.replace", busy_then_replace)
    monkeypatch.setattr("legal_checker.shared.storage.http.time.sleep", delays.append)
    CachedHttpSourceStorage(tmp_path)._write_cache(tmp_path / SHA, PDF)
    assert len(calls) == 3
    assert delays == [0.01, 0.02]
    assert list(tmp_path.iterdir()) == [tmp_path / SHA]
    assert (tmp_path / SHA).read_bytes() == PDF


@pytest.mark.parametrize("failures", [2, 5])
@pytest.mark.parametrize("crt_errno", [False, True])
def test_windows_cache_reads_retry_but_persistent_sharing_failure_is_explicit(
    tmp_path, monkeypatch, failures, crt_errno
):
    from pathlib import Path

    path = tmp_path / SHA
    path.write_bytes(PDF)
    original_open = Path.open
    calls, delays = [], []

    def busy_reader(candidate, *args, **kwargs):
        if candidate == path:
            calls.append(candidate)
            if len(calls) <= failures:
                if crt_errno:
                    # Python's CRT file open reports errno=13, winerror=None.
                    raise PermissionError(errno.EACCES, "Destination is temporarily in use")
                raise sharing_violation()
        return original_open(candidate, *args, **kwargs)

    def forbidden_download(*args):
        pytest.fail("An unreadable cache must not be silently treated as a miss")

    monkeypatch.setattr(Path, "open", busy_reader)
    monkeypatch.setattr(CachedHttpSourceStorage, "_download", forbidden_download)
    monkeypatch.setattr("legal_checker.shared.storage.http.time.sleep", delays.append)
    storage = CachedHttpSourceStorage(tmp_path)
    if failures == 2:
        assert storage.read(source("https://example.test/source.pdf")) == PDF
        assert len(calls) == 3
        assert delays == [0.01, 0.02]
    else:
        with pytest.raises(SourceCacheError):
            storage.read(source("https://example.test/source.pdf"))
        assert len(calls) == 5
        assert delays == [0.01, 0.02, 0.04, 0.08]
    assert path.stat().st_size == len(PDF)


def test_windows_cache_publication_accepts_identical_concurrent_winner(tmp_path, monkeypatch):
    def another_publisher_won(temporary, destination):
        destination.write_bytes(PDF)
        raise sharing_violation()

    monkeypatch.setattr("legal_checker.shared.storage.http.os.replace", another_publisher_won)
    CachedHttpSourceStorage(tmp_path)._write_cache(tmp_path / SHA, PDF)
    assert list(tmp_path.iterdir()) == [tmp_path / SHA]
    assert (tmp_path / SHA).read_bytes() == PDF


def test_windows_cache_sharing_errors_never_accept_corrupt_winner(tmp_path, monkeypatch):
    calls = []
    (tmp_path / SHA).write_bytes(b"corrupt")

    def still_busy(*args):
        calls.append(True)
        raise sharing_violation()

    monkeypatch.setattr("legal_checker.shared.storage.http.os.replace", still_busy)
    monkeypatch.setattr("legal_checker.shared.storage.http.time.sleep", lambda _: None)
    with pytest.raises(SourceCacheError):
        CachedHttpSourceStorage(tmp_path)._write_cache(tmp_path / SHA, PDF)
    assert len(calls) == 5
    assert list(tmp_path.iterdir()) == [tmp_path / SHA]
    assert (tmp_path / SHA).read_bytes() == b"corrupt"


def test_windows_corrupt_cache_removal_retries_sharing_error(tmp_path, http_source, monkeypatch):
    from pathlib import Path

    base, _ = http_source
    path = tmp_path / SHA
    path.write_bytes(b"corrupt")
    unlink = Path.unlink
    calls = []

    def busy_once(candidate, **kwargs):
        if candidate == path:
            calls.append(candidate)
            if len(calls) == 1:
                raise sharing_violation()
        return unlink(candidate, **kwargs)

    monkeypatch.setattr(Path, "unlink", busy_once)
    monkeypatch.setattr("legal_checker.shared.storage.http.time.sleep", lambda _: None)
    assert CachedHttpSourceStorage(tmp_path).read(source(base + "/source.pdf")) == PDF
    assert len(calls) == 2
    assert list(tmp_path.iterdir()) == [path]
    assert path.read_bytes() == PDF


def test_non_http_locations_are_not_opened(tmp_path):
    with pytest.raises(SourceDownloadError):
        CachedHttpSourceStorage(tmp_path).read(source("file:///etc/hosts"))


def test_mutated_contract_cannot_escape_cache_directory(tmp_path):
    document = source("https://example.test/source.pdf")
    document.sha256 = "../other-file"
    with pytest.raises(ValidationError):
        CachedHttpSourceStorage(tmp_path).read(document)
    assert list(tmp_path.iterdir()) == []


def test_constructor_does_not_create_cache_or_connect(tmp_path):
    path = tmp_path / "not-created"
    CachedHttpSourceStorage(path)
    assert not path.exists()


@pytest.mark.parametrize(
    "options", [{"timeout_seconds": 0}, {"timeout_seconds": float("nan")}, {"max_bytes": 0}]
)
def test_invalid_limits_fail_at_startup(tmp_path, options):
    with pytest.raises(ValueError):
        CachedHttpSourceStorage(tmp_path, **options)


def test_storage_settings_anchor_relative_paths_to_project_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SOURCE_CACHE_DIR", "data/private/test-source-cache")
    monkeypatch.setenv("SOURCE_DOWNLOAD_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("SOURCE_MAX_BYTES", "123456")
    settings = Settings.from_env()
    assert settings.source_cache_dir == PROJECT_ROOT / "data/private/test-source-cache"
    assert settings.source_download_timeout_seconds == 12.5
    assert settings.source_max_bytes == 123456


def test_factory_provides_source_storage_without_downloading(database_url, tmp_path, monkeypatch):
    def unexpected_download(*args):
        pytest.fail("Factory must not download documents")

    monkeypatch.setattr(CachedHttpSourceStorage, "_download", unexpected_download)
    cache_dir = tmp_path / "not-created"
    services = build_services(Settings(database_url=database_url, source_cache_dir=cache_dir))
    assert isinstance(services.source_storage, CachedHttpSourceStorage)
    assert services.source_storage.cache_dir == cache_dir
    assert not cache_dir.exists()
