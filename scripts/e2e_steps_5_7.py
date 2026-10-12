"""Exercise independent C07–C11 APIs, pipeline persistence and run idempotency over HTTP."""

import argparse
import json
from pathlib import Path
from uuid import uuid4

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--input", type=Path, default=Path("examples/steps_5_7.json"))
    parser.add_argument("--output", type=Path, default=Path("data/private/e2e_result.json"))
    args = parser.parse_args()
    request = json.loads(args.input.read_text(encoding="utf-8"))
    request["run_id"] = "E2E_" + uuid4().hex
    request["trace_id"] = request["run_id"]
    for retrieval in request["payload"]["retrieval"]:
        retrieval["lan_chay_id"] = request["run_id"]
    for citation in request["payload"].get("citations", []):
        citation["lan_chay_id"] = request["run_id"]
    context = {k: v for k, v in request.items() if k not in ("contract_name", "payload")}
    with httpx.Client(base_url=args.base_url, timeout=30) as client:

        def post(path, payload):
            response = client.post(path, json=payload)
            response.raise_for_status()
            return response.json()

        reasoning_request = {
            **context,
            "contract_name": "CriterionReasoningInput",
            "payload": {k: v for k, v in request["payload"].items() if k != "citations"},
        }
        criteria = post("/api/v1/reasoning", reasoning_request)["payload"]
        intermediate = {
            **context,
            "payload": {
                "hop_dong_id": request["payload"]["hop_dong_id"],
                "requirements": request["payload"]["requirements"],
                "criterion_results": criteria,
            },
        }
        requirements = post("/api/v1/aggregation", intermediate)["payload"]
        risks = post(
            "/api/v1/risks",
            {
                **intermediate,
                "payload": {
                    **intermediate["payload"],
                    "citations": request["payload"].get("citations", []),
                },
            },
        )["payload"]
        recommendations = post(
            "/api/v1/recommendations",
            {
                **context,
                "payload": {
                    "hop_dong_id": request["payload"]["hop_dong_id"],
                    "requirements": request["payload"]["requirements"],
                    "risks": risks,
                },
            },
        )["payload"]
        pipeline = post("/api/v1/pipeline/steps-5-7", request)
        expected = {
            "criterion_results": criteria,
            "requirement_results": requirements,
            "risks": risks,
            "recommendations": recommendations,
        }
        for key, value in expected.items():
            if pipeline["payload"][key] != value:
                raise RuntimeError(f"Pipeline and standalone module output differ: {key}")
        stored = client.get(f"/api/v1/cases/{request['ca_id']}/runs/{request['run_id']}")
        stored.raise_for_status()
        if stored.json() != pipeline or post("/api/v1/pipeline/steps-5-7", request) != pipeline:
            raise RuntimeError("Persistence or idempotency check failed")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(pipeline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "run_id": request["run_id"],
                "criterion_findings": [r["finding"] for r in criteria],
                "requirement_statuses": [r["status"] for r in requirements],
                "risk_count": len(risks),
                "recommendation_count": len(recommendations),
                "output": str(args.output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
