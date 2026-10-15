# Dữ liệu trên máy local

Repo giữ code, schema/migrations, tài liệu và cấu hình mẫu. Dataset, DB local,
cache và thông tin kết nối thật nằm ngoài Git trong `data/private/` và `.env`.
`data/private/` cũng được loại khỏi Docker build context.

## Bộ dữ liệu đang dùng

- Dataset: `v7.5.0-source-pdf360-r2-structured`, storage revision `supabase-public-v1`.
- Dev: workbook đầy đủ DEV_VALIDATION, 240 DEV + 60 VALIDATION.
- MASTER và TEST_INPUTS giữ ở nơi phát hành ngoài repo; evaluator dùng đúng gói.
- SHA-256 workbook DEV_VALIDATION:
  `e1f15b658d6ef511efa784eb09896adcda67befadbc51ae7411a90c1a4b29e61`.
- Workbook chia nhỏ phục vụ xem/tra cứu; lệnh seed vẫn nhận workbook đầy đủ.

```text
data/
├── README.md                         # Tài liệu trong repo
└── private/                          # Được Git và Docker bỏ qua
    ├── postgres-local/               # PostgreSQL native và các DB local
    └── v750_source_pdf360_r2_supabase/
        ├── bang_du_lieu_runtime_v7_5_0_360_STRUCTURED_R2_SUPABASE_DEV_VALIDATION.xlsx
        ├── README_SU_DUNG.md
        ├── PDF_URLS_DEV_VALIDATION.csv
        └── sources/
            ├── text/                 # Text tham chiếu đúng 300 ca DEV/VALIDATION
            └── controlled/           # Nguồn cho regression cases
```

PDF chính được tải từ URL public trong `tep_nguon.object_uri`, kiểm tra SHA-256
rồi cache local. Các file PDF offline có thể lấy từ ZIP DEV_VALIDATION nếu cần.
Text references dùng `dataset://v750-source-pdf360-r2-structured/sources/text/` và
ánh xạ theo thư mục giải nén; chúng chưa được upload lên storage.

## Seed DB

Từ root repo, sau khi activate môi trường Python và chuẩn bị PostgreSQL:

```bash
python -m scripts.dataset pull
python -m scripts.dataset check
python -m scripts.local_db init
python -m scripts.local_db seed
python -m scripts.local_db check
```

Các lệnh đọc `DATABASE_URL` và `SEED_WORKBOOK_PATH` từ `.env`.
`dataset pull` dùng manifest `configs/dataset_dev_validation.json`, kiểm tra hash ZIP
và từng file, chỉ cài workbook/text/controlled/CSV/README. File PDF tải từ Supabase;
ZIP DEV_VALIDATION chứa bản offline nếu cần. Lệnh tải giữ nguyên DB và dữ liệu local
đang có; workbook hoặc text khác hash sẽ báo lỗi thay vì ghi đè.
Mỗi người dùng DB local riêng. Với workbook khác hash, dùng DB mới theo kiểm tra
của seeder; giữ nguyên DB đã seed nếu vẫn cần baseline cũ.
PostgreSQL native dùng `postgres-local/`; Docker Compose dùng named volume riêng.
