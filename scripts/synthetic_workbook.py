"""Export 90 declared synthetic scenarios as SQL-compatible dev/evaluation workbooks."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

from devtools.database_seed import read_workbook
from devtools.synthetic_scenarios import URI_PREFIX, VERSION
from devtools.synthetic_workbook import build_synthetic_release, distribution_rows
from devtools.workbook_optimization import (
    package_distribution,
    subset_release,
    write_release,
)
from legal_checker.core.config import Settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--split-from", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--legal-checks", type=Path, required=True)
    parser.add_argument(
        "--font-path",
        type=Path,
        default=Path("/usr/share/fonts/noto/NotoSans-Regular.ttf"),
    )
    parser.add_argument("--database-url", default=Settings.from_env().database_url)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    guide = Path(__file__).resolve().parents[1] / "docs/v750_synthetic_eval.md"
    (args.output_dir / "README_SU_DUNG.md").write_text(guide.read_text(), encoding="utf-8")
    seed, prior = read_workbook(args.input), read_workbook(args.split_from)
    split = {
        r["case_id"]: r["split"]
        for r in prior.qa_tables["case_manifest"]
        if r["case_kind"] == "CORPUS"
    }
    release = build_synthetic_release(
        seed,
        args.database_url,
        args.output_dir / "sources",
        args.font_path,
        split,
        json.loads(args.legal_checks.read_text()),
    )
    variants = {
        "MASTER": release,
        "DEV_VALIDATION": subset_release(release, {"DEV", "VALIDATION"}),
        "TEST_INPUTS": subset_release(release, {"TEST"}, hide_expected=True),
    }
    for tag, data in variants.items():
        filename = f"bang_du_lieu_runtime_v7_5_0_SYNTHETIC_{tag}.xlsx"
        path = args.output_dir / filename
        write_release(
            data,
            path,
            tag,
            version=VERSION,
            synthetic=True,
            coverage=distribution_rows(data) if tag != "TEST_INPUTS" else None,
        )
        parsed = read_workbook(path)
        if parsed.counts != data.counts or parsed.qa_counts != data.qa_counts:
            raise ValueError("Workbook round-trip count mismatch: " + tag)
        archive = package_distribution(
            args.output_dir,
            filename,
            data,
            tag,
            prefix=URI_PREFIX,
            archive_prefix="legal_compliance_v750_SYNTHETIC",
        )
        print(tag, len(data.tables["ca_danh_gia"]), "cases;", archive, flush=True)
    coverage = distribution_rows(release)
    with (args.output_dir / "PHAN_PHOI.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "split", "label", "count"])
        writer.writerows(coverage)
    with (args.output_dir / "CASE_MANIFEST.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(["case_id", "hop_dong_id", "split", "scenario", "group_id"])
        writer.writerows(
            [
                r["case_id"],
                r["hop_dong_id"],
                r["split"],
                r["limitations_json"]["scenario"],
                r["group_id"],
            ]
            for r in release.qa_tables["case_manifest"]
        )
    (args.output_dir / "release_summary.json").write_text(
        json.dumps(
            {
                "dataset_version": VERSION,
                "mode": "SYNTHETIC_EVALUATION",
                "source_sha256": seed.source_sha256,
                "runtime_counts": release.counts,
                "qa_counts": release.qa_counts,
                "distribution": coverage,
                "independent_scenario_assertions_passed": 90,
                "production_modules_1_4_evaluated": False,
                "real_world_legal_accuracy_measured": False,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    files = sorted(
        p for p in args.output_dir.iterdir() if p.is_file() and p.name != "SHA256SUMS.txt"
    )
    (args.output_dir / "SHA256SUMS.txt").write_text(
        "".join(hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n" for p in files),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
