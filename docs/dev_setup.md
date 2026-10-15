# Tạo môi trường ảo và bắt đầu phát triển

Chạy lệnh từ **thư mục gốc repo**, nơi có `backend/`, `scripts/`, `README.md` và `.env.example`. Mỗi thành viên tạo `.venv` và DB riêng trên máy mình; dùng cùng manifest dataset để giữ baseline thống nhất.

## 1. Chuẩn bị Python

Project yêu cầu **Python 3.11 trở lên**; CI dùng **Python 3.12**. Có thể dùng Python 3.12 để cùng phiên bản với CI. PostgreSQL được chạy bằng Docker Compose hoặc launcher native trên Linux/macOS, xem bước 5.

Linux/macOS:

```bash
python3 --version
```

Windows PowerShell:

```powershell
py --version
```

Nếu máy có nhiều phiên bản, chọn interpreter phù hợp khi tạo môi trường: ví dụ `python3.12 -m venv .venv` hoặc `py -3.12 -m venv .venv` khi đã cài Python 3.12.

## 2. Tạo và kích hoạt môi trường ảo

Chỉ tạo một lần khi chưa có `.venv`. Mỗi lần mở terminal mới, kích hoạt lại môi trường đó.

**Linux/macOS — Bash/Zsh:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows — PowerShell:**

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Windows — Command Prompt:**

```bat
py -m venv .venv
.venv\Scripts\activate.bat
```

Sau khi activate, kiểm tra interpreter đang dùng:

```bash
python -c "import sys; print(sys.executable); print(sys.version)"
python -m pip --version
```

Đường dẫn phải nằm trong `.venv` của repo. `.venv` chứa interpreter và thư viện Python riêng; file `.env` ở bước 4 chứa cấu hình ứng dụng. Hai thứ có mục đích khác nhau.

Nếu PowerShell chặn `Activate.ps1`, có thể chạy qua interpreter đầy đủ mà không đổi execution policy:

```powershell
.\.venv\Scripts\python.exe -m pip install -e './backend[dev,dataset]' -c constraints.txt
```

Với cách này, các lệnh `python -m ...` bên dưới cũng dùng `.\.venv\Scripts\python.exe -m ...`. Linux/macOS có thể dùng `.venv/bin/python` tương tự khi chưa activate.

## 3. Cài dependencies

Trong terminal đã activate, tại root repo:

```bash
python -m pip install -e './backend[dev,dataset]' -c constraints.txt
```

- `-e`: cài package từ source hiện tại, giúp sửa code trong `backend/src/` mà không cài lại sau mỗi lần chỉnh file Python.
- `dev`: pytest, Ruff, HTTP test client và thư viện đọc Excel.
- `dataset`: downloader Google Drive dùng bởi `scripts.dataset`.
- `constraints.txt`: khóa phiên bản thư viện đã chọn cho repo.

Kiểm tra package đã import được:

```bash
python -c "import legal_checker, devtools; print('Backend imports OK')"
```

Khi `pyproject.toml` hoặc constraints thay đổi, chạy lại lệnh cài dependencies. Không cần xóa `.venv` sau mỗi lần sửa code.

## 4. Tạo cấu hình và tải dataset

Copy `.env.example` khi chưa có `.env`. Nếu đã có, giữ cấu hình cá nhân và đối chiếu `DATABASE_URL`, `SEED_WORKBOOK_PATH` với bản hiện tại.

Linux/macOS:

```bash
if [ ! -f .env ]; then
    cp .env.example .env
fi
```

Windows PowerShell:

```powershell
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
}
```

Tải gói DEV_VALIDATION và kiểm tra checksum:

```bash
python -m scripts.dataset pull
python -m scripts.dataset check
```

Script tạo `data/private/v750_source_pdf360_r2_supabase/`. Dataset hiện tại có 240 DEV + 60 VALIDATION; workbook đầy đủ được dùng để seed, các workbook chia nhỏ chỉ dùng để xem. `.env`, `.venv` và `data/private/` đều được Git bỏ qua.

Drive private/hết quota hoặc đã tải ZIP bằng trình duyệt: xem [hướng dẫn dataset](dataset_download.md).

## 5. Bật PostgreSQL và seed DB local

**Cách A — Docker Compose:**

```bash
docker compose up -d --wait postgres
```

**Cách B — launcher native trên Linux/macOS, khi không dùng Docker:**

```bash
python -m pip install -e './backend[local-server]' -c constraints.txt
python -m scripts.local_postgres start
python -m scripts.local_postgres status
```

Chọn một cách. Khi dùng PostgreSQL có sẵn, cấu hình `DATABASE_URL` cho instance đó. Sau khi DB server sẵn sàng:

```bash
python -m scripts.local_db init
python -m scripts.local_db preview
python -m scripts.local_db seed
python -m scripts.local_db check
```

