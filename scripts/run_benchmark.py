"""Run PDF inputs through the real assessment API and persist predictions for offline scoring."""

import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from uuid import uuid4

import httpx


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, payload):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def inputs(root, case_ids, split):
    root = root.resolve()
    index = {row["case_id"]: row for row in read_json(root / "SOURCE_INDEX.json")}
    if case_ids is None:
        case_ids = sorted(key for key, row in index.items() if row["split"] == split)
    for case_id in case_ids:
        if not re.fullmatch(r"CA360_[0-9]{3}", case_id) or case_id not in index:
            raise ValueError(f"Unrecognized case {case_id}")
        row = index[case_id]
        if row["split"] != split:
            raise ValueError(f"{case_id} belongs to {row['split']}, not {split}")
        pdf, intake = ((root / row[key]).resolve() for key in ("pdf_path", "intake_path"))
        if not pdf.is_relative_to(root / "sources" / "pdf") or not intake.is_relative_to(
            root / "public_inputs"
        ):
            raise ValueError(f"Invalid source path for {case_id}")
        source = read_json(intake)
        if source["case"]["ca_id"] != case_id:
            raise ValueError(f"Intake case mismatch for {case_id}")
        with pdf.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != row["source_sha256"] or digest != source["case"]["source"]["sha256"]:
            raise ValueError(f"PDF hash mismatch for {case_id}")
        yield row, pdf, source


def request(client, method, path, *, check_module=False, **kwargs):
    response = client.request(method, path, **kwargs)
    response.raise_for_status()
    if check_module and response.headers.get("X-Module-Source") != "MODULES":
        raise ValueError("Run did not declare real MODULES source")
    return response.json()


def assert_pin(actual, expected, keys):
    for key in keys:
        if actual.get(key) != expected.get(key):
            raise ValueError(f"Run pin mismatch on {key}")


def run_case(client, row, pdf, source, folder, timeout):
    started = time.monotonic()
    with pdf.open("rb") as stream:
        contract = request(
            client,
            "POST",
            "/api/v1/contracts",
            files={"file": (pdf.name, stream, "application/pdf")},
            data={"ten_tai_lieu": f"Benchmark {row['case_id']} {folder.parent.name}"},
        )
    if contract["source"]["sha256"] != row["source_sha256"]:
        raise ValueError("Uploaded PDF hash mismatch")
    expected = source["case"]
    deployment, timing = expected["deployment"], expected["assessment_context"]
    case = request(
        client,
        "POST",
        "/api/v1/cases",
        json={
            "hop_dong_id": contract["hop_dong_id"],
            "phien_ban_id": deployment["phien_ban_id"],
            **timing,
        },
    )["case"]
    assert_pin(case["assessment_context"], timing, timing)
    assert_pin(case["deployment"], deployment, deployment)
    case_path = f"/api/v1/cases/{case['ca_id']}"
    accepted = request(
        client,
        "POST",
        f"{case_path}/runs",
        check_module=True,
        headers={"Idempotency-Key": "benchmark-" + uuid4().hex},
    )
    write_json(folder / "accepted.json", accepted)
    context = accepted["context"]
    assert_pin(context, case, ("ca_id",))
    keys = ("ca_id", "run_id", "trace_id", "knowledge_snapshot_sha256", *deployment)
    assert_pin(
        context, {**source["context"], **deployment}, ("knowledge_snapshot_sha256", *deployment)
    )
    run_path = f"{case_path}/runs/{context['run_id']}"
    while True:
        status = request(client, "GET", f"{run_path}/status", check_module=True)
        assert_pin(status["context"], context, keys)
        if status["status"] in {"COMPLETED", "FAILED"} or time.monotonic() - started > timeout:
            write_json(folder / "status.json", status)
            break
        time.sleep(1)
    receipt = {
        "case_id": row["case_id"],
        "runtime_case_id": case["ca_id"],
        "run_id": context["run_id"],
        "group_id": row["group_id"],
        "split": row["split"],
        "source_sha256": row["source_sha256"],
        "knowledge_snapshot_sha256": context["knowledge_snapshot_sha256"],
        "module_source": "MODULES",
        "status": status["status"],
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }
    if status["status"] == "COMPLETED":
        result = request(client, "GET", f"{run_path}/results", check_module=True)
        assert_pin(result["context"], context, keys)
        if result["case"]["source"]["sha256"] != row["source_sha256"]:
            raise ValueError("Result source hash mismatch")
        reports = request(client, "GET", f"{run_path}/reports")["items"]
        if not reports or any(report["run_id"] != context["run_id"] for report in reports):
            raise ValueError("Missing or mismatched report")
        write_json(folder / "prediction.json", result)
        write_json(folder / "reports.json", reports)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--split", choices=["DEV", "VALIDATION", "TEST"], required=True)
    parser.add_argument("--case", nargs="+", help="If omitted, use all cases in --split")
    parser.add_argument("--api", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=1200)
    args = parser.parse_args()
    if (args.case and len(set(args.case)) != len(args.case)) or args.timeout <= 0:
        parser.error("Pass unique case IDs and a positive timeout")
    plan = list(inputs(args.inputs, args.case, args.split))
    if not plan:
        parser.error("No input cases for this split")
    args.output.mkdir(parents=True, exist_ok=False, mode=0o700)
    write_json(
        args.output / "plan.json",
        {"split": args.split, "cases": [row["case_id"] for row, _, _ in plan]},
    )
    summary = []
    with httpx.Client(
        base_url=args.api, timeout=60, trust_env=False, follow_redirects=False
    ) as client:
        for row, pdf, source in plan:
            case_id = row["case_id"]
            folder = args.output / case_id
            folder.mkdir()
            try:
                receipt = run_case(client, row, pdf, source, folder, args.timeout)
            except (httpx.HTTPError, ValueError, KeyError) as error:
                receipt = {"case_id": case_id, "status": "ERROR", "error": str(error)}
            write_json(folder / "receipt.json", receipt)
            summary.append(receipt)
            print(
                case_id,
                receipt["status"],
                receipt.get("run_id", receipt.get("error", "")),
                flush=True,
            )
    write_json(args.output / "runs.json", summary)
    if any(row["status"] != "COMPLETED" for row in summary):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
