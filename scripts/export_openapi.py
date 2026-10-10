"""Export versioned API schemas without creating a runtime database in the repository."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from app.main import create_app


def main():
    with TemporaryDirectory() as directory:
        api = create_app(database_path=Path(directory) / "runtime.sqlite3")
        Path("docs/openapi.json").write_text(
            json.dumps(api.openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
