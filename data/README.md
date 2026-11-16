# Dữ liệu local ngoài Git

Repo giữ code, schema/migrations, tài liệu và manifest; workbook, PDF, DB/cache
và `.env` nằm ngoài Git. `data/private/` cũng được loại khỏi Docker build context.

Release hiện hành: `v7.5.0-pdf360-v4r2-runtime-20261110`, storage
`bundled-pdf-v4r2`, knowledge `HUMAN_VERIFIED` theo quyết định chủ dự án.
DEV_VALIDATION gồm 240 DEV + 60 VALIDATION và 32 ca regression trong QA.

```text
data/private/
├── postgres-local/                     # PostgreSQL native, giữ dữ liệu cũ
├── source_cache/<sha256>                # Cache PDF đã kiểm hash
└── v750_pdf360_v4r2_runtime_20261110/
    ├── bang_du_lieu_v7_5_0_PDF360_V4R2_20261110_DEV_VALIDATION.xlsx
    ├── SOURCE_FILES.json
    ├── KNOWLEDGE_ACCEPTANCE.json
    ├── QUALITY_SCOPE.json
    ├── LITERAL_ASSERTIONS.csv
    ├── README_SU_DUNG.md
    └── sources/
        ├── pdf/HD360_*.pdf              # Đúng PDF v4 r2 của workbook
        └── controlled/                 # Nguồn giả lập chỉ cho regression
```

```bash
python -m scripts.dataset pull --archive /path/to/legal_compliance_v750_PDF360_V4R2_20261110_DEV_VALIDATION.zip
python -m scripts.dataset check
python -m scripts.dataset cache-sources
python -m scripts.local_db init
python -m scripts.local_db seed
python -m scripts.local_db check
```

Đổi `.env` sang DB/folder mới trước khi seed. Không xóa DB cũ hoặc dùng lệnh
update reviewed-flags cho release thay PDF/chunks. `dataset pull` và
`cache-sources` chỉ tạo files, không ghi DB.

PDF dùng `dataset://` và cache theo hash; v4 r2 chưa được xuất bản Supabase.
Không lấy bytes v2 từ URL cũ thay cho PDF mới. API/worker cần cùng cache.
Workbook chia nhỏ chỉ để xem, seed nhận workbook đầy đủ trong manifest.

Xem [phạm vi reference/gold và hướng dẫn chi tiết](../docs/guides/dataset_pdf360_v4r2_runtime_20261110.md).
