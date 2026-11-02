# Hướng dẫn Triển khai Nhóm A (Bước 1–2: Document Intelligence)

> **Người phụ trách**: Người 2 · **Input**: PDF/DOCX file · **Output**: C01, C02 (ContractProfile), C03 (ExtractedCitations)

Tài liệu chung: [Tổng quan module & Quy tắc JOIN](README.md)

---

## 4. Nhóm A: bước 1–2: tiếp nhận và Document Intelligence

### 4.1 Mục tiêu và phần nhận/trả

**Bước 1:** nhận PDF/DOCX, lưu nguồn và tạo ca đánh giá có deployment pin.
**Bước 2:** đọc tệp, trích xuất profile/chủ thể/mốc thời gian, chunks và viện dẫn.

| Contract | Model hiện có | Ý nghĩa |
|---|---|---|
| C01 | `AssessmentCase`, `SourceDocument`, `DeploymentPin` | Ca + nguồn + các phiên bản đã chọn |
| C02 | `ContractProfile`, `DocumentIntelligenceResult` | Hồ sơ và facts/evidence; result còn chứa chunks/C03 |
| Chunks | `Chunk` | Text nguyên bản theo đoạn, ID hợp đồng và số trang |
| C03 | `CitationExtraction` | Viện dẫn do hợp đồng tự nêu, raw text, chuẩn hóa sơ bộ và vị trí |

C03 chưa kết luận VALID/STALE/INVALID: đó là nhiệm vụ bước 3B.

### 4.2 Các bảng đọc và ghi

| Việc | Bảng |
|---|---|
| Đọc/lưu tệp và hợp đồng | `runtime.hop_dong`, `tep_nguon` |
| Tạo ca và pin | `runtime.ca_danh_gia`, đọc `knowledge.phien_ban_trien_khai` |
| Profile được chọn | `runtime.ho_so_hop_dong` |
| Chủ thể | `runtime.chu_the_hop_dong` |
| Chunks | `runtime.doan_hop_dong` |
| Giá trị trích xuất/raw/candidate | `runtime.trich_xuat_truong`, `bang_chung_truong` |
| Evidence profile | `runtime.bang_chung_ho_so` |
| Mốc thời gian | `runtime.moc_thoi_gian_hop_dong` |
| Viện dẫn và vị trí/quote | `runtime.vien_dan_phap_ly_hop_dong`, `bang_chung_vien_dan` |

DI chủ yếu dùng tệp gốc để extraction. Có thể đọc danh mục loại hợp đồng/cấu hình,
nhưng không dùng decision/risk rules để tự kết luận tuân thủ.

### 4.3 Làm lần lượt

1. **Intake:** kiểm tra định dạng/kích thước, đọc bytes và tính SHA256; lưu tệp vào storage
   local hoặc object storage; lưu `tep_nguon` và metadata `hop_dong`.
2. **Tạo C01:** sinh contract/case ID, ghi tenant/actor, ngày đánh giá và pin deployment.
   `SourceDocument` cần `object_uri` hoặc `url_nguon` truy cập được.
   `IntakeService.register(case)` hiện nhận C01 đã dựng; phần upload/tạo C01 ban đầu
   cần use case bổ sung ở API/service, không chỉ gọi Protocol rồi coi là đã upload.
3. **Parser:** trích text theo trang; PDF có text dùng parser, trang scan/không đọc được
   đi OCR. Ghi nhận chất lượng/những trang thiếu để bước sau biết giới hạn coverage.
4. **Chunker:** chia theo cấu trúc điều/khoản hoặc đoạn, giữ thứ tự, section/page và hash.
   Giữ nguyên text dùng làm evidence; nếu cần text sạch cho search, lưu nó riêng.
5. **Profile extractor:** chọn loại giao dịch, đối tượng, chủ thể, giá trị và mốc thời gian;
   giữ raw/candidate/evidence bên cạnh giá trị được chọn. Không suy ra ngày ký đầy đủ
   từ một trường trống hoặc chỉ có năm.
6. **Citation extractor:** nhận diện số hiệu/tên/loại văn bản và điều/khoản nếu có;
   ghi nguyên văn và vị trí. Citation mơ hồ giữ trạng thái AMBIGUOUS/UNKNOWN.
7. **Dựng DTO:** `ContractProfile` + `list[Chunk]` + `list[CitationExtraction]`, validate
   bằng `DocumentIntelligenceResult`, rồi validate liên kết bằng `validate_document`.
