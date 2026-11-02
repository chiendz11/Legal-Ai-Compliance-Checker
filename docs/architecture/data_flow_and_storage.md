# Đọc PDF từ URL và cache local cho nhóm A

`shared/storage/source.py` giữ interface `SourceStorage.read(source) -> bytes`.
Implementation là `CachedHttpSourceStorage` trong `shared/storage/http.py`.
Nhóm A gọi `read()` để lấy nguyên bytes PDF rồi đưa vào parser/OCR của mình.
Storage không trích profile, chunk, citation hoặc đọc đáp án QA.

## Luồng đọc

```text
C01.source: tep_id + object_uri/url_nguon + mime_type + sha256
    ↓
Đọc cache theo SHA-256 → kiểm tra lại hash và PDF header
    ├── Hợp lệ: trả bytes, không gọi mạng
    └── Chưa có/hỏng: tải HTTP(S) → kiểm tra kích thước, hash và PDF header
                                      ↓
                              Ghi cache nguyên tử → trả bytes
                                      ↓
                          Parser/OCR do nhóm A triển khai
```

Ưu tiên `object_uri` nếu là URL HTTP(S), sau đó mới xét `url_nguon`.
Trong dataset hiện tại, `object_uri` là URL PDF Supabase public; `url_nguon` có thể
là trang xuất bản mẫu hợp đồng cũ. Nếu tải từ URL đã chọn thất bại/hash sai, storage
báo lỗi; không tự chuyển sang trang nguồn khác có thể chứa tài liệu khác.
Nếu `object_uri` là URI chưa hỗ trợ như `s3://...`, storage xét `url_nguon` HTTP(S).

PDF được kiểm tra dấu hiệu `%PDF-` trong 1.024 bytes đầu. Đây là kiểm tra header,
không chứng minh toàn bộ cấu trúc PDF đọc được; parser/OCR vẫn phải xử lý PDF lỗi,
mã hóa hoặc trang scan. Với MIME khác PDF, storage vẫn kiểm tra kích thước và hash,
không thực hiện kiểm tra header PDF.

## Cấu hình local

Các giá trị sau có mặc định; không cần sửa `.env` nếu dùng mặc định:

```dotenv
SOURCE_CACHE_DIR=data/private/source_cache
SOURCE_DOWNLOAD_TIMEOUT_SECONDS=30
SOURCE_MAX_BYTES=104857600
```

- Đường dẫn tương đối trong `Settings.from_env()` tính từ root repo, dù chạy Python ở folder khác.
- Cache được tạo khi lưu lần đầu, nằm trong `data/private/` đã được Git bỏ qua.
- Giới hạn mặc định là 100 MiB cho mỗi file, áp dụng cả khi server không gửi `Content-Length`.
- Timeout áp dụng cho mỗi thao tác mạng chờ kết nối/đọc, không phải tổng thời gian tải file.
- URL public hiện tại không cần API key Supabase. Client này chưa hỗ trợ bucket private/auth headers.
- Constructor không tải file hoặc tạo thư mục; chỉ `read()` mới thực hiện I/O.

Các URL truyền vào phải là nguồn đã được intake/dataset tin cậy. Client local hỗ trợ
HTTP(S), không mở `file://` hoặc đường dẫn máy. Nếu sau này mở endpoint công khai
cho phép người dùng nhập URL tùy ý, intake cần kiểm soát đích truy cập trước khi gọi storage.

## Ví dụ chạy độc lập: lấy một PDF từ DB đã seed

Chạy đoạn Python dưới đây trong môi trường ảo đã cài backend, sau khi seed DB.
Query chỉ lấy **tệp chính được `hop_dong.tep_nguon_id` chỉ định**; không lấy text
sidecar làm PDF input. Chỉ SELECT, không sửa DB hoặc output tham chiếu.

```python
from legal_checker.core.config import Settings
from legal_checker.core.postgres import connect_postgres
from legal_checker.shared.contracts.assessment import SourceDocument
from legal_checker.shared.storage.http import CachedHttpSourceStorage

settings = Settings.from_env()
with connect_postgres(settings.database_url) as connection:
    row = connection.execute(
        """
        SELECT t.tep_id, t.object_uri, t.url_nguon, t.mime_type, t.sha256
        FROM runtime.ca_danh_gia ca
        JOIN runtime.hop_dong h ON h.hop_dong_id = ca.hop_dong_id
        JOIN runtime.tep_nguon t
          ON t.tep_id = h.tep_nguon_id AND t.hop_dong_id = h.hop_dong_id
        WHERE ca.ca_id = %(case_id)s
        """,
        {"case_id": "CA360_001"},
    ).fetchone()

if row is None:
    raise LookupError("Không tìm thấy ca hoặc tệp chính; kiểm tra DB/seed")

source = SourceDocument.model_validate(row)
storage = CachedHttpSourceStorage(
    settings.source_cache_dir,
    timeout_seconds=settings.source_download_timeout_seconds,
    max_bytes=settings.source_max_bytes,
)
pdf_bytes = storage.read(source)
print(f"Đã đọc {len(pdf_bytes)} bytes, hash đã khớp C01")

# Lần sau đọc lại sẽ dùng cache đã kiểm tra hash.
assert storage.read(source) == pdf_bytes
```

