# Cấu hình dùng chung của repo

`dataset_dev_validation.json` là manifest của dataset đã chốt:
**v7.5.0-source-pdf360-r2-structured / supabase-public-v1**,
gồm 240 DEV + 60 VALIDATION và 32 ca regression QA.

Manifest cung cấp:

- Link Drive, kích thước và SHA-256 của gói ZIP.
- Đường dẫn cài dataset local và tên workbook đầy đủ dùng để seed.
- SHA-256 của từng file bắt buộc để kiểm tra đúng phiên bản.
- Knowledge snapshot hash và URL gốc của PDF public trên Supabase.

Hai lệnh sau đọc manifest mặc định từ folder này:

```bash
python -m scripts.dataset pull
python -m scripts.dataset check
```

Manifest được commit cùng code; dataset tải về nằm trong `data/private/` ngoài Git.
Khi thay release dataset, cập nhật manifest theo gói thực tế và review các checksum.
Xem [hướng dẫn tải dataset](../docs/dataset_download.md).

Cấu hình riêng của mỗi máy như DB URL và cache PDF đặt trong `.env`, theo
`.env.example` và `legal_checker.core.config.Settings`. Mỗi module tự cấu hình
LLM/embeddings theo nhu cầu; không lưu API key hoặc thông tin đăng nhập trong `configs/`.
