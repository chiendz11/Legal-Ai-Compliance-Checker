"""Download/check the pinned DEV_VALIDATION dataset. Run from the repository root."""

import argparse
import json
import os
from pathlib import Path

from devtools.dataset_download import DatasetError, check_dataset, pull_dataset, read_manifest
from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("pull", "check"))
    parser.add_argument(
        "--manifest", type=Path, default=PROJECT_ROOT / "configs/dataset_dev_validation.json"
    )
    parser.add_argument("--destination", type=Path)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--url")
    source.add_argument("--archive", type=Path, help="Use a ZIP already downloaded in your browser")
    args = parser.parse_args()
    try:
        manifest = read_manifest(args.manifest)
        config = dotenv_values(PROJECT_ROOT / ".env")
        destination = args.destination or PROJECT_ROOT / manifest["destination"]
        if not destination.is_absolute():
            destination = PROJECT_ROOT / destination
        # Preserve a configured local location when its workbook name matches this release.
        configured = os.getenv("SEED_WORKBOOK_PATH") or config.get("SEED_WORKBOOK_PATH")
        if args.destination is None and configured:
            workbook = Path(configured)
            if workbook.name != manifest["workbook"]:
                raise DatasetError("SEED_WORKBOOK_PATH points to a different dataset workbook")
            destination = (PROJECT_ROOT / workbook).parent
        url = args.url or os.getenv("DATASET_ARCHIVE_URL") or config.get("DATASET_ARCHIVE_URL")
        if args.command == "check":
            result = {"status": "verified", **check_dataset(manifest, destination)}
        else:
            result = pull_dataset(manifest, destination, url=url, archive_path=args.archive)
    except (DatasetError, OSError, KeyError, ValueError) as error:
        parser.exit(1, f"Dataset error: {error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
