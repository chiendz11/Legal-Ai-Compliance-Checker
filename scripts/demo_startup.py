"""Demonstrate startup and steps 5–7 persistence with a temporary SQLite database.

Run from the repository root: python -m scripts.demo_startup
"""

import json
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from legal_checker.api.dependencies import build_services
from legal_checker.core.config import PROJECT_ROOT, Settings
from legal_checker.main import create_app
from legal_checker.shared.contracts.pipeline import PipelineRequest
from legal_checker.workflows.steps_5_7 import evaluate


def main():
    with TemporaryDirectory() as directory:
        # 1. Settings only describes where data lives; it does not open files/DBs.
        settings = replace(Settings.from_env(), database_path=Path(directory) / "demo.sqlite3")

        # 2. Read knowledge and prepare SQLite; now we have real objects to call.
        services = build_services(settings)

        # 3. Hand the same objects to FastAPI; create_app does not construct them again.
        api = create_app(settings=settings, services=services)
        assert api.state.services is services

        # 4. Execute the workflow and save/retrieve its result using those objects.
        request = PipelineRequest.model_validate_json(
            (PROJECT_ROOT / "examples/steps_5_7.json").read_text(encoding="utf-8")
        )
        result = evaluate(request, services.knowledge)
        saved = services.assessments.save(request, result)
        restored = services.assessments.get(request.ca_id, request.run_id)
        if restored != saved:
            raise RuntimeError("The stored result did not match the workflow output")

        print(
            json.dumps(
                {
                    "knowledge_adapter": type(services.knowledge).__name__,
                    "knowledge_tables": len(services.knowledge.tables),
                    "criteria_loaded": len(services.knowledge.criteria),
                    "database_adapter": type(services.assessments).__name__,
                    "database_created": settings.database_path.is_file(),
                    "api_reuses_services": api.state.services is services,
                    "criterion_results": len(saved.payload.criterion_results),
                    "requirement_results": len(saved.payload.requirement_results),
                    "risks": len(saved.payload.risks),
                    "recommendations": len(saved.payload.recommendations),
                    "saved_result_matches": restored == saved,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    print("Demo completed; its temporary database has been removed.")


if __name__ == "__main__":
    main()
