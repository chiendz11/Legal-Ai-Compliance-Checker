import os
from dataclasses import dataclass
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]
PROJECT_ROOT = BACKEND_ROOT.parent


@dataclass(frozen=True)
class Settings:
    knowledge_path: Path
    database_path: Path

    @classmethod
    def from_env(cls):
        return cls(
            knowledge_path=Path(os.getenv("KNOWLEDGE_PATH", PROJECT_ROOT / "data/knowledge.json")),
            database_path=Path(
                os.getenv("DATABASE_PATH", PROJECT_ROOT / "data/private/runtime.sqlite3")
            ),
        )
