"""Export reference C13 reports from the local DB as frontend mock fixtures. Run from repo root.

Fixtures are QA EXPECTED references for UI layout only, not output of a dev run.
They go to frontend/src/mocks/fixtures/ which Git ignores.
"""

import argparse
import json
import os
from collections import Counter
from pathlib import Path

from devtools.qa_validation import join_artifacts
from dotenv import load_dotenv
from legal_checker.core.postgres import connect_postgres
from legal_checker.shared.contracts.report import FinalReport

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "frontend/src/mocks/fixtures"


def load_reports(database_url: str, case_ids: list[str] | None) -> dict[str, dict]:
    query = """SELECT a.* FROM qa.artifacts a JOIN qa.case_manifest m USING (case_id)
               WHERE a.role = 'EXPECTED' AND a.contract_name = 'C13' AND m.split = 'DEV'"""
    params: tuple = ()
    if case_ids:
        query += " AND a.case_id = ANY(%s)"
        params = (case_ids,)
    with connect_postgres(database_url) as connection:
        rows = connection.execute(query, params).fetchall()
    reports = {}
    for payload in join_artifacts(rows).values():
        report = FinalReport.model_validate(payload).model_dump(mode="json")
        reports[report["ca_id"]] = report
    return reports


def diversity(report: dict) -> tuple[int, int]:
    content = report["report_json"]
    statuses = Counter(r["status"] for r in content["compliance"]["requirement_results"])
    findings = Counter(c["finding"] for c in content["compliance"]["criterion_results"])
    citations = Counter(f["status"] for f in content["citation_validation"]["findings"])
    risk_groups = sum(1 for risks in content["risks"].values() if risks)
    return len(statuses) + len(findings) + len(citations) + risk_groups, findings["VIOLATED"]


def report_record(report: dict) -> dict:
    """Shape of Output_ReportRecord in docs/openapi.design.json."""
    return {
        "run_id": report["report_json"]["audit"]["context"]["run_id"],
        "review_revision": "none",
        "report": report,
    }


def main() -> None:
    load_dotenv(ROOT / ".env", override=False)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--case", action="append", dest="cases", help="DEV case ID; repeatable")
    parser.add_argument("--limit", type=int, default=5, help="Cases picked when --case is absent")
    args = parser.parse_args()
    if not args.database_url:
        parser.error("Set DATABASE_URL in .env or pass --database-url")

    reports = load_reports(args.database_url, args.cases)
    if args.cases:
        missing = sorted(set(args.cases) - reports.keys())
        if missing:
            parser.error(f"No DEV C13 reference for: {', '.join(missing)}")
        selected = [reports[case_id] for case_id in args.cases]
    else:
        ranked = sorted(reports.values(), key=lambda r: (diversity(r), r["ca_id"]), reverse=True)
        selected = sorted(ranked[: args.limit], key=lambda r: r["ca_id"])

    args.output.mkdir(parents=True, exist_ok=True)
    for stale in args.output.glob("*.json"):
        stale.unlink()
    for report in selected:
        path = args.output / f"{report['ca_id']}.json"
        path.write_text(json.dumps(report_record(report), ensure_ascii=False), encoding="utf-8")
    print(
        json.dumps(
            {"output": str(args.output), "cases": [r["ca_id"] for r in selected]},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
