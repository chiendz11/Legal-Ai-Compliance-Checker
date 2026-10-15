import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[3]
PROJECT_ROOT = BACKEND_ROOT.parent
DEFAULT_DATABASE_URL = (
    "postgresql://legal_checker:legal_checker_local_only@127.0.0.1:5433/legal_checker_dev"
)


@dataclass(frozen=True)
class Settings:
    database_url: str
    knowledge_snapshot_sha256: str | None = None
    source_cache_dir: Path = PROJECT_ROOT / "data/private/source_cache"
    source_download_timeout_seconds: float = 30
    source_max_bytes: int = 100 * 1024 * 1024

    @classmethod
    def from_env(cls):
        load_dotenv(PROJECT_ROOT / ".env", override=False)
        cache_dir = Path(os.getenv("SOURCE_CACHE_DIR", "data/private/source_cache")).expanduser()
        if not cache_dir.is_absolute():
            cache_dir = PROJECT_ROOT / cache_dir
        return cls(
            database_url=os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL),
            knowledge_snapshot_sha256=os.getenv("KNOWLEDGE_SNAPSHOT_SHA256") or None,
            source_cache_dir=cache_dir,
            source_download_timeout_seconds=float(
                os.getenv("SOURCE_DOWNLOAD_TIMEOUT_SECONDS", "30")
            ),
            source_max_bytes=int(os.getenv("SOURCE_MAX_BYTES", str(100 * 1024 * 1024))),
        )