8. **Lưu kết quả:** commit profile/chunks/citations/extractions/evidence đồng bộ.
   `hop_dong.tep_nguon_id` và `tep_nguon.hop_dong_id` có vòng FK: dùng một transaction.
   Hướng xử lý re-extraction và phiên bản chunks xem mục 8.4.

Khi test bước 2 độc lập, C01/PDF là input; các bảng profile/chunks/citations seed là
output tham khảo. Implementation phải đọc PDF để tạo output mới.

### 4.4 Xem nguồn và output mẫu

```sql
SELECT t.tep_id, t.hop_dong_id, t.object_uri, t.url_nguon, t.mime_type, t.sha256
FROM runtime.tep_nguon t
JOIN runtime.ca_danh_gia ca ON ca.hop_dong_id = t.hop_dong_id
WHERE ca.ca_id = 'CA360_001';

SELECT d.doan_id, d.thu_tu, d.page_start, d.page_end, d.section_path, d.noi_dung
FROM runtime.doan_hop_dong d
JOIN runtime.ca_danh_gia ca ON ca.hop_dong_id = d.hop_dong_id
WHERE ca.ca_id = 'CA360_001'
ORDER BY d.thu_tu, d.doan_id;
```

Seed không tải PDF vào PostgreSQL. Bộ 360 có PDF đi kèm; ánh xạ URI `dataset://...`
về thư mục đã giải nén và kiểm tra SHA256 trước khi đọc. Text sidecar/profile/chunks
là tham chiếu cho DEV, không thay parser của implementation. Giá trị literal trong
phụ lục đã được đối chiếu; text layer, suy luận scope và citation regex chưa phải
annotation gold độc lập của toàn bộ hợp đồng.

### 4.5 Test tối thiểu và bàn giao

- PDF có text, PDF scan, DOCX; trang lỗi/thiếu phải có trạng thái rõ.
- Ngày/chủ thể để trống → null/UNKNOWN, không bịa dữ kiện.
- Quote nằm đúng chunk, offset khớp text, cùng `hop_dong_id`.
- Nhận diện citation vẫn chạy dù không biết văn bản đó đúng/hết hiệu lực.
- Chạy lại không nhân đôi chunks/citations của cùng phiên bản extraction.
- C02/C03 validate được; facts quan trọng truy về đoạn/tệp nguồn.

Tái sử dụng các files `intake.py`, `parser.py`, `ocr.py`, `chunker.py`,
`profile_extractor.py`, `citation_extractor.py`, `service.py`, `repository.py` trong
`modules/documents/`. Phần lớn hiện vẫn là skeleton/interface.

```bash
pytest -q -c backend/pyproject.toml backend/tests/contract/test_db_handoffs.py -k document
```

Lệnh này cần TEST_DATABASE_URL và kiểm tra handoffs trên DB test; vẫn cần eval parser thật.
Bàn giao C01, C02/chunks, C03, mapper/writer, PDF test hợp lệ và các test mới.

### 4.6 Recipe đọc/join cho nhóm A: tách PDF input khỏi output tham chiếu

#### A1 — Bước 1: lấy đúng tệp đầu vào và dựng C01

**Nguồn:** intake tạo `hop_dong`, `tep_nguon`, `ca_danh_gia`. Chọn **tệp chính được chỉ định**
bởi `hop_dong.tep_nguon_id`; không JOIN mọi tệp theo contract rồi lấy row đầu tiên.
Bộ mới có cả PDF và text sidecar, nên cách chọn row đầu dễ đưa text reference vào parser.

```sql
-- Q10_INTAKE: 1 case → 1 contract → 1 primary source + deployment.
SELECT ca.ca_id, ca.hop_dong_id, ca.tenant_id, ca.created_by,
       ca.ngay_danh_gia, ca.moc_ap_dung, ca.loai_moc_ap_dung,
       ca.phien_ban_id, ca.rule_version, ca.legal_knowledge_version,
       t.tep_id, t.object_uri, t.url_nguon, t.mime_type, t.sha256,
       p.schema_version, p.model_reasoning, p.model_embedding, p.prompt_version
FROM runtime.ca_danh_gia ca
JOIN runtime.hop_dong h ON h.hop_dong_id=ca.hop_dong_id
JOIN runtime.tep_nguon t
  ON t.tep_id=h.tep_nguon_id AND t.hop_dong_id=h.hop_dong_id
JOIN knowledge.phien_ban_trien_khai p ON p.phien_ban_id=ca.phien_ban_id
WHERE ca.ca_id=%(case_id)s;
```

