"""Install a pinned local dataset without changing the database or existing files."""

import hashlib
import json
import shutil
import stat
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from zipfile import BadZipFile, ZipFile


class DatasetError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def member_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if (
        not name
        or path.is_absolute()
        or ".." in path.parts
        or "\\" in name
        or "\x00" in name
        or ":" in name
        or path.as_posix() != name.rstrip("/")
    ):
        raise DatasetError(f"Invalid dataset member path: {name}")
    return path


def read_manifest(path: Path) -> dict:
    manifest = json.loads(path.read_text())
    if manifest.get("manifest_version") != 1:
        raise DatasetError("Unsupported dataset manifest version")
    if manifest.get("distribution") != "DEV_VALIDATION":
        raise DatasetError("This command installs only DEV_VALIDATION")
    archive = manifest["archive"]
    files = manifest["required_files"]
    if not files or manifest["workbook"] not in files:
        raise DatasetError("Manifest must pin its full seed workbook")
    for name in files:
        member_path(name)
    for digest in [archive["sha256"], *files.values()]:
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise DatasetError("Manifest contains an invalid SHA-256")
    if archive["bytes"] <= 0 or archive["max_expanded_bytes"] <= 0:
        raise DatasetError("Manifest contains invalid archive sizes")
    return manifest


def check_dataset(manifest: dict, destination: Path) -> dict:
    if destination.is_symlink() or not destination.is_dir():
        raise DatasetError(f"Dataset directory unavailable: {destination}")
    for name, expected in manifest["required_files"].items():
        path = destination.joinpath(*member_path(name).parts)
        if (
            not path.is_file()
            or path.is_symlink()
            or not path.resolve().is_relative_to(destination.resolve())
        ):
            raise DatasetError(f"Dataset missing required local file: {name}")
        if sha256_file(path) != expected:
            raise DatasetError(f"Dataset file checksum differs: {name}")
    return {
        "dataset_version": manifest["dataset_version"],
        "distribution": manifest["distribution"],
        "destination": str(destination.resolve()),
        "verified_files": len(manifest["required_files"]),
        "seed_workbook_path": str((destination / manifest["workbook"]).resolve()),
        "workbook_sha256": manifest["required_files"][manifest["workbook"]],
        "database_changed": False,
    }


def download_archive(url: str, output: Path, expected_bytes: int) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise DatasetError("Dataset download URL must use HTTPS")
    if parsed.hostname in ("drive.google.com", "docs.google.com"):
        try:
            import gdown
        except ImportError as error:
            raise DatasetError(
                "Install the downloader: pip install -e './backend[dataset]'"
            ) from error

        def progress(size, total):
            if size > expected_bytes:
                raise DatasetError("Download is larger than the pinned DEV_VALIDATION archive")

        try:
            result = gdown.download(
                url=url,
                output=str(output),
                use_cookies=False,
                quiet=False,
                timeout=60,
                retries=2,
                progress=progress,
            )
        except Exception as error:
            raise DatasetError(
                "Drive download failed. Check sharing/quota, or download in your browser "
                "and use dataset pull --archive /path/to/DEV_VALIDATION.zip."
            ) from error
        if not result or not output.is_file():
            raise DatasetError("Drive did not return a downloadable ZIP")
        return
    request = Request(url, headers={"User-Agent": "LegalChecker-Dataset/1.0"})
    with urlopen(request, timeout=60) as response, output.open("wb") as target:
        count = 0
        for block in iter(lambda: response.read(1024 * 1024), b""):
            count += len(block)
            if count > expected_bytes:
                raise DatasetError("Download exceeds the pinned archive size")
            target.write(block)


def extract_dataset(manifest: dict, archive_path: Path, destination: Path) -> None:
    archive_spec = manifest["archive"]
    if archive_path.stat().st_size != archive_spec["bytes"]:
        raise DatasetError("ZIP size differs from the pinned DEV_VALIDATION archive")
    if sha256_file(archive_path) != archive_spec["sha256"]:
        raise DatasetError("ZIP SHA-256 differs: use the exact published DEV_VALIDATION ZIP")
    try:
        with ZipFile(archive_path) as archive:
            members = archive.infolist()
            names = [item.filename for item in members]
            if len(names) != len(set(names)):
                raise DatasetError("ZIP contains duplicate paths")
            if sum(item.file_size for item in members) > archive_spec["max_expanded_bytes"]:
                raise DatasetError("ZIP expanded size exceeds the manifest limit")
            for item in members:
                # ZipInfo normalizes backslashes (Windows) and truncates at NUL.
                # Validate the name as stored, before that lossy normalization.
                member_path(item.orig_filename)
                member_path(item.filename)
                if stat.S_ISLNK(item.external_attr >> 16):
                    raise DatasetError("ZIP contains symbolic links")
            if not set(manifest["required_files"]).issubset(names):
                raise DatasetError("ZIP lacks required dataset files")
            # Install the DB seed and reference texts. PDFs remain available via Supabase.
            for name in manifest["required_files"]:
                target = destination.joinpath(*member_path(name).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(name) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output, 1024 * 1024)
    except BadZipFile as error:
        raise DatasetError("Downloaded file is not a valid ZIP") from error


def pull_dataset(
    manifest: dict,
    destination: Path,
    *,
    url: str | None = None,
    archive_path: Path | None = None,
    downloader=download_archive,
) -> dict:
    if destination.exists() or destination.is_symlink():
        try:
            result = check_dataset(manifest, destination)
        except DatasetError as error:
            raise DatasetError(
                f"Existing dataset folder was preserved: {error}. "
                "Use another destination or restore the expected files."
            ) from error
        return {"status": "already_present", **result}
    source_url = url or manifest["archive"].get("url")
    if archive_path is None and not source_url:
        raise DatasetError("Provide --url, DATASET_ARCHIVE_URL, or --archive")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".dataset-pull-", dir=destination.parent) as temporary:
        staging = Path(temporary)
        if archive_path is None:
            archive_path = staging / "dataset.zip"
            downloader(source_url, archive_path, manifest["archive"]["bytes"])
        elif not archive_path.is_file():
            raise DatasetError(f"Local ZIP unavailable: {archive_path}")
        ready = staging / "ready"
        ready.mkdir()
        extract_dataset(manifest, archive_path, ready)
        check_dataset(manifest, ready)
        if destination.exists() or destination.is_symlink():
            raise DatasetError("Destination appeared during download; existing data was preserved")
        ready.rename(destination)
    return {"status": "installed", **check_dataset(manifest, destination)}
