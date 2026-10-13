"""Export API schemas without opening or modifying a database."""

import json
from pathlib import Path

from legal_checker.api.dependencies import Services
from legal_checker.main import create_app


def main():
    # Schema-only factory: handlers are never invoked during export.
    api = create_app(services=Services(knowledge=None, assessments=None))
    Path("docs/openapi.json").write_text(
        json.dumps(api.openapi(), ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
