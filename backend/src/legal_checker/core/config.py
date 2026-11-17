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
    documents_extractor: str = "rules"
    documents_llm_provider: str = "ollama"
    documents_ollama_url: str = "http://127.0.0.1:11434"
    documents_ollama_model: str = "qwen3.5:9b-q4_K_M"
    documents_llm_max_calls: int = 2
    documents_llm_timeout_seconds: float = 240
    documents_llm_recheck_existing: bool = False
    c11_personalization: str = "off"
    c11_ollama_url: str = "http://127.0.0.1:11434"
    c11_ollama_model: str = "qwen3.5:9b-q4_K_M"
    c11_llm_timeout_seconds: float = 240
    c11_llm_context_tokens: int = 4096
    c11_llm_output_tokens: int = 512
    c11_llm_num_threads: int = 4
    c11_llm_max_calls: int = 10
    c11_llm_max_input_chars: int = 12000
    c11_llm_total_budget_seconds: float = 600
    # "modules": read real bytes (including remote URLs), never silently replay QA;
    # "modules_di_reference": explicitly allow dataset DI for development;
    # "reference": replay QA end to end; "none": fail clearly.
    assessment_modules: str = "none"
    # C07 observations: "offline" (no calls, UNKNOWN), "openai", "groq", or "ollama".
    assessment_llm: str = "offline"
    assessment_llm_max_calls: int = 20
    assessment_llm_batch_size: int = 1
    assessment_llm_max_context_chars: int = 80000
    c07_ollama_url: str = "http://127.0.0.1:11434"
    c07_ollama_model: str = "qwen3:4b-q4_K_M"
    c07_ollama_context_tokens: int = 8192
    c07_ollama_num_threads: int = 4
    c07_llm_timeout_seconds: float = 240
    c07_llm_max_output_tokens: int = 3000
    # Explicit, hash-bound study sources. None keeps ordinary source-only checks.
    synthetic_scenario_path: Path | None = None
    assessment_full_document_review: bool = True
    # "inline" runs jobs in the API process; "celery" sends them to the Redis-backed worker.
    assessment_queue: str = "inline"
    redis_url: str = "redis://127.0.0.1:6379/0"
    run_lease_seconds: int = 600
    run_requeue_after_seconds: int = 120
    report_export_dir: Path = PROJECT_ROOT / "data/private/report_exports"
    upload_dir: Path = PROJECT_ROOT / "data/private/uploads"
    # Deployment pins for new cases; default to the versions existing cases of the release use.
    deployment_rule_version: str | None = None
    deployment_legal_knowledge_version: str | None = None
    # Caller identity when auth is off (local development only).
    dev_actor_id: str = "LOCAL_DEV"
    dev_tenant_id: str = "LOCAL_SOURCE_PDF360"
    # "on": login required (local accounts, signed session cookie); "off": dev identity above.
    auth_mode: str = "off"
    auth_secret: str | None = None
    auth_session_hours: int = 8

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
            documents_extractor=os.getenv("DOCUMENTS_EXTRACTOR", "rules"),
            documents_llm_provider=os.getenv("DOCUMENTS_LLM_PROVIDER", "ollama"),
            documents_ollama_url=os.getenv("DOCUMENTS_OLLAMA_URL", "http://127.0.0.1:11434"),
            documents_ollama_model=os.getenv("DOCUMENTS_OLLAMA_MODEL", "qwen3.5:9b-q4_K_M"),
            documents_llm_max_calls=int(os.getenv("DOCUMENTS_LLM_MAX_CALLS", "2")),
            documents_llm_timeout_seconds=float(os.getenv("DOCUMENTS_LLM_TIMEOUT_SECONDS", "240")),
            documents_llm_recheck_existing=os.getenv(
                "DOCUMENTS_LLM_RECHECK_EXISTING", "off"
            ).lower()
            in {"on", "true", "1"},
            c11_personalization=os.getenv("C11_PERSONALIZATION", "off"),
            c11_ollama_url=os.getenv("C11_OLLAMA_URL", "http://127.0.0.1:11434"),
            c11_ollama_model=os.getenv("C11_OLLAMA_MODEL", "qwen3.5:9b-q4_K_M"),
            c11_llm_timeout_seconds=float(os.getenv("C11_LLM_TIMEOUT_SECONDS", "240")),
            c11_llm_context_tokens=int(os.getenv("C11_LLM_CONTEXT_TOKENS", "4096")),
            c11_llm_output_tokens=int(os.getenv("C11_LLM_OUTPUT_TOKENS", "512")),
            c11_llm_num_threads=int(os.getenv("C11_LLM_NUM_THREADS", "4")),
            c11_llm_max_calls=int(os.getenv("C11_LLM_MAX_CALLS", "10")),
            c11_llm_max_input_chars=int(os.getenv("C11_LLM_MAX_INPUT_CHARS", "12000")),
            c11_llm_total_budget_seconds=float(os.getenv("C11_LLM_TOTAL_BUDGET_SECONDS", "600")),
            assessment_modules=os.getenv("ASSESSMENT_MODULES", "none"),
            assessment_llm=os.getenv("ASSESSMENT_LLM", "offline"),
            assessment_llm_max_calls=int(os.getenv("ASSESSMENT_LLM_MAX_CALLS", "20")),
            assessment_llm_batch_size=int(os.getenv("ASSESSMENT_LLM_BATCH_SIZE", "1")),
            assessment_llm_max_context_chars=int(
                os.getenv("ASSESSMENT_LLM_MAX_CONTEXT_CHARS", "80000")
            ),
            c07_ollama_url=os.getenv("C07_OLLAMA_URL", "http://127.0.0.1:11434"),
            c07_ollama_model=os.getenv("C07_OLLAMA_MODEL", "qwen3:4b-q4_K_M"),
            c07_ollama_context_tokens=int(os.getenv("C07_OLLAMA_CONTEXT_TOKENS", "8192")),
            c07_ollama_num_threads=int(os.getenv("C07_OLLAMA_NUM_THREADS", "4")),
            c07_llm_timeout_seconds=float(os.getenv("C07_LLM_TIMEOUT_SECONDS", "240")),
            c07_llm_max_output_tokens=int(os.getenv("C07_LLM_MAX_OUTPUT_TOKENS", "3000")),
            synthetic_scenario_path=(
                _project_path(os.environ["SYNTHETIC_SCENARIO_PATH"])
                if os.getenv("SYNTHETIC_SCENARIO_PATH")
                else None
            ),
            assessment_full_document_review=os.getenv(
                "ASSESSMENT_FULL_DOCUMENT_REVIEW", "on"
            ).lower()
            in {"on", "true", "1"},
            assessment_queue=os.getenv("ASSESSMENT_QUEUE", "inline"),
            redis_url=os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
            run_lease_seconds=int(os.getenv("RUN_LEASE_SECONDS", "600")),
            run_requeue_after_seconds=int(os.getenv("RUN_REQUEUE_AFTER_SECONDS", "120")),
            report_export_dir=_project_path(
                os.getenv("REPORT_EXPORT_DIR", "data/private/report_exports")
            ),
            upload_dir=_project_path(os.getenv("UPLOAD_DIR", "data/private/uploads")),
            deployment_rule_version=os.getenv("DEPLOYMENT_RULE_VERSION") or None,
            deployment_legal_knowledge_version=(
                os.getenv("DEPLOYMENT_LEGAL_KNOWLEDGE_VERSION") or None
            ),
            dev_actor_id=os.getenv("DEV_ACTOR_ID", "LOCAL_DEV"),
            dev_tenant_id=os.getenv("DEV_TENANT_ID", "LOCAL_SOURCE_PDF360"),
            auth_mode=os.getenv("AUTH_MODE", "off"),
            auth_secret=os.getenv("AUTH_SECRET") or None,
            auth_session_hours=int(os.getenv("AUTH_SESSION_HOURS", "8")),
        )
