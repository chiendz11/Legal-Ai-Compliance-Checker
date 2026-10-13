"""Build private master, dev/validation and blind-test-input workbooks from v7.5.0."""

import argparse
import json
from pathlib import Path

from devtools.database_seed import read_workbook
from devtools.workbook_optimization import (
    build_release,
    package_distribution,
    subset_release,
    write_release,
)
from legal_checker.core.config import Settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-audit", type=Path, required=True)
    parser.add_argument("--legal-checks", type=Path, required=True)
    parser.add_argument("--database-url", default=Settings.from_env().database_url)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "README_SU_DUNG.md").write_text(
        "# v7.5.0 dev/eval r1\n\n"
        "MASTER: evaluator/maintainer only, 90 SILVER corpus cases.\n"
        "DEV_VALIDATION: 60 DEV + 15 VALIDATION; TEST corpus and labels excluded.\n"
        "TEST_INPUTS: 15 cases; intake input only, target outputs excluded.\n\n"
        "Separate QA suite: 32 independent steps-5-7 specifications, "
        "8 synthetic PDF extraction specifications.\n"
        "Corpus outputs are current-engine guard references, not legal gold. "
        "Synthetic fixtures are not real transactions.\n"
        "Original PDFs where downloaded are not yet aligned/annotated as OCR gold. "
        "Other sources use derived text, whose bytes/hash are real.\n"
        "dataset://v750-r1/sources/... resolves to the sources folder in this archive.\n\n"
        "Seed into a fresh local DB using scripts.local_db. "
        "Read docs/v750_dev_eval.md in the repository for setup and evaluation.\n"
        "Do not give MASTER to developers tuning on DEV. "
        "Do not report reference replay/spec tests as OCR/LLM/legal accuracy.\n"
    )
    seed = read_workbook(args.input)
    release = build_release(
        seed,
        args.database_url,
        args.output_dir / "sources",
        json.loads(args.source_audit.read_text()),
        json.loads(args.legal_checks.read_text()),
    )
    files = {
        "MASTER": ("bang_du_lieu_runtime_v7_5_0_DEV_EVAL_MASTER.xlsx", release),
        "DEV_VALIDATION": (
            "bang_du_lieu_runtime_v7_5_0_DEV_VALIDATION.xlsx",
            subset_release(release, {"DEV", "VALIDATION"}, include_controls=True),
        ),
        "TEST_INPUTS": (
            "bang_du_lieu_runtime_v7_5_0_TEST_INPUTS.xlsx",
            subset_release(release, {"TEST"}, hide_expected=True),
        ),
    }
    for distribution, (filename, data) in files.items():
        target = args.output_dir / filename
        write_release(data, target, distribution)
        parsed = read_workbook(target)
        assert parsed.counts == data.counts and parsed.qa_counts == data.qa_counts
        print(distribution, "validated", parsed.counts["ca_danh_gia"], "cases", flush=True)
        print(
            "PACKAGE",
            package_distribution(args.output_dir, filename, data, distribution),
            flush=True,
        )
    (args.output_dir / "release_summary.json").write_text(
        json.dumps(
            {
                "source_sha256": seed.source_sha256,
                "runtime_counts": release.counts,
                "qa_counts": release.qa_counts,
                "quality": "SILVER_GUARD_REFERENCE + SYNTHETIC_SPEC; NOT LEGAL GOLD",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