Đóng transaction đọc metadata trước khi tải PDF; không giữ kết nối DB trong lúc chờ mạng.
Nếu chỉ cần đọc PDF, không cần gọi `build_services()` hoặc tải knowledge.

## Nối vào service của nhóm A

`build_services(settings)` khởi tạo sẵn `Services.source_storage`. Trong composition,
truyền dependency này vào implementation Document Intelligence do nhóm A viết.
Module phụ thuộc `SourceStorage`, không import `api.dependencies` để tự lấy dependency.

```python
from legal_checker.modules.documents.parser import DocumentReader, DocumentText
from legal_checker.shared.contracts.assessment import SourceDocument
from legal_checker.shared.storage.source import SourceStorage


class DocumentParsingService:
    def __init__(self, storage: SourceStorage, reader: DocumentReader):
        self.storage = storage
        self.reader = reader

    def parse(self, source: SourceDocument) -> DocumentText:
        pdf_bytes = self.storage.read(source)
        return self.reader.extract(pdf_bytes, source.mime_type)
```

Đây là ví dụ nối storage → reader. Nhóm A vẫn cần triển khai reader, OCR, chunking,
profile/citation extraction, mapper và repository để trả `DocumentIntelligenceResult`.
Storage không tự được gắn vào workflow skeleton chưa có implementation nhóm A.

## Lỗi và quản lý cache

| Lỗi | Cách xử lý ở module/caller |
|---|---|
| `SourceDownloadError` | Kiểm tra URL, quyền public, mạng, timeout; nếu cần retry thì caller quyết định |
| `SourceIntegrityError` | Dừng xử lý: bytes tải về khác hash C01; kiểm tra đúng file/phiên bản, không sửa hash để bỏ qua lỗi |
| `SourceFormatError` | MIME khai báo PDF nhưng bytes không có header PDF; kiểm tra link có trả HTML/trang đăng nhập không |
| `SourceTooLargeError` | Kiểm tra kích thước hoặc tăng giới hạn có chủ đích |
| `SourceCacheError` | Kiểm tra quyền ghi và dung lượng thư mục cache |

Tất cả kế thừa `SourceStorageError`. C01 sai schema phát sinh Pydantic `ValidationError`.
Storage không tự retry hoặc thay PDF bằng text sidecar/đáp án QA. Bytes tải sai hoặc dở
không được trả cho parser và không được lưu thành cache hợp lệ. Nếu cache hỏng, xóa entry
hỏng rồi tải lại; nếu mạng cũng lỗi thì dừng. Lỗi ghi cache cũng được báo rõ.

Tên file cache là SHA-256, không có đuôi `.pdf`; parser nhận bytes nên không cần đuôi.
Cùng hash dùng cùng một entry. Mỗi lần đọc đều kiểm tra hash; nhiều lượt tải đồng thời
ghi qua file tạm riêng rồi thay entry nguyên tử, không để parser đọc file đang ghi dở.
Cache không lưu URL, key hoặc đáp án; bản thân bytes PDF là dữ liệu local của người dev.

Có thể xóa folder `data/private/source_cache/` khi cần giải phóng dung lượng, sau khi dừng
các lượt đọc đang chạy. Lần đọc tiếp theo tải lại. Hiện chưa có tự động dọn cache/LRU.
Tài liệu mới có hash mới sẽ tạo entry khác; storage không cập nhật metadata hoặc seed DB.

## Kiểm tra phần dùng chung

```bash
pytest -q -c backend/pyproject.toml backend/tests/integration/test_source_storage_http.py
```

Các kiểm tra HTTP/cache dùng server local, không cần Supabase. Test khởi tạo dependency
factory cần `TEST_DATABASE_URL` như [hướng dẫn tests](../backend/tests/README.md).
Kiểm thử chất lượng parser/OCR là phần riêng của nhóm A.
