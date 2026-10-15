# v7.5.0 — 360 PDF, workbook r2 với cấu trúc Điều/Khoản và citation occurrences

> Dataset hiện tại dùng bản **supabase-public-v1**. Code bước 5–7 chỉ còn skeleton nội bộ, các HTTP POST riêng đã xóa; runner/eval CLI chưa triển khai. Công cụ dựng/rebuild dataset cũ đã xóa. Các PDF/workbook/reference của release được giữ để dev và eval. [Trạng thái backend](architecture.md#trạng-thái-skeleton-bước-57).

Phiên bản dataset: **v7.5.0-source-pdf360-r2-structured**.
PDF đầu vào là nguyên bytes của bộ 360 PDF v2. Bản r1 và workbook gốc được giữ để so sánh.
R2 là bộ tham chiếu chuẩn bị cho dev song song; production DI/Retrieval vẫn do nhóm A/B
triển khai. Script dựng dataset không thay implementation thật của các nhóm.

## Những gì được dựng lại

- Chunks ưu tiên Điều/Khoản/Điểm, trường giao dịch và đoạn văn; một nội dung có thể qua trang.
- Khoản ngắn giữ nguyên; đơn vị dài được chia theo câu/nhóm câu, hoặc hàng bảng.
  Tokenizer `cl100k_base`, target 500, giới hạn 900 token cho text chunk. Đây là cấu hình
  tham chiếu; không phải tuyên bố tokenizer/giới hạn thích hợp cho mọi embedding model.
- `section_path` chứa đường dẫn nghiệp vụ thay vì chỉ số trang. Không thêm tiêu đề giả vào
  `noi_dung`; prefix tìm kiếm lưu riêng trong metadata.
- Quan hệ section/unit/chunk, source offsets, ngữ cảnh cha/con, bảng ứng viên và dẫn chiếu
  nội bộ nằm trong QA artifact `DocumentStructure`.
- BBox text blocks và bảng có đường kẻ được đọc từ PDF thực. Bảng không có đường kẻ có
  candidate dựa vào căn cột text; quan hệ ô/tiêu đề vẫn cần review, không gọi là table gold.
- C03 giữ từng occurrence, kể cả số hiệu lặp; đọc số hiệu xuống dòng và tên luật không có
  số hiệu theo danh mục/aliases được hỗ trợ. Câu nguồn có thể ánh xạ nhiều evidence spans.
- Mốc ngày, chủ thể, facts, profile/evidence, C04/C05, C06 và outputs C07–C13 draft được
  dựng lại để không giữ liên kết đến IDs/text/offsets của r1.
- C02 có facts `profile.<field>` cùng evidence để đáp ứng handoff validator. Facts này là
  alias/classification của selected profile, không phải dữ kiện pháp lý được xác minh mới.
- C09 vẫn UNKNOWN khi chưa xác minh độc lập identity/version/domain. Các occurrences có
  thể tạo nhiều verification risks; số occurrence khác số văn bản pháp luật được nhắc tới.
- Embeddings, LLM logs, chứng từ thu tiền và human review không được giả lập thành đã chạy.

Giữ nguyên **50 bảng nghiệp vụ và 6 bảng QA, tên/cột không đổi**. Không cần migration schema
mới. Dùng QA multipart cho metadata/payload dài; native report vẫn là projection gọn.
Core knowledge/rules và cờ phê duyệt giữ nguyên. Deployment/URI/run/version của dataset đổi.

## Chọn gói và seed

| Gói | Ai dùng? | Nội dung |
|---|---|---|
| MASTER | Evaluator/người quản lý | 360 ca, outputs và metadata tham chiếu, 32 regression |
| DEV_VALIDATION | Nhóm phát triển | 240 DEV + 60 VALIDATION, upstream/expected tham chiếu, regression |
| TEST_INPUTS | Chạy blind E2E | 60 PDF + intake/C01; không text/chunks/profile/QA expected/structure |

Giữ split/source family của r1. Không đưa bốn biến thể cùng nguồn vào các split khác nhau.
TEST labels/DocumentStructure ở MASTER chỉ evaluator dùng, không đưa vào prompt/dev tuning.

Nhóm dev dùng [script tải dataset](dataset_download.md); manifest `configs/dataset_dev_validation.json` pin phiên bản, storage revision và SHA-256. Các workbook chia nhỏ chỉ dùng để xem; seed bằng workbook đầy đủ DEV_VALIDATION.

```bash
pip install -e './backend[dev,dataset]' -c constraints.txt
# Chỉ copy khi chưa có .env; nếu đã có, cập nhật DATABASE_URL/SEED_WORKBOOK_PATH.
cp .env.example .env
python -m scripts.dataset pull
python -m scripts.dataset check
# Bật PostgreSQL theo hướng dẫn local_database.md, rồi:
python -m scripts.local_db init
python -m scripts.local_db seed
```

Folder local: `data/private/v750_source_pdf360_r2_supabase/`; workbook:
`bang_du_lieu_runtime_v7_5_0_360_STRUCTURED_R2_SUPABASE_DEV_VALIDATION.xlsx`.
DB mặc định trong `.env.example`: `legal_checker_dev_v750_r2_supabase`.

PDF trong `runtime.tep_nguon.object_uri` dùng public URL Supabase, ví dụ
[HD360_001.pdf](https://agqjzspmvtrvyoftoabz.supabase.co/storage/v1/object/public/Hop_dong_raw/raw/HD360_001.pdf).
Text/controlled references vẫn dùng `dataset://v750-source-pdf360-r2-structured/sources/...` và ánh xạ sang `sources/` của gói local. Downloader cài 335 files: workbook, 300 text references, 32 controlled sources, README và CSV URL. Nhóm A tải PDF bằng URL, kiểm tra SHA-256 theo source metadata.

Seeder chặn workbook khác checksum trên DB đã seed. Khi đổi dataset, dùng DB mới; không sửa seed metadata để bỏ qua kiểm tra. Không đưa MASTER/TEST answers vào môi trường tuning của nhóm dev.

Chuẩn bị Knowledge snapshot một lần bằng `Knowledge(database_url)` và đối chiếu `.sha256`
với manifest trước khi dùng `Knowledge(database_url, snapshot_sha256=...)`. Seeder không
tự capture mọi knowledge snapshot. Đừng đổi pin để ép một catalog khác chạy được.

## Query/map cho các nhóm

Các JOIN nghiệp vụ vẫn theo
[hướng dẫn module sau seed](huong_dan_trien_khai_module_sau_seed.md).
Chọn run tham chiếu thực tế bằng query; r2 dùng dạng `CA360_001_PDF360_LS2_REFERENCE`.
Không dùng IDs `_P001_...`/run r1 để đọc chunks/finding của r2.

```sql
SELECT m.case_id, m.split, ca.hop_dong_id,
       ARRAY(SELECT DISTINCT k.lan_chay_id FROM runtime.ket_qua_tieu_chi k
             WHERE k.ca_id=ca.ca_id ORDER BY k.lan_chay_id) AS reference_runs
FROM qa.case_manifest m JOIN runtime.ca_danh_gia ca ON ca.ca_id=m.case_id
WHERE m.case_kind='CORPUS' AND m.split IN ('DEV','VALIDATION')
ORDER BY m.case_id;
```

Đọc `DocumentStructure` từ QA như các artifacts khác:

```python
from devtools.qa_validation import join_artifacts
from legal_checker.core.postgres import connect_postgres

with connect_postgres(database_url) as connection:
    parts = connection.execute(
        "SELECT * FROM qa.artifacts WHERE case_id=%s AND role='EXPECTED' "
        "AND contract_name='DocumentStructure'",
        (case_id,),
    ).fetchall()
payloads = join_artifacts(parts)  # Kiểm tra đủ parts và hash.
if len(payloads) != 1:
    raise ValueError("Missing/ambiguous source structure")
structure = next(iter(payloads.values()))
```

Các mục chính:

| Metadata | Cách dùng |
|---|---|
| `parents` | Section/unit có `children`, parent IDs, path và source range |
| `chunks` | `doan_id` → unit/section, raw source range, token count, search prefix |
| `tables` | Text-alignment candidates/rows; status nói rõ chưa xác minh cấu trúc ô |
| `pdf_layout` | BBox blocks, ruled tables, lỗi/unmapped blocks, trang ít text cần OCR/review |
| `internal_references` | Raw dẫn chiếu, target candidates, RESOLVED/AMBIGUOUS/UNRESOLVED |
| `citation_occurrences` | Mỗi occurrence với câu nguồn, số/tên/Điều/Khoản literal và evidence spans |

Source offsets trong metadata là Unicode offsets vào canonical text sidecar. Evidence
trong bảng nghiệp vụ vẫn dùng offsets **tương đối trong `doan_hop_dong.noi_dung`**.
Canonical text nối trang bằng `\n\u2028\n` (Unicode LINE SEPARATOR, hợp lệ trong Excel); chỉ bỏ dòng watermark synthetic khỏi text reference,
không sửa PDF. Coverage 100% là non-whitespace của text layer canonical, không phải OCR gold.

- **Nhóm A:** input là bytes PDF/C01. C02/C03/chunks/DocumentStructure chỉ để đối chiếu
  hoặc hiểu output mong muốn. Chấm literal fields, spans, structure boundaries riêng;
  classifier profile và layout heuristic chưa phải gold độc lập.
- **Nhóm B:** có thể dùng C02/C05/chunks tham chiếu để dev. Index raw chunks kèm path
  trong search text; retrieval mở sibling chunks của cùng unit và target dẫn chiếu đã
  resolve, với budget. Prefix/header metadata không trở thành quote nguồn.
- **Nhóm C:** C06 reference có candidates theo path/text và context links; selected evidence
  vẫn là source spans của predicates có giới hạn. Ngữ cảnh mở rộng chưa tự verified.
  Không dùng observations QA để chấm provider/LLM mới; chúng chỉ phục vụ replay.
- **Nhóm D:** hiển thị path/page range, occurrence citation, finding/risk provenance.
  Phân biệt số occurrences với số legal identities; đọc full C13 từ QA, report DRAFT.

Native `thong_tin_chuan_hoa_json` của C03 giữ normalized fields cùng provenance bổ sung.
Mapper chỉ chọn fields `CitationNormalization` nhận; không đưa cả JSONB có extra metadata
vào DTO strict. Full typed C03 trong QA đã có mapping đúng.

## Các nguyên tắc pháp lý khi dùng bộ này

1. Tên luật không có số/năm không đủ để chọn phiên bản; giữ ambiguous/UNKNOWN.
2. Khớp số hiệu catalog không chứng minh VALID, hiệu lực hay phù hợp domain.
3. Dẫn chiếu “Điều 2 của Hợp đồng” là liên kết nội bộ, không phải căn cứ pháp luật C03.
4. Điều trùng số trong nội quy/phụ lục được phân biệt theo document part; target không
   duy nhất giữ ambiguous, không chọn target đầu tiên.
5. Thân hợp đồng và phụ lục có giá/điều khoản khác nhau giữ cả hai nguồn; không tự xác lập
   thứ tự ưu tiên pháp lý. Source predicate override chỉ áp dụng khi có câu thay thế rõ
   trong kịch bản synthetic và vẫn giữ scope/temporal/gates.
6. Ngày bàn giao dự kiến không chứng minh đã bàn giao; ngày ký không thay ngày thu tiền.
7. Khoản trống/evidence rỗng không tự chứng minh MISSING. Coverage/absence và legal gates
   vẫn cần đủ điều kiện; không ép phân phối labels cho đẹp.

Knowledge và references của dataset giới hạn ở catalog/10 requirement families đã chọn; engine tạo references thuộc phiên bản dựng release trước đây. Chưa phải rà soát
pháp lý toàn diện, chưa có expert gold cho toàn bộ 360 PDF. Cờ human_verified không được
bật chỉ vì script/schema/tests pass. Nguồn bảo hành đã đối chiếu trước giữ nguyên:
[Luật Nhà ở 27/2023, Điều 129](https://datafiles.chinhphu.vn/cpp/files/vbpq/2024/01/luat27_tiep.pdf).

## Tái dựng và kiểm tra

Công cụ dựng lại release này đã được xóa khỏi code base. Dùng `python -m scripts.dataset pull` để lấy gói frozen DEV_VALIDATION, rồi `python -m scripts.local_db seed` để nạp DB. Các mô tả kiểm tra bên dưới ghi lại quá trình dựng release trước đây.

Builder trước đây dùng PyMuPDF/tiktoken, không gọi LLM. Các dependency đó đã bỏ khỏi extra dev sau khi xóa builder.
Validation gồm source hash, non-whitespace coverage, Unicode quotes/offsets, C02 handoff,
ownership/FKs, DTOs, independent guarded predicates/regression, workbook roundtrip và
TEST không chứa target artifacts. Các kiểm tra này không thay eval implementations thật.

Hướng tiếp cận cấu trúc/token budget tham khảo
[Docling Hybrid/Hierarchical Chunker](https://docling-project.github.io/docling/concepts/chunking/).
R2 dùng adapter riêng, không tuyên bố đã chạy Docling hoặc OCR toàn corpus.
