# Manifest dataset dùng chung

`dataset_dev_validation.json` pin release `v7.5.0-pdf360-v4r2-runtime-20261110`:
240 DEV + 60 VALIDATION, 32 regression trong QA, workbook đầy đủ và PDF v4 r2.
Snapshot knowledge `HUMAN_VERIFIED` theo quyết định chủ dự án. Runtime references
vẫn là SILVER; literal reference độc lập có phạm vi cụ thể.

Manifest ghi hash/kích thước ZIP và từng file, tên workbook, destination,
knowledge hash/version/review status và `bundled_sources_index`. Chỉ metadata
được commit; PDF/workbook/cache nằm trong `data/private/` ngoài Git.

```bash
python -m scripts.dataset pull --archive /path/to/legal_compliance_v750_PDF360_V4R2_20261110_DEV_VALIDATION.zip
python -m scripts.dataset check
python -m scripts.dataset cache-sources
```

`LOCAL_ARCHIVE_READY` nghĩa ZIP mới sẵn trên máy maintainer, chưa được khẳng định
đã xuất bản tại URL. Không thay checksum mới nhưng giữ URL trỏ gói cũ. Khi upload
đúng ZIP, cập nhật URL và publication status, giữ checksum theo bytes thực tế.
`cache-sources` kiểm PDF và điền cache theo hash, không thay DB.

Xem [hướng dẫn release và seed DB mới](../docs/guides/dataset_pdf360_v4r2_runtime_20261110.md).