Map row thành `AssessmentCase`:

| Phần C01 | Từ cột nào? |
|---|---|
| `ca_id`, `hop_dong_id`, tenant/actor | `ca_danh_gia` |
| `source` | `tep_id`, URI/URL, MIME, SHA của **tep_nguon chính** |
| `assessment_context` | Ngày đánh giá và mốc từ case; timestamp → date có policy timezone |
| `deployment` | `phien_ban_id`, `rule_version`, `legal_knowledge_version` của case |

Các cột model/prompt/schema của deployment giúp cấu hình/audit, không đưa thêm vào C01
nếu DTO không nhận. Tệp nguồn không tồn tại/hash sai thì dừng DI với lỗi có nguyên nhân.
Với upload mới, tính hash bytes mới và tạo rows mới; không tái dùng metadata mẫu của seed.

#### A2 — Bước 2: parser/chunker chạy từ bytes PDF

Phần dùng chung đã có: `CachedHttpSourceStorage.read(case.source)` tải URL public,
kiểm tra SHA-256 và cache local rồi trả nguyên bytes. Dependency factory cung cấp
`Services.source_storage`; nhóm A inject qua interface `SourceStorage`.
Xem [hướng dẫn, query lấy tệp chính và ví dụ nối parser](source_storage.md).

Đầu vào thật là C01 + file storage. Parser không cần JOIN bảng profile để biết phải trích
xuất gì. Sau parser/chunker, lưu chunks vào `doan_hop_dong`. Khi đối chiếu DEV, đọc chunks
seed bằng query mục 4.4. Khác chunk boundaries không tự là lỗi; so theo trang/text/span
và coverage. Nếu re-extraction tạo text khác, tạo IDs/version mới để quote cũ vẫn truy vết.

#### A3 — Đọc C02 mẫu: profile, subjects và mốc là ba tập riêng

```sql
-- Q11_PROFILE: 1 row profile; LEFT JOIN giữ case chưa có DI.
SELECT ca.ca_id, ca.hop_dong_id, p.*
FROM runtime.ca_danh_gia ca
LEFT JOIN runtime.ho_so_hop_dong p ON p.hop_dong_id=ca.hop_dong_id
WHERE ca.ca_id=%(case_id)s;
```

```sql
-- Q12_SUBJECTS: N chủ thể; evidence chunk phải thuộc cùng hợp đồng.
SELECT s.*, d.page_start, d.page_end, d.noi_dung AS evidence_text
FROM runtime.ca_danh_gia ca
JOIN runtime.chu_the_hop_dong s ON s.hop_dong_id=ca.hop_dong_id
LEFT JOIN runtime.doan_hop_dong d
  ON d.doan_id=s.doan_bang_chung_id AND d.hop_dong_id=ca.hop_dong_id
WHERE ca.ca_id=%(case_id)s ORDER BY s.vai_tro, s.chu_the_id;
```

```sql
-- Q13_MARKERS: N mốc; JOIN extraction để thấy ngày dựa trên fact nào.
SELECT m.*, tx.ten_truong, tx.gia_tri_raw AS fact_raw,
       tx.gia_tri_chuan_json, tx.trang_thai AS fact_status
FROM runtime.ca_danh_gia ca
JOIN runtime.moc_thoi_gian_hop_dong m ON m.hop_dong_id=ca.hop_dong_id
LEFT JOIN runtime.trich_xuat_truong tx
  ON tx.trich_xuat_id=m.trich_xuat_id AND tx.hop_dong_id=ca.hop_dong_id
WHERE ca.ca_id=%(case_id)s ORDER BY m.loai_moc, m.moc_id;
```

Map `p` → `ProfileFields`, subjects → `ProfileSubject[]`, mốc → `ProfileTimeMarker[]`.
Chỉ chọn fields DTO nhận, chuyển boolean TEXT như mục 8.2. Các mốc SIGNING,
EXPECTED_HANDOVER, COLLECTION… có ý nghĩa khác nhau; không dùng ngày ký hoặc ngày bàn
giao **dự kiến** để lấp ngày thu tiền/bàn giao thực tế chưa biết.

#### A4 — Facts phải đi cùng quote/offset

