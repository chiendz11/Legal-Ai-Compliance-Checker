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

    @classmethod
    def from_env(cls):
        load_dotenv(PROJECT_ROOT / ".env", override=False)
        return cls(
            database_url=os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL),
            knowledge_snapshot_sha256=os.getenv("KNOWLEDGE_SNAPSHOT_SHA256") or None,
        )
