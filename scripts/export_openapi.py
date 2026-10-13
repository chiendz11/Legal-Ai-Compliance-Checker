"""Export versioned API schemas without creating a runtime database in the repository."""

import json
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from legal_checker.core.config import Settings
from legal_checker.main import create_app


def main():
    with TemporaryDirectory() as directory:
        settings = replace(Settings.from_env(), database_path=Path(directory) / "runtime.sqlite3")
        api = create_app(settings=settings)
        Path("docs/openapi.json").write_text(
            json.dumps(api.openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