```sql
-- Q14_FACTS: 1 extraction → N quotes; fact không có evidence vẫn xuất hiện.
SELECT tx.trich_xuat_id, tx.ten_truong, tx.gia_tri_raw, tx.gia_tri_chuan_json,
       tx.trang_thai, tx.phuong_phap, tx.human_verified,
       b.bang_chung_id, b.doan_id, b.trich_dan_nguyen_van,
       b.ky_tu_bat_dau, b.ky_tu_ket_thuc, d.page_start, d.page_end,
       d.noi_dung AS chunk_text
FROM runtime.ca_danh_gia ca
JOIN runtime.trich_xuat_truong tx ON tx.hop_dong_id=ca.hop_dong_id
LEFT JOIN runtime.bang_chung_truong b ON b.trich_xuat_id=tx.trich_xuat_id
LEFT JOIN runtime.doan_hop_dong d
  ON d.doan_id=b.doan_id AND d.hop_dong_id=ca.hop_dong_id
WHERE ca.ca_id=%(case_id)s ORDER BY tx.trich_xuat_id, b.bang_chung_id;
```

Nhóm theo `trich_xuat_id` để tạo `ExtractedFact`; `evidence_ids` lấy từ `bang_chung_id`.
Tạo `ProfileEvidence` từ quote rows, map `trich_dan_nguyen_van` → `trich_dan`.
Nếu quote có ID nhưng `chunk_text` NULL, đó là lỗi ownership/missing source cần xử lý,
không bỏ row rồi tự coi fact đã verified. Giá mâu thuẫn giữ candidates + CONFLICT;
không lấy `MAX(gia_tri...)` để chọn một giá.

`bang_chung_ho_so` chỉ liên kết profile với chunk; bảng này **không có quote/offset**,
nên không thể tự thành `ProfileEvidence` đầy đủ. Dùng quote từ extraction có nguồn
hoặc thực hiện lại extraction. Validator `validate_document` còn yêu cầu facts mang
tên `profile.<field>` cho các profile fields có giá trị. Native rows của bộ mới có các
tên như `ngay_giao_ket`, `contract_price`. Bộ r2 đã có alias facts `profile.<field>` với phương pháp
`DERIVED_PROFILE_MAPPING_WITH_SOURCE`; giữ rõ đây là mapping/classification cần review,
không tự bật human_verified. Không chỉ đưa `p.*` vào DTO rồi bỏ qua evidence.

#### A5 — C03: citation gốc → vị trí nguồn

```sql
-- Q15_CITATIONS: 1 citation → N vị trí; chưa lấy C09 khi test extractor.
SELECT v.vien_dan_id, v.hop_dong_id, v.noi_dung_vien_dan_mau AS raw_text,
       v.so_hieu, v.ten_van_ban, v.trang_thai_trich_xuat,
       v.thong_tin_chuan_hoa_json,
       b.lien_ket_id, b.doan_id, b.trich_dan_nguyen_van,
       b.ky_tu_bat_dau, b.ky_tu_ket_thuc, d.page_start, d.page_end
FROM runtime.ca_danh_gia ca
JOIN runtime.vien_dan_phap_ly_hop_dong v ON v.hop_dong_id=ca.hop_dong_id
LEFT JOIN runtime.bang_chung_vien_dan b ON b.vien_dan_id=v.vien_dan_id
LEFT JOIN runtime.doan_hop_dong d
  ON d.doan_id=b.doan_id AND d.hop_dong_id=ca.hop_dong_id
WHERE ca.ca_id=%(case_id)s ORDER BY v.vien_dan_id, b.lien_ket_id;
```

Nhóm theo `vien_dan_id`; map raw text và normalized fields; `evidence[]` của C03 hiện là
`CitationPosition(doan_id, page_start, page_end)`. Quote/offset vẫn lưu ở bảng evidence
để grounding. Trạng thái native như `SOURCE_REGEX_REFERENCE_NOT_EXHAUSTIVE` là nhãn
phương pháp/reference, không phải enum C03; mapper chuyển về EXTRACTED/AMBIGUOUS/UNKNOWN
theo độ chắc chắn thực tế và giữ provenance ngoài enum.

**Bàn giao nhóm A:** C01 + `DocumentIntelligenceResult`, danh sách rows đã ghi, cách mở URI,
hash nguồn, version extraction/chunks. Người nhóm B nhận C02/C03/chunks đó; không phải tự
đọc lại PDF để đoán profile mà nhóm A đã xử lý.

