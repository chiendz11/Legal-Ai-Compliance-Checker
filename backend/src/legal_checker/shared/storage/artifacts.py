"""Immutable evidence files shared by API and worker, addressed by exact bytes."""

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StoredArtifact:
    path: Path
    sha256: str

    @property
    def uri(self):
        return f"artifact://evidence/{self.sha256}.json"


def store_bytes(directory: Path, raw: bytes) -> StoredArtifact:
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    digest = hashlib.sha256(raw).hexdigest()
    path = directory / f"{digest}.json"
    with tempfile.NamedTemporaryFile(dir=directory, delete=False) as temporary:
        temporary.write(raw)
        temporary.flush()
        os.fsync(temporary.fileno())
        name = Path(temporary.name)
    try:
        try:
            os.link(name, path)
        except FileExistsError:
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise ValueError("Evidence artifact was changed after registration") from None
    finally:
        name.unlink(missing_ok=True)
    return StoredArtifact(path, digest)


def store_json(directory: Path, value) -> StoredArtifact:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    return store_bytes(directory, raw)
