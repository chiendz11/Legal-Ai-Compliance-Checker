"""Run real deterministic steps 5–7 using a QA input, with new immutable run IDs."""

import argparse
import json

from devtools.qa_runs import new_run
from devtools.qa_validation import join_artifacts
from legal_checker.core.config import Settings
from legal_checker.core.postgres import connect_postgres
from legal_checker.modules.assessments.repository import Store
from legal_checker.modules.legal_knowledge.repository import Knowledge
from legal_checker.workflows.steps_5_7 import evaluate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=Settings.from_env().database_url)
    parser.add_argument("--case", required=True)
    parser.add_argument("--run", required=True)
    args = parser.parse_args()
    with connect_postgres(args.database_url) as connection:
        manifest = connection.execute(
            "SELECT * FROM qa.case_manifest WHERE case_id=%s", (args.case,)
        ).fetchone()
        if not manifest or manifest["case_kind"] != "CORPUS":
            parser.error("Choose a corpus case from the DEV_VALIDATION workbook")
        if manifest["split"] == "TEST":
            parser.error("Use an evaluator harness for held-out TEST cases")
        rows = connection.execute(
            "SELECT * FROM qa.artifacts WHERE case_id=%s AND role='INPUT' "
            "AND contract_name='PipelineRequest'",
            (args.case,),
        ).fetchall()
    raw = join_artifacts(rows)[(args.case, "INPUT", "PipelineRequest", args.case)]
    if args.run == raw["run_id"]:
        parser.error("Choose a new run ID, different from the frozen reference")
    request = new_run(raw, args.run)
    knowledge = Knowledge(args.database_url, request.knowledge_snapshot_sha256)
    store = Store(args.database_url)
    response = store.save(request, evaluate(request, knowledge))
    print(
        json.dumps(
            {
                "ca_id": response.ca_id,
                "run_id": response.run_id,
                "criterion_results": len(response.payload.criterion_results),
                "requirement_statuses": [r.status for r in response.payload.requirement_results],
                "risks": len(response.payload.risks),
                "recommendations": len(response.payload.recommendations),
                "producer": "DETERMINISTIC_STEPS_5_7_NO_LLM",
                "persisted_in_postgresql": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
