"""Nạp PDF local vào cache của CachedHttpSourceStorage để đọc nguồn không cần mạng.

CachedHttpSourceStorage lưu cache theo tên file = SHA-256 và kiểm tra lại hash mỗi lần đọc.
Khi URL trong ``tep_nguon.object_uri`` không truy cập được, chép PDF gốc (từ ZIP dataset
trên Drive) vào cache là đủ; code module không phải đổi.

    python -m scripts.seed_source_cache data/private/pdf
"""

import argparse
import hashlib
import shutil
from pathlib import Path

from legal_checker.core.config import Settings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf_dir", type=Path, help="Thư mục chứa các PDF gốc")
    args = parser.parse_args()

    cache_dir = Settings.from_env().source_cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)
    copied = skipped = 0
    for path in sorted(args.pdf_dir.glob("*.pdf")):
        target = cache_dir / hashlib.sha256(path.read_bytes()).hexdigest()
        if target.exists():
            skipped += 1
            continue
        shutil.copyfile(path, target)
        copied += 1
    print(f"Cache: {cache_dir}\nĐã chép {copied} PDF, bỏ qua {skipped} PDF đã có.")


if __name__ == "__main__":
    main()
