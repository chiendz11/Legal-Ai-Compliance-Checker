"""Export the shared handoff schemas for independent module implementations."""

from devtools.parallel import json_text
from legal_checker.core.config import PROJECT_ROOT
from legal_checker.shared.contracts.handoffs import HandoffSet


def main():
    schema = HandoffSet.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    target = PROJECT_ROOT / "docs/parallel_contracts.schema.json"
    target.write_text(json_text(schema), encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
