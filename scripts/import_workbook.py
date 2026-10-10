"""Import curated knowledge only; contract text, profiles and runtime fixtures stay local."""

import argparse
import hashlib
import json
from pathlib import Path

from openpyxl import load_workbook

TABLES = [
    "phien_ban_yeu_cau",
    "tieu_chi_danh_gia",
    "quy_tac_quyet_dinh",
    "quy_tac_tong_hop",
    "chinh_sach_bang_chung",
    "quy_tac_rui_ro",
    "danh_muc_rui_ro",
    "danh_muc_khuyen_nghi",
    "rui_ro_khuyen_nghi",
    "dieu_khoan_phap_ly",
    "van_ban_phap_ly",
    "ngoai_le_ap_dung",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/knowledge.json"))
    args = parser.parse_args()
    workbook = load_workbook(args.workbook, read_only=True, data_only=True)
    tables = {}
    for name in TABLES:
        rows = iter(workbook[name].values)
        headers = next(rows)
        tables[name] = [
            dict(zip(headers, row, strict=True))
            for row in rows
            if any(value is not None for value in row)
        ]
    snapshot = {
        "schema_version": "v7.3.2",
        "source_sha256": hashlib.sha256(args.workbook.read_bytes()).hexdigest(),
        "tables": tables,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(snapshot, ensure_ascii=False, default=str, indent=2) + "\n", encoding="utf-8"
    )
    workbook.close()
    print(
        json.dumps(
            {"output": str(args.output), "counts": {k: len(v) for k, v in tables.items()}},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
