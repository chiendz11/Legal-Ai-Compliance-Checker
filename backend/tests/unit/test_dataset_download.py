import hashlib
import json
import shutil
import stat
import sys
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile, ZipInfo

import pytest
from devtools.dataset_download import (
    DatasetError,
    check_dataset,
    download_archive,
    pull_dataset,
    read_manifest,
    sha256_file,
)


def dataset_zip(tmp_path, extras=None):
    path = tmp_path / "dataset.zip"
    content = {"full.xlsx": b"frozen workbook", "sources/text/HD001.txt": b"source text"}
    with ZipFile(path, "w") as archive:
        for name, value in content.items():
            archive.writestr(name, value)
        archive.writestr("sources/pdf/HD001.pdf", b"%PDF-offline source")
        for name, value in (extras or {}).items():
            archive.writestr(name, value)
    with ZipFile(path) as archive:
        expanded = sum(item.file_size for item in archive.infolist())
    manifest = {
        "manifest_version": 1,
        "dataset_version": "frozen-r2",
        "distribution": "DEV_VALIDATION",
        "workbook": "full.xlsx",
        "archive": {
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "url": "https://drive.google.com/file/d/example/view",
            "max_expanded_bytes": expanded,
        },
        "required_files": {
            name: hashlib.sha256(value).hexdigest() for name, value in content.items()
        },
    }
    return manifest, path


def test_install_exact_files_and_rerun_without_download(tmp_path):
    manifest, archive = dataset_zip(tmp_path)
    destination = tmp_path / "private/current"
    result = pull_dataset(manifest, destination, archive_path=archive)
    assert result["status"] == "installed"
    assert result["database_changed"] is False
    assert (destination / "full.xlsx").read_bytes() == b"frozen workbook"
    assert not (destination / "sources/pdf").exists()
    assert check_dataset(manifest, destination)["verified_files"] == 2
    assert (
        pull_dataset(manifest, destination, downloader=lambda *a: pytest.fail("downloaded"))[
            "status"
        ]
        == "already_present"
    )
    assert not list(destination.parent.glob(".dataset-pull-*"))


def test_existing_folder_is_preserved_on_mismatch(tmp_path):
    manifest, archive = dataset_zip(tmp_path)
    destination = tmp_path / "existing"
    destination.mkdir()
    marker = destination / "user-data"
    marker.write_bytes(b"keep")
    with pytest.raises(DatasetError, match="preserved"):
        pull_dataset(manifest, destination, archive_path=archive)
    assert marker.read_bytes() == b"keep"
    assert not (destination / "full.xlsx").exists()


def test_changed_existing_reference_is_detected_without_overwrite(tmp_path):
    manifest, archive = dataset_zip(tmp_path)
    destination = tmp_path / "current"
    pull_dataset(manifest, destination, archive_path=archive)
    text = destination / "sources/text/HD001.txt"
    text.write_bytes(b"user edit")
    with pytest.raises(DatasetError, match="checksum differs"):
        pull_dataset(manifest, destination, archive_path=archive)
    assert text.read_bytes() == b"user edit"


def test_same_size_corrupt_download_never_publishes(tmp_path):
    manifest, archive = dataset_zip(tmp_path)
    raw = archive.read_bytes()
    archive.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
    destination = tmp_path / "current"
    with pytest.raises(DatasetError, match="SHA-256 differs"):
        pull_dataset(manifest, destination, archive_path=archive)
    assert not destination.exists()
    assert not list(tmp_path.glob(".dataset-pull-*"))


def test_wrong_file_hash_never_publishes(tmp_path):
    manifest, archive = dataset_zip(tmp_path)
    manifest["required_files"]["sources/text/HD001.txt"] = "0" * 64
    destination = tmp_path / "current"
    with pytest.raises(DatasetError, match="checksum differs"):
        pull_dataset(manifest, destination, archive_path=archive)
    assert not destination.exists()


@pytest.mark.parametrize("name", ["../escape", "/absolute", "C:/windows", "a\\b", "a//b"])
def test_zip_invalid_paths_never_escape_staging(tmp_path, name):
    manifest, archive = dataset_zip(tmp_path, {name: b"untrusted"})
    destination = tmp_path / "current"
    with pytest.raises(DatasetError, match="Invalid dataset member"):
        pull_dataset(manifest, destination, archive_path=archive)
    assert not destination.exists()
    assert not (tmp_path / "escape").exists()


def test_zip_symlink_is_rejected(tmp_path):
    member = ZipInfo("link")
    member.external_attr = (stat.S_IFLNK | 0o777) << 16
    manifest, archive = dataset_zip(tmp_path, {member: "../escape"})
    with pytest.raises(DatasetError, match="symbolic links"):
        pull_dataset(manifest, tmp_path / "current", archive_path=archive)


def test_missing_required_member_and_size_limits(tmp_path):
    manifest, archive = dataset_zip(tmp_path)
    manifest["required_files"]["missing.txt"] = "0" * 64
    with pytest.raises(DatasetError, match="lacks required"):
        pull_dataset(manifest, tmp_path / "current", archive_path=archive)
    del manifest["required_files"]["missing.txt"]
    manifest["archive"]["max_expanded_bytes"] = 1
    with pytest.raises(DatasetError, match="expanded size"):
        pull_dataset(manifest, tmp_path / "current", archive_path=archive)


def test_downloader_override_is_used_then_hash_verified(tmp_path):
    manifest, archive = dataset_zip(tmp_path)
    calls = []

    def download(url, output, size):
        calls.append((url, size))
        shutil.copyfile(archive, output)

    result = pull_dataset(
        manifest, tmp_path / "current", url="https://example.org/data.zip", downloader=download
    )
    assert result["status"] == "installed"
    assert calls == [("https://example.org/data.zip", archive.stat().st_size)]


def test_public_drive_download_does_not_use_browser_cookies(tmp_path, monkeypatch):
    calls = []

    def fake_download(**kwargs):
        calls.append(kwargs)
        Path(kwargs["output"]).write_bytes(b"ZIP")
        return kwargs["output"]

    monkeypatch.setitem(sys.modules, "gdown", SimpleNamespace(download=fake_download))
    download_archive("https://drive.google.com/file/d/id/view", tmp_path / "file.zip", 3)
    assert calls[0]["use_cookies"] is False
    assert calls[0]["timeout"] == 60
    assert calls[0]["retries"] == 2


def test_missing_url_and_non_dev_manifest_are_rejected(tmp_path):
    manifest, _ = dataset_zip(tmp_path)
    manifest["archive"]["url"] = None
    with pytest.raises(DatasetError, match="Provide --url"):
        pull_dataset(manifest, tmp_path / "current")
    manifest["distribution"] = "MASTER"
    file = tmp_path / "manifest.json"
    file.write_text(json.dumps(manifest))
    with pytest.raises(DatasetError, match="only DEV_VALIDATION"):
        read_manifest(file)