`init` dùng Alembic để cập nhật schema. `preview` chỉ đọc/validate workbook; `seed` đảm bảo schema đã tới head, rồi nạp dữ liệu trong transaction riêng. Nếu seed lỗi, dữ liệu nhập bị rollback, schema đã cập nhật vẫn giữ. Đọc thêm [DB local và seed](local_database.md) và [cách tạo/chạy Alembic revisions](database_migrations.md).

## 6. Chạy API và bắt đầu module

```bash
python -m uvicorn legal_checker.main:create_app --factory --host 127.0.0.1 --port 8000
```

Mở Swagger tại `http://127.0.0.1:8000/docs`, health tại `http://127.0.0.1:8000/health`. API cần DB đã migrate/seed để khởi tạo Knowledge reader.

Khi bắt đầu module, tự viết query và mapper để dựng input đúng contract từ dữ liệu DB.
Chọn case/run và JOIN theo [hướng dẫn triển khai sau seed](huong_dan_trien_khai_module_sau_seed.md).

Bước 5–7 hiện là skeleton nội bộ; không có POST riêng cho reasoning/aggregation/risks/recommendations/pipeline. GET knowledge và run đã lưu vẫn dùng được. API khởi chạy assessment toàn bộ và implementation các module cần được bổ sung theo thiết kế. Người phụ trách dùng tests của module khi có implementation thật.

## 7. Kiểm tra code

```bash
python -m ruff check --config backend/pyproject.toml .
python -m ruff format --check --config backend/pyproject.toml .
python -m pytest -q -c backend/pyproject.toml
```

Không có `TEST_DATABASE_URL` thì tests cần PostgreSQL bị skip. Để chạy cả DB tests, dùng database tên bắt đầu bằng `legal_checker_test` và user có quyền CREATEDB.

Linux/macOS:

```bash
export TEST_DATABASE_URL='postgresql://legal_checker:legal_checker_local_only@127.0.0.1:5433/legal_checker_test'
python -m pytest -q -c backend/pyproject.toml
```

Windows PowerShell:

```powershell
$env:TEST_DATABASE_URL = 'postgresql://legal_checker:legal_checker_local_only@127.0.0.1:5433/legal_checker_test'
python -m pytest -q -c backend/pyproject.toml
```

Điều chỉnh user/password/port theo PostgreSQL của máy mình. Tests tạo/xóa DB con riêng; không trỏ biến này vào DB dev. Chạy xong có thể bỏ biến bằng `unset TEST_DATABASE_URL` (Bash/Zsh) hoặc `Remove-Item Env:TEST_DATABASE_URL` (PowerShell).

## 8. Làm việc những ngày sau

Không cần tải/seed lại mỗi lần mở terminal. Từ root repo:

```bash
source .venv/bin/activate
python -m scripts.local_postgres status
python -m uvicorn legal_checker.main:create_app --factory --host 127.0.0.1 --port 8000
```

`local_postgres status` dành cho người đã chọn launcher native. Người dùng Docker kiểm tra server bằng `docker compose ps`; bật lại cách chạy DB đã chọn nếu server đang tắt. Windows activate bằng lệnh ở bước 2.

Trong VS Code, chọn **Python: Select Interpreter** rồi trỏ tới `.venv/bin/python` (Linux/macOS) hoặc `.venv\Scripts\python.exe` (Windows), để editor và terminal dùng cùng bộ thư viện.

Dừng API bằng `Ctrl+C`. Thoát môi trường ảo:

```bash
deactivate
```

Khi pull code có revision schema mới, cài lại dependencies nếu thay đổi rồi chạy `python -m scripts.local_db init`. Không cần seed lại workbook để áp dụng migration mới.

## Lỗi thường gặp

| Lỗi | Cách xử lý |
|---|---|
| Python thấp hơn 3.11 | Chọn interpreter phù hợp, rồi tạo `.venv` bằng interpreter đó |
| `No module named legal_checker` hoặc `devtools` | Kiểm tra `sys.executable`, activate đúng `.venv`, cài editable từ root repo |
| `No module named gdown` khi tải dataset | Cài extra `[dev,dataset]` theo bước 3 |
| `No module named scripts` | Chạy lệnh từ root repo |
| DB connection refused | Bật PostgreSQL và đối chiếu `DATABASE_URL`/port |
| Workbook thiếu hoặc sai checksum | Chạy `scripts.dataset check`, xem [hướng dẫn dataset](dataset_download.md) |
| Gọi POST chạy riêng bước 5–7 bị 404 | Các routes nội bộ này đã xóa; module gọi qua hàm Python, API chạy assessment toàn bộ chưa triển khai |

Các script và trạng thái của chúng: [scripts/README](../scripts/README.md). Khi bắt đầu module, đọc [hướng dẫn JOIN và bàn giao theo nhóm](huong_dan_trien_khai_module_sau_seed.md).
