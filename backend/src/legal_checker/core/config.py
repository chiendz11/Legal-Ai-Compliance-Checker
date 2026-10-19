import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[3]
PROJECT_ROOT = BACKEND_ROOT.parent
DEFAULT_DATABASE_URL = (
    "postgresql://legal_checker:legal_checker_local_only@127.0.0.1:5433/legal_checker_dev"
)


def _project_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


@dataclass(frozen=True)
class Settings:
    database_url: str
    knowledge_snapshot_sha256: str | None = None
    source_cache_dir: Path = PROJECT_ROOT / "data/private/source_cache"
    source_download_timeout_seconds: float = 30
    source_max_bytes: int = 100 * 1024 * 1024
    # "reference" replays QA references (integration only); "none" until A/B/C deliver.
    assessment_modules: str = "none"
    # "inline" runs jobs in the API process; "celery" sends them to the Redis-backed worker.
    assessment_queue: str = "inline"
    redis_url: str = "redis://127.0.0.1:6379/0"
    run_lease_seconds: int = 600
    run_requeue_after_seconds: int = 120
    report_export_dir: Path = PROJECT_ROOT / "data/private/report_exports"

    @classmethod
    def from_env(cls):
        load_dotenv(PROJECT_ROOT / ".env", override=False)
        cache_dir = _project_path(os.getenv("SOURCE_CACHE_DIR", "data/private/source_cache"))
        return cls(
            database_url=os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL),
            knowledge_snapshot_sha256=os.getenv("KNOWLEDGE_SNAPSHOT_SHA256") or None,
            source_cache_dir=cache_dir,
            source_download_timeout_seconds=float(
                os.getenv("SOURCE_DOWNLOAD_TIMEOUT_SECONDS", "30")
            ),
            source_max_bytes=int(os.getenv("SOURCE_MAX_BYTES", str(100 * 1024 * 1024))),
            assessment_modules=os.getenv("ASSESSMENT_MODULES", "none"),
            assessment_queue=os.getenv("ASSESSMENT_QUEUE", "inline"),
            redis_url=os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
            run_lease_seconds=int(os.getenv("RUN_LEASE_SECONDS", "600")),
            run_requeue_after_seconds=int(os.getenv("RUN_REQUEUE_AFTER_SECONDS", "120")),
            report_export_dir=_project_path(
                os.getenv("REPORT_EXPORT_DIR", "data/private/report_exports")
            ),
        )
