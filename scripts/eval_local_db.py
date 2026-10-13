"""Evaluate frozen QA references in local SQL; no writes or LLM/OCR-accuracy claims."""

import argparse
import json

from devtools.evaluation_controls import verify_control
from devtools.qa_validation import join_artifacts
from legal_checker.core.config import Settings
from legal_checker.core.postgres import connect_postgres
from legal_checker.modules.assessments.audit import digest
from legal_checker.modules.legal_knowledge.repository import Knowledge
from legal_checker.shared.contracts.pipeline import PipelineRequest, PipelineResponse
from legal_checker.workflows.steps_5_7 import evaluate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=Settings.from_env().database_url)
    parser.add_argument(
        "--split", choices=("DEV", "VALIDATION", "TEST", "REGRESSION"), required=True
    )
    args = parser.parse_args()
    knowledge = Knowledge(args.database_url)
    passed = []
    failed = []
    with connect_postgres(args.database_url) as connection:
        cases = connection.execute(
            "SELECT * FROM qa.case_manifest WHERE split=%s ORDER BY case_id", (args.split,)
        ).fetchall()
        if not cases:
            parser.error("No cases in requested split; seed the appropriate workbook first")
        pending_documents = [c["case_id"] for c in cases if c["module_scope"] == "DOCUMENTS"]
        for case in cases:
            if case["module_scope"] == "DOCUMENTS":
                continue
            cid = case["case_id"]
            try:
                if case["knowledge_snapshot_sha256"] != knowledge.sha256:
                    raise ValueError("QA knowledge hash differs from current SQL knowledge")
                rows = connection.execute(
                    "SELECT * FROM qa.artifacts WHERE case_id=%s", (cid,)
                ).fetchall()
                artifacts = join_artifacts(rows)
                raw = artifacts[(cid, "INPUT", "PipelineRequest", cid)]
                if case["case_kind"] == "CONTROLLED":
                    assertions = connection.execute(
                        "SELECT * FROM qa.controlled_assertions WHERE case_id=%s", (cid,)
                    ).fetchone()
                    verify_control(
                        {
                            "case_id": cid,
                            "input": raw,
                            "expected": assertions["expected_assertions_json"],
                        },
                        knowledge,
                    )
                else:
                    expected = PipelineResponse.model_validate(
                        artifacts[(cid, "EXPECTED", "PipelineResponse", cid)]
                    )
                    actual = evaluate(PipelineRequest.model_validate(raw), knowledge)
                    if digest(actual.payload) != digest(expected.payload):
                        raise ValueError("Output differs from deterministic reference")
                passed.append(cid)
            except (ValueError, AssertionError, KeyError) as error:
                failed.append({"case_id": cid, "error": str(error)})
    print(
        json.dumps(
            {
                "split": args.split,
                "passed": len(passed),
                "failed": failed,
                "metric_kind": "SYNTHETIC_SPEC_CHECK"
                if args.split == "REGRESSION"
                else "DETERMINISTIC_REFERENCE_REPLAY",
                "legal_accuracy_measured": False,
                "ocr_or_llm_quality_measured": False,
                "pending_document_implementation": pending_documents,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
