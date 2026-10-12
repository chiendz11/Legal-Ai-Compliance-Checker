"""Export the shared handoff schemas for independent module implementations."""

from app.contracts.handoffs import HandoffSet
from app.shared.config import PROJECT_ROOT
from devtools.parallel import json_text


def main():
    schema = HandoffSet.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    target = PROJECT_ROOT / "docs/parallel_contracts.schema.json"
    target.write_text(json_text(schema), encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
