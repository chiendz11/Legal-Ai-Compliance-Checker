"""Export module boundary schemas; no fixtures, seed files or DB connection needed."""

import json
from pathlib import Path

from legal_checker.shared.contracts.handoffs import HandoffSet


def main():
    Path("docs/module_contracts.schema.json").write_text(
        json.dumps(HandoffSet.model_json_schema(), ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
