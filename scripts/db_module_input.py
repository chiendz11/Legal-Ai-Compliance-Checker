"""Inspect actual DB input rows for independent module development; no fixed fixtures."""

import argparse
import json

from legal_checker.core.config import Settings
from legal_checker.modules.retrieval.repository import RetrievalDatasetRepository


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--run", required=True)
    args = parser.parse_args()
    repo = RetrievalDatasetRepository(Settings.from_env().database_url)
    inputs = repo.load_input_rows(args.case)
    candidates = repo.load_seeded_evidence(args.case, args.run)
    print(
        json.dumps(
            {
                "input_rows": inputs,
                "evidence_candidates": candidates,
                "missing_criterion_ids": sum(r["tieu_chi_id"] is None for r in candidates),
                "notice": "RAW_DB_ROWS_REQUIRE_MAPPING_AND_VALIDATION",
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
