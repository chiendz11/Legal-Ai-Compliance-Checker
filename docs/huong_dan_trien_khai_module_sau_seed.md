# Hướng dẫn phát triển từng module sau khi đã seed PostgreSQL local

Tài liệu dành cho các nhóm làm **bước 1–2**, **bước 3–4**, **bước 5–7** và **bước 9**.
Mục tiêu: mỗi nhóm mở repo, đọc đúng dữ liệu mẫu từ DB, viết phần của mình, test độc lập,
rồi bàn giao output có thể ghép với các nhóm khác.

Nguồn nghiệp vụ: `BRD_AI_Legal_Compliance_Checker_v1.1(5).pdf` người dùng cung cấp,
mục 6–8, tiêu chí nghiệm thu và phụ lục kiến trúc A.3–A.8 bổ sung ngày 13/10/2026.
Tên bảng/kiểu cột lấy từ migration workbook `v7_4_9_RISK` đang có trong repo.
Contract thực thi hiện tại lấy từ `backend/src/legal_checker/shared/contracts/`.
Phụ lục BRD có các API/kiến trúc đề xuất; những đề xuất đó chưa tự trở thành code đã chạy.

## Mục lục

1. [Hiểu đúng phần đã có](#1-hiểu-đúng-phần-đã-có)
2. [Chuẩn bị chung và chọn ca mẫu](#2-chuẩn-bị-chung-và-chọn-ca-mẫu)
3. [Cách viết một module](#3-cách-viết-một-module)
4. [Nhóm A: bước 1–2](#4-nhóm-a-bước-12-tiếp-nhận-và-document-intelligence)
5. [Nhóm B: bước 3–4](#5-nhóm-b-bước-34-applicable-law-citation-validation-và-retrieval)
6. [Nhóm C: bước 5–7](#6-nhóm-c-bước-57-compliance-risk-và-recommendation)
7. [Nhóm D: bước 9](#7-nhóm-d-bước-9-reportui-và-ghép-hệ-thống)
8. [Các mapping cần thống nhất](#8-các-mapping-cần-thống-nhất)
9. [Thứ tự làm và cách bàn giao](#9-thứ-tự-làm-và-cách-bàn-giao)
10. [Tiêu chí hoàn thành](#10-tiêu-chí-hoàn-thành-và-các-test-cần-có)

## 1. Hiểu đúng phần đã có

### 1.1 DB đã giúp chúng ta điều gì?

Mỗi dev có database `legal_checker_dev` riêng trên máy mình:

| Schema | Chứa gì? | Ví dụ |
|---|---|---|
| `knowledge` | Luật, requirements, phiên bản, criteria, decision/risk rules, templates và quản trị knowledge | `tieu_chi_danh_gia`, `quy_tac_rui_ro` |
| `runtime` | Hợp đồng, profile, chunks, viện dẫn, ca đánh giá và các kết quả mẫu | `doan_hop_dong`, `yeu_cau_ap_dung`, `ket_qua_tieu_chi` |
| `dev_meta` | Thông tin kỹ thuật của migration và seed | `schema_migrations`, `seed_imports` |

Đã seed 50 bảng nghiệp vụ: 22 bảng `knowledge`, 28 bảng `runtime`, tổng 35.688 dòng
trong workbook đã kiểm tra. Phụ lục BRD chia bảng theo bốn **nhóm trách nhiệm**
(knowledge, runtime, quản trị, kỹ thuật); DB hiện đặt chúng vào hai **schema lưu trữ**.
Đó là hai cách phân loại cùng bộ bảng, không phải thiếu bảng hoặc cần bốn database.

Ví dụ: người làm bước 5 có thể đọc profile/chunks/C05/kết quả retrieval mẫu trong DB
để phát triển, dù người làm bước 2 và bước 4 chưa hoàn thành implementation thật.
Khi ghép hệ thống, input đó được thay bằng output thật của các bước trước.

### 1.2 Những phần code nào đã có?

| Phần | Hiện trạng | Dev tiếp tục làm gì? |
|---|---|---|
| PostgreSQL local | Có server setup, migration 50 bảng, seed và integration tests | Dùng DB riêng; bổ sung query của module |
| Knowledge SQL | Có `WorkbookKnowledgeRepository` đọc criteria, decision rules, risk/templates | Viết reader/snapshot đáp ứng interface của engines khi chuyển bước 5–7 sang DB |
| Retrieval SQL | Có `RetrievalDatasetRepository` lấy source rows theo case/run | Map DTO; triển khai index/search/rerank và writer |
| Bước 1–4 | Có interfaces/DTOs và skeleton files | Triển khai intake, parser/OCR, extraction, scope, temporal, citation, retrieval |
| Bước 5–7 | Có engines deterministic, numeric rules, gates, aggregation, risk và template recommendation | Nối DB, knowledge adapter, input mapper, observations/provider và persistence |
| Workflow | Có `DraftAssessmentWorkflow` để nối implementations được inject | Ghép implementations thật; bổ sung orchestration/persistence/recovery |
| Bước 9 | Có `build_draft_report` tạo C13 draft từ handoffs cũ | Đọc DB, ghép report, lưu version, export, API và UI |
| Bước 8 | Có C12 và interfaces review | Bổ sung review thật hoặc giữ báo cáo draft khi chưa có review |

**API đang chạy vẫn dùng knowledge JSON v7.3.2 và SQLite snapshots.**
Đặt `DATABASE_URL` không tự chuyển API sang PostgreSQL. Tài liệu này hướng dẫn công việc
cần làm tiếp trên DB đã seed; không xác nhận các module trên đã hoàn thiện.

### 1.3 Phân công theo phần bạn yêu cầu

| Nhóm | Phần BRD | Folder nghiệp vụ chính | Bàn giao |
|---|---|---|---|
| A | 1–2 | `modules/documents/` | C01; C02 + chunks; C03 |
| B | 3A, 3B, 4 | `modules/applicable_law/`, `citation_validation/`, `retrieval/` | C04; C05; C09; C06 |
| C | 5–7 | `modules/compliance/`, `risks/`, `recommendations/` | C07; C08; C10; C11 |
| D | 9 và ghép hệ thống | `modules/reports/`, `assessments/`, `api/`, `workflows/`, `frontend/` | C13; API/UI/report export |

Nếu vẫn phân công **5 người như trước**, tách nhóm B thành:
người 2 làm 3A/3B; người 3 làm Retrieval bước 4.
Nhóm A tương ứng người 1, C tương ứng người 4, D tương ứng người 5.
Các tham số `--person` của tooling cũ vẫn dùng cách đánh số 5 người này.

### 1.4 Luồng ghép module

```mermaid
flowchart TD
    A["Nhóm A — Bước 1: C01 + tệp gốc"] --> B["Nhóm A — Bước 2: C02 profile + chunks, C03 citations"]
    B --> S["Nhóm B — 3A Scope: C04"]
    S --> T["Nhóm B — 3A Temporal: C05"]
    B --> V["Nhóm B — 3B Citation Validation: C09"]
    T --> R["Nhóm B — Bước 4 Retrieval: C06"]
    B --> R
    T --> C["Nhóm C — Bước 5: C07 criterion → C08 requirement"]
    R --> C
    C --> K["Nhóm C — Bước 6: C10 risks"]
    V --> K
    K --> N["Nhóm C — Bước 7: C11 recommendations"]
    N --> H["Bước 8: C12 review — khi được triển khai"]
    H --> P["Nhóm D — Bước 9: C13 report/UI"]
    B --> P
    T --> P
    V --> P
    C --> P
    K --> P
    N --> P
    DB["Knowledge từ DB / snapshot đã chọn"] --> S
    DB --> T
    DB --> V
    DB --> R
    DB --> C
    DB --> K
    DB --> N
```

Khi chưa có bước 8, nhóm D vẫn làm **report DRAFT/PENDING** từ kết quả máy.
Báo cáo đã xác nhận cần review thật; không dùng một review seed để duyệt kết quả dev mới.

## 2. Chuẩn bị chung và chọn ca mẫu

### 2.1 Mở DB của mình

Làm theo [hướng dẫn DB local](local_database.md). Sau khi seed:

```bash
source .venv/bin/activate
python -m scripts.local_db check
```

Cấu hình mặc định: host `127.0.0.1`, port `5433`, database `legal_checker_dev`,
user `legal_checker`, password local `legal_checker_local_only`.
Dùng DBeaver/pgAdmin để xem bảng nếu chưa quen query trong Python.

### 2.2 Chọn một ca để bắt đầu

```sql
SELECT ca_id, hop_dong_id, tenant_id, phien_ban_id,
       rule_version, legal_knowledge_version, trang_thai, loai_du_lieu
FROM runtime.ca_danh_gia
ORDER BY ca_id;

SELECT a.ca_id, r.lan_chay_id, count(*) AS so_dong_retrieval
FROM runtime.ket_qua_truy_xuat r
JOIN runtime.yeu_cau_ap_dung a USING (yeu_cau_ca_id)
GROUP BY a.ca_id, r.lan_chay_id
ORDER BY a.ca_id, r.lan_chay_id;
```

Một cặp đã có trong workbook seed:
`ca_id = 'SEED_CA_001'`, `lan_chay_id = 'SEED_RUN_SEED_CA_001'`.
Đây là ca mẫu đọc dữ liệu, không phải ca mới do module của bạn đã xử lý.

Mỗi người ghi lại ít nhất: `ca_id`, `hop_dong_id`, `tenant_id`, `lan_chay_id`,
`phien_ban_id`, `rule_version`, `legal_knowledge_version`.
Khi chạy implementation thật, tạo case/run của dev riêng để giữ baseline mẫu.

### 2.3 Seed là dữ liệu mẫu, chưa phải bộ contract hoàn chỉnh

Một dòng SQL có thể chứa nhiều cột audit hơn DTO, hoặc thiếu trường DTO cần.
Vì vậy, `SELECT *` rồi đưa cả row vào Pydantic thường không đúng.
Phải có mapper chọn trường, đổi tên/kiểu và xử lý dữ liệu chưa đủ.

**Điểm đã kiểm tra trực tiếp trên DB hiện tại:** cả 160 dòng
`runtime.ket_qua_truy_xuat` đều có `tieu_chi_id = NULL`.
Trong khi C06 `RetrievalEvidence` yêu cầu `tieu_chi_id` là string.
Các dòng này có thể dùng làm tập evidence ứng viên theo requirement;
chưa thể trả trực tiếp như C06 per-criterion hợp lệ, dù `giai_doan = 'FINAL'` trong seed.
Nhóm B cần chọn evidence cho từng criterion rồi phát hành C06 có đủ ID.
Không điền criterion đầu tiên hoặc gán tất cả candidates cho mọi criterion cho đủ schema.

Dữ liệu `SYNTHETIC_DEMO`, `AI_DRAFT`, các cờ chưa human-verified giữ nguyên ý nghĩa.
Seed thành công chứng minh dữ liệu nhập được vào SQL; không chứng minh parser/OCR,
retrieval hay LLM đã xử lý đúng hợp đồng.

## 3. Cách viết một module

### 3.1 Chia trách nhiệm trong folder module

```text
modules/<module>/
├── repository.py       Query/join và ghi các bảng module phụ trách
├── mappers.py          Gợi ý file mới: SQL rows ↔ DTO/contract
├── service.py          Use case và interface; nhận dependency qua constructor/tham số
├── <logic>.py          Logic riêng: resolver, reasoner, aggregator, generator…
└── <provider>.py       Nếu cần: adapter OCR/LLM/index, nằm cùng module hoặc shared client
```

`mappers.py` và tên provider là **gợi ý file cần viết**, không phải file đã có sẵn.
Giữ chữ ký Protocol hiện có khi thêm implementation, để workflow/test vẫn gọi được.

Luồng bên trong module:

```text
Repository đọc các bảng cần thiết
        → Mapper dựng input đúng DTO
        → Service gọi logic nghiệp vụ và provider nếu cần
        → Validate output/grounding
        → Repository ghi output + evidence + audit trong transaction
```

Engine nghiệp vụ không tự mở kết nối SQL hoặc chứa key LLM.
Connection dùng chung ở `core/postgres.py`; SDK/transport dùng chung có thể ở `shared/llm/`.
Prompt và cách diễn giải kết quả thuộc module sở hữu nghiệp vụ.
LLM nhận gói dữ liệu do backend chuẩn bị, không tự JOIN DB hay tự quyết định quyền truy cập.

### 3.2 Query bằng Python

Ví dụ chạy được khi DB đã bật và `.env` được cấu hình:

```python
import os
from dotenv import load_dotenv
from legal_checker.core.postgres import connect_postgres

load_dotenv(".env")
with connect_postgres(os.environ["DATABASE_URL"]) as connection:
    rows = connection.execute(
        """
        SELECT * FROM runtime.yeu_cau_ap_dung
        WHERE ca_id = %s ORDER BY yeu_cau_ca_id
        """,
        ("SEED_CA_001",),
    ).fetchall()
print(len(rows))
```

Dùng SQL parameter `%s` cho giá trị. Query thật phải kiểm tra quyền/tenant trước khi lấy
profile, evidence hoặc report; biết một `ca_id` không đồng nghĩa được quyền đọc ca đó.

### 3.3 Ghi output và retry

Validate output trước khi ghi. Một transaction chứa kết quả và các liên kết evidence liên quan.
Transaction kết thúc thành công mới cập nhật checkpoint của ca.
Khi gọi lại cùng case/run/input, writer phải nhận diện kết quả đã lưu; khi đổi input,
tạo run mới hoặc báo conflict theo chính sách đã thống nhất.

PK hiện có ngăn trùng **ID**, chưa tự ngăn trùng nghiệp vụ nếu mỗi retry sinh UUID khác.
Writer cần ID ổn định theo case/run/module/target hoặc unique key nghiệp vụ bổ sung.
Giữ cách tạo ID tại `shared/ids.py` khi tái sử dụng engine hiện có.
Không dùng seed CLI để lưu kết quả chạy module; seed CLI chỉ nhập baseline workbook.

### 3.4 Ba lớp kiểm thử

| Lớp | Input | Cần chứng minh |
|---|---|---|
| Unit | DTO nhỏ tự dựng, fake provider | Logic đúng, xử lý UNKNOWN/lỗi, không phụ thuộc module trước |
| Integration DB | DB test có schema và dữ liệu mẫu | Query/join/mapping/writer đúng, không trộn case/run, rollback/retry đúng |
| Integration/E2E hệ thống | Implementation thật của nhiều module, hợp đồng mới | Output ghép được; upload → hai nhánh → draft/review/report đúng |

Unit test không cần gọi provider trả phí. Test có provider thật là nhóm eval riêng,
chạy khi đã cấu hình credentials và lưu version/log của lần gọi thật.

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
WHERE ca.ca_id = 'SEED_CA_001';

SELECT d.doan_id, d.thu_tu, d.page_start, d.page_end, d.section_path, d.noi_dung
FROM runtime.doan_hop_dong d
JOIN runtime.ca_danh_gia ca ON ca.hop_dong_id = d.hop_dong_id
WHERE ca.ca_id = 'SEED_CA_001'
ORDER BY d.thu_tu, d.doan_id;
```

Seed không tải nội dung PDF của `object_uri`/URL. Muốn đánh giá parser/OCR, chuẩn bị
PDF/DOCX mẫu thật và bản annotation mong đợi tương ứng: trang/text, profile, citations,
quotes/offsets. Không mặc định mọi profile seed khớp chính xác nội dung PDF gốc.

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
pytest -q -c backend/pyproject.toml backend/tests/contract/parallel/test_person_1_documents.py
```

Lệnh này kiểm tra handoff mẫu cũ; cần thêm unit/integration/eval của parser thật.
Bàn giao C01, C02/chunks, C03, mapper/writer, PDF test hợp lệ và các test mới.

## 5. Nhóm B: bước 3–4: Applicable Law, Citation Validation và Retrieval

Nhóm này có **hai nhánh độc lập ở bước 3**; bước 4 chỉ tiếp tục nhánh Applicable Law.
C09 gửi cho Risk/Report, không dùng để thêm/bớt checklist C05.

### 5.1 Bước 3A.1: Scope Resolver → C04

**Nhận:** C02 profile/chủ thể và knowledge phạm vi/requirement families.
**Trả:** `list[ScopeResolution]`, tức C04.

Đọc: `knowledge.loai_hop_dong`, `pham_vi_ap_dung`, `yeu_cau_phap_ly`, các metadata
cần thiết của `phien_ban_yeu_cau`; đọc `runtime.ho_so_hop_dong`, `chu_the_hop_dong`.

Làm lần lượt:

1. Dựng profile DTO từ giá trị đã chọn, giữ unknown và provenance.
2. Lấy các scope predicates liên quan; viết interpreter cho dạng JSON được hỗ trợ.
3. Đánh giá ba trạng thái: MATCH / NO_MATCH / UNKNOWN. Thiếu fact không mặc định NO_MATCH.
4. Tạo checklist requirement families và lý do; giữ profile/scope condition snapshot.
5. Trả C04 với `yeu_cau_ca_id`, `ca_id`, `requirement_id`, `scope_status`, `scope_reason`.
6. Writer lưu/cập nhật phần scope của `runtime.yeu_cau_ap_dung`.
   Scope và Temporal cùng viết bảng này: thống nhất ID và phân quyền cột để không ghi đè nhau.

Không chọn requirement chỉ vì hợp đồng viện dẫn nó. Một luật không được viện dẫn
vẫn có thể tạo requirement áp dụng theo profile.

### 5.2 Bước 3A.2: Temporal Resolver → C05

**Nhận:** C02 + C04 + phiên bản requirement/metadata thời gian/chuyển tiếp.
**Trả:** `list[ApplicableRequirement]`, tức C05.

Đọc: `knowledge.phien_ban_yeu_cau`, `van_ban_phap_ly`, `quan_he_van_ban`,
`ngoai_le_ap_dung`, nguồn/điều khoản cần xác minh và `runtime.moc_thoi_gian_hop_dong`.
Ghi phần temporal của `runtime.yeu_cau_ap_dung`.

Làm lần lượt:

1. Chọn mốc đúng nghĩa vụ/ngữ cảnh: ngày giao kết, hiệu lực hoặc mốc liên quan có evidence.
   Không dùng ngày chạy dev để thay mọi relevant date.
2. Chọn version trong khoảng hiệu lực `[từ, đến)` theo policy đã kiểm tra.
3. Xét thay thế/sửa đổi/chuyển tiếp và ngoại lệ; các điều kiện chưa đủ giữ chưa resolve.
4. Giữ nguyên `requirement_id`, `scope_status` và checklist của Scope Resolver.
5. Ghi version ID, mốc/loại mốc, resolution method, source snapshot và lý do.
6. Validate C05: CONFIRMED cần MATCH + RESOLVED + version ID + relevant date.

BRD phụ lục nêu cả NO_VERSION/CONFLICT. DTO C05 hiện chỉ nhận
`version_status = RESOLVED | UNKNOWN`; xem mục 8.3 trước khi mở rộng enum.

Query để xem C05 nguồn và phiên bản:

```sql
SELECT a.*, v.noi_dung AS noi_dung_requirement,
       v.hieu_luc_tu, v.hieu_luc_den, v.source_van_ban_id, v.dieu_khoan_id
FROM runtime.yeu_cau_ap_dung a
LEFT JOIN knowledge.phien_ban_yeu_cau v USING (requirement_version_id)
WHERE a.ca_id = 'SEED_CA_001'
ORDER BY a.yeu_cau_ca_id;
```

C05 được dùng cho **cả Retrieval và Compliance/Aggregation**: giữ requirement/version
và trạng thái áp dụng của ca, không chỉ là thông tin chuyển riêng từ Temporal sang Retrieval.

### 5.3 Bước 3B: Citation Validator → C09

**Nhận:** C03 + C02/context, metadata pháp lý và relevant date.
**Trả:** `list[CitationValidation]`, tức C09.

Đọc: `runtime.vien_dan_phap_ly_hop_dong`, `bang_chung_vien_dan`, chunks/mốc/profile;
`knowledge.van_ban_phap_ly`, `quan_he_van_ban`, `nguon_phap_ly`, các nguồn liên quan.
Ghi: `runtime.phat_hien_vien_dan`.

Làm lần lượt theo các files trong `modules/citation_validation/`:

1. `normalizer.py`: chuẩn hóa citation có evidence, giữ nguyên raw; nhiều ứng viên
   định danh chưa phân biệt được thì giữ UNKNOWN.
2. `identity_validator.py`: kiểm tra số hiệu/tên/loại khớp nguồn đã xác minh.
3. `temporal_validator.py`: xét hiệu lực/thay thế tại relevant date; current status lưu riêng.
4. `domain_validator.py`: xét phù hợp giao dịch/chủ thể/vấn đề pháp lý.
5. `classifier.py`: trả VALID / STALE / INVALID / UNKNOWN với reason code, lý do và nguồn.
6. `service.py`/writer: validate case/citation IDs, lưu finding + snapshot + run/version.

Ví dụ test nghiệp vụ bắt buộc: citation hợp lệ ngày ký nhưng bị thay thế sau đó vẫn
VALID cho đánh giá lịch sử; có thể hiển thị current status đã hết hiệu lực riêng.
Citation sai domain có reason/risk phù hợp, nhưng không đổi compliance label.

```sql
SELECT f.finding_id, f.ca_id, f.vien_dan_id, f.van_ban_id, f.trang_thai,
       f.ma_ly_do, f.moc_ap_dung, f.finding_verified, f.lan_chay_id
FROM runtime.phat_hien_vien_dan f
WHERE f.ca_id = 'SEED_CA_001'
  AND f.lan_chay_id = 'SEED_RUN_SEED_CA_001'
ORDER BY f.finding_id;
```

### 5.4 Bước 4: Retrieval → C06

**Nhận:** C05 + chunks đúng hợp đồng + criteria của các requirement versions đã chọn.
**Trả:** `list[RetrievalEvidence]`, tức C06 có liên kết **per-criterion**.

Đọc: `runtime.yeu_cau_ap_dung`, `doan_hop_dong`; knowledge `tieu_chi_danh_gia`,
`phien_ban_yeu_cau`, policies liên quan; index/embedding của đúng phiên bản.
Ghi: `runtime.ket_qua_truy_xuat`; nếu triển khai embeddings, ghi
`runtime.embedding_doan_hop_dong` và metadata model/index.

Làm lần lượt:

1. Dùng `RetrievalDatasetRepository.load_input_rows(ca_id)` để lấy case, C05 source rows,
   chunks và criteria. Map C05/chunks sang DTO; kiểm tra quyền trước khi đọc.
2. Với requirement chưa resolve, giữ trạng thái chưa đủ dữ liệu; không chọn version ngẫu nhiên.
3. Dựng query theo từng criterion từ nội dung requirement/criterion/evidence cần tìm.
4. Xây index toàn tài liệu; search ứng viên và lọc đúng contract/index version.
5. Rerank/select theo criterion; phát hành C06 có `yeu_cau_ca_id`, `tieu_chi_id`, `doan_id`.
6. Ghi score/rank, stage, selected flag và model/retrieval/index/run versions.
7. Evidence rỗng vẫn là kết quả retrieval hợp lệ của criterion đó; bước 5 quyết định
   UNKNOWN hay MISSING dựa thêm coverage/absence gates, không phải retrieval tự kết luận.

Ví dụ dùng repository hiện có:

```python
import os
from dotenv import load_dotenv
from legal_checker.modules.retrieval.repository import RetrievalDatasetRepository

load_dotenv(".env")
repository = RetrievalDatasetRepository(os.environ["DATABASE_URL"])
inputs = repository.load_input_rows("SEED_CA_001")
candidates = repository.load_seeded_evidence("SEED_CA_001", "SEED_RUN_SEED_CA_001")
print(len(inputs["requirements"]), len(inputs["chunks"]), len(candidates))
```

`candidates` là rows mẫu, chưa tự thành C06 vì thiếu criterion ID như mục 2.3.
Khi chạy Retrieval thật, module của bạn là bên tạo lựa chọn per-criterion đó.
File `retriever.py`, `indexer.py`, `reranker.py`, `service.py` đã có điểm đặt implementation.

Embedding seed cần giữ đúng nhãn model/index. Không gọi vector baseline từ vựng là
semantic embedding của LLM; khi đổi embedding model phải xây index tương ứng.

### 5.5 Test và bàn giao nhóm B

- Profile thiếu fact → Scope UNKNOWN; luật không được viện dẫn vẫn có thể áp dụng.
- Ngày đúng tại biên hiệu lực; thiếu ngày; chuyển tiếp chưa rõ → trạng thái/lý do đúng.
- Đổi C09 VALID thành STALE không thay C04/C05/C08.
- Citation ambiguity, sai số hiệu/domain, nguồn chưa xác minh → không đoán VALID.
- C06 đúng case/contract/criterion/run; Recall@K đo trên evidence đã annotation.
- Search toàn hợp đồng, không chỉ các đoạn có tên luật; retrieval miss không thành VIOLATED.

```bash
pytest -q -c backend/pyproject.toml backend/tests/contract/parallel/test_person_2_legal.py
pytest -q -c backend/pyproject.toml backend/tests/contract/parallel/test_person_3_retrieval.py
```

Đây là tests của handoffs tổng hợp cũ; bổ sung DB mapper/query tests và eval riêng.
Bàn giao C04/C05 cho Retrieval/Compliance, C09 cho Risk/Report, C06 cho Compliance.

## 6. Nhóm C: bước 5–7: Compliance, Risk và Recommendation

### 6.1 Việc nên làm đầu tiên

Logic bước 5–7 đã có. Trước khi gọi LLM, làm ba việc để dùng được workbook DB mới:

1. Viết `SqlKnowledgeSnapshot` hoặc adapter tương đương đáp ứng `KnowledgeSnapshot`.
   Đây là implementation **cần bổ sung**, không phải class đã có.
2. Map C05/C06/chunks/facts thành input của engines, với case/run/release nhất quán.
3. Viết PostgreSQL writer cho C07/C08/C10/C11 và evidence.

`WorkbookKnowledgeRepository` hiện là helper query, **chưa đáp ứng toàn bộ**
`KnowledgeSnapshot`: engines cần các indices `criteria`, `versions`, `risks`,
`recommendations`, `aggregations`, `articles`, `documents`, `tables`, cùng
`criteria_for`, `decision`, `legal_basis`, `sha256`.

Reader hiện có từ JSON chỉ nhận schema v7.3.2. Reader SQL mới phải xử lý workbook v7_4_9:
JSONB trả dict/list trong khi một số engines hiện gọi `json.loads` trên chuỗi rule.
Chọn một dạng rule nội bộ thống nhất và test adapter, không pass raw SQL helper vào engine.
Soát các rule shapes/policies mới; policy chưa hỗ trợ phải báo chưa hỗ trợ/UNKNOWN rõ.
Không diễn giải JSON bằng `eval` và không gán old hash cho knowledge mới.

### 6.2 Bước 5: criterion reasoning → C07 → aggregation C08

**Input:** C05, C06 per-criterion, chunks/facts/chứng từ ngoài và knowledge đã pin.
**Output:** `CriterionResult` (C07), `RequirementResult` (C08).

Đọc:

- Runtime: applicable requirements, selected retrieval/chunks, field facts/evidence;
  `chung_tu_bo_sung`, `bang_chung_ngoai` khi cần chứng từ thực hiện nghĩa vụ.
- Knowledge: criteria, requirement versions, decision rules, nguồn/điều khoản,
  exceptions, evidence policies và aggregation rules.

Ghi: `runtime.ket_qua_tieu_chi`, `bang_chung_ket_qua`, `bang_chung_ngoai`,
`ket_qua_tuan_thu`. Các C07/C08 đã seed là output tham khảo, không phải input
để reasoning tự sao chép kết luận.

#### Luồng xử lý một criterion

1. Từ C05 chọn requirement version; lấy criteria của version đó.
2. Lấy C06 của đúng `yeu_cau_ca_id` + `tieu_chi_id` + run, selected FINAL evidence.
3. Chuẩn bị gói nhỏ: criterion, requirement/legal basis, decision rules, ngoại lệ,
   evidence text/ID và facts đã xác minh. Không gửi cả 50 bảng cho một prompt.
4. Rule định lượng tính bằng `Decimal`; tiêu chí ngữ nghĩa có thể dùng provider
   tạo `Observation` theo interface `ObservationProvider.observe`.
5. Validate proposed output/ID/enum; kiểm tra quote/offset và provenance bằng backend.
6. Đặt gates theo kết quả kiểm tra thật. LLM tự nói “đã xác minh” không đủ để bật gate.
7. Chạy `criterion_reasoner.reason` để có C07; unknown giữ nguyên lý do.
8. Chạy `requirement_aggregator.aggregate` để có C08 theo policy đã chọn.
9. Ghi findings và evidence/snapshots/model/prompt/run version trong transaction.

Bốn nhãn C07: SATISFIED / MISSING / VIOLATED / UNKNOWN.
Bốn nhãn C08: COMPLIANT / PARTIAL / NON_COMPLIANT / INSUFFICIENT.
Requirement chưa resolve không biến thành kết quả chắc chắn; requirement NOT_APPLICABLE
được loại có lý do, không được dùng để giấu knowledge gap.

**MISSING cần kiểm tra đầy đủ:** criterion bắt buộc có nội dung trong hợp đồng;
coverage và absence được xác nhận; trang/phụ lục đọc đủ; evidence/source/scope/version/
ngoại lệ đủ tin cậy và không có mâu thuẫn. Retrieval rỗng hoặc thiếu OCR không tự thỏa các điều kiện này.
SATISFIED/VIOLATED cần evidence có thể kiểm chứng; lời hứa trong hợp đồng không tự chứng minh
một nghĩa vụ bên ngoài đã được thực hiện.

Ví dụ query evidence đã chọn — vẫn cần xử lý criterion ID thiếu trong seed:

```sql
SELECT r.truy_xuat_id, a.yeu_cau_ca_id, a.requirement_version_id,
       r.tieu_chi_id, r.doan_id, r.thu_hang, d.noi_dung
FROM runtime.ket_qua_truy_xuat r
JOIN runtime.yeu_cau_ap_dung a USING (yeu_cau_ca_id)
JOIN runtime.ca_danh_gia ca USING (ca_id)
JOIN runtime.doan_hop_dong d
  ON d.doan_id = r.doan_id AND d.hop_dong_id = ca.hop_dong_id
WHERE ca.ca_id = 'SEED_CA_001'
  AND r.lan_chay_id = 'SEED_RUN_SEED_CA_001'
  AND r.duoc_chon IS TRUE AND r.giai_doan = 'FINAL'
ORDER BY a.yeu_cau_ca_id, r.thu_hang, r.truy_xuat_id;
```

Quote check thực thi theo text chunk:

```python
assert chunk.noi_dung[evidence.ky_tu_bat_dau:evidence.ky_tu_ket_thuc] == evidence.trich_dan
```

`chunk`/`evidence` trong ví dụ là DTO đã dựng. Offset là vị trí ký tự trong text chunk,
không phải byte PDF hoặc vị trí trên text đã bị chuẩn hóa khác.

#### Tái sử dụng engine hiện có

```text
modules/compliance/observations.py             Interface cung cấp Observation
modules/compliance/numeric_rules.py            Rule số liệu
modules/compliance/criterion_reasoner.py       reason(request, knowledge) → C07
modules/compliance/requirement_aggregator.py   aggregate(context, knowledge, C07, C05) → C08
modules/compliance/grounding_validator.py      Kiểm tra handoff/provenance
```

Policy `AGG_CAN_HO_V1` hiện có: chưa confirmed/thiếu rule/thiếu findings → INSUFFICIENT;
có VIOLATED → NON_COMPLIANT; còn UNKNOWN → INSUFFICIENT; tất cả MISSING → NON_COMPLIANT;
có SATISFIED cùng MISSING → PARTIAL; tất cả SATISFIED → COMPLIANT.
Đây là policy đang được code hỗ trợ, không phải rule chung cho mọi requirement trong tương lai.

### 6.3 Bước 6: Risk Aggregation → C10

**Nhận:** C07 từ nhánh compliance, C09 từ nhánh citation, context và risk rules/catalog.
**Trả:** `list[RiskResult]` (C10).

Đọc knowledge `quy_tac_rui_ro`, `danh_muc_rui_ro`; runtime C07/C09 của đúng ca/run.
Ghi `runtime.ket_qua_rui_ro`.

1. Match compliance trigger theo criterion/finding/context; không map chỉ một status chung.
2. Match citation trigger theo status/reason/domain/relevant context và verification.
3. Lấy risk ID và severity từ rules/catalog; giữ rule/risk snapshot.
4. Mỗi risk tham chiếu **một** C07 hoặc C09 (XOR), cùng case và evidence/legal basis.
5. Hợp nhất danh sách, giữ branch/provenance; không ghi đè compliance label theo citation.
6. Writer lưu mapping C10 → bảng SQL như mục 8.1, kiểm tra run lineage trước commit.

Tái sử dụng `risks/aggregator.py`, `compliance_mapper.py`, `citation_mapper.py`,
`common.py`, `service.py`. C10 hiện hỗ trợ COMPLIANCE / CITATION / VERIFICATION.
UNKNOWN/chưa xác minh cần luồng yêu cầu thông tin phù hợp; không được biến thành
một kết luận vi phạm đã xác nhận.

### 6.4 Bước 7: Recommendation → C11

**Nhận:** C10 đã xác định + risk/template mappings + context/evidence/legal basis.
**Trả:** `list[Recommendation]` (C11), chờ review.

Đọc `knowledge.rui_ro_khuyen_nghi`, `danh_muc_khuyen_nghi`, criterion/requirement
và context liên quan. Ghi `runtime.khuyen_nghi_danh_gia`.

1. Theo `risk.rui_ro_id` tìm link → template; không viết một câu chung cho mọi risk.
2. Giữ action/priority/severity và các `required_elements_json`/`gioi_han_sinh_json`.
3. Template engine hiện có tạo nội dung cơ bản. Nếu bổ sung LLM, chỉ cá thể hóa
   câu chữ từ facts/basis đã có; không tự tạo luật, ngày, số tiền hoặc danh tính.
4. UNKNOWN/chưa đủ căn cứ → yêu cầu xác minh đúng dữ kiện còn thiếu.
5. Validate C11: cùng risk ID, legal basis/evidence, template và knowledge/rule version.
6. Lưu nội dung, action, priority và snapshots; giữ review PENDING.

`Recommendation.model_version` hiện bị giới hạn `TEMPLATE_ENGINE_NO_LLM`,
`prompt_version` là `NOT_USED`; một số handoff validators so sánh đúng template output.
Muốn có LLM-generated C11 cần cập nhật contract/version/validator/tests có chủ đích;
không ghi output LLM nhưng để metadata “NO_LLM”.

#### Hai cách chạy cần phân biệt

- `evaluate_compliance` trong `compliance/service.py` phục vụ handoff **người 4 cũ**:
  C07/C08 + risks/actions chỉ từ compliance. `ComplianceOutput` không nhận citation-sourced risks.
- `workflows/steps_5_7.evaluate` nhận cả C09 và hợp nhất hai nhánh để trả C07–C11 đầy đủ.

Nếu nhóm C hiện phụ trách toàn bộ 5–7, dùng luồng đầy đủ. Nhóm D lấy C10/C11 đã hợp nhất
để làm report; không tạo lại citation risks/recommendations một lần nữa.

### 6.5 LLM và audit: khi nào cần?

Không bắt buộc LLM cho mọi criterion. Rule số liệu, aggregation và risk mapping có thể
chạy deterministic; LLM phù hợp extraction fallback, semantic reasoning và viết khuyến nghị.
Hiện `shared/llm/client.py` chưa có provider implementation.

Mỗi lời gọi thật cần timeout, retry có giới hạn, validate structured output và X02 audit
lưu vào `runtime.nhat_ky_goi_llm`: provider/model/prompt/schema version, input/output hash,
tokens, latency, cost nếu có, lỗi, attempt và trace.
Dữ liệu hợp đồng là dữ liệu đầu vào, không được đổi rules/system instruction hoặc tự gọi tool.
Không tạo log SUCCESS giả cho template engine hoặc fixture replay.

### 6.6 Test và bàn giao nhóm C

- Numeric threshold boundary, unknown facts, chứng từ ngoài chưa verified.
- MISSING gates; evidence sai quote/contract/criterion/run; provider trả ID/enum sai.
- UNKNOWN/INSUFFICIENT và policy C08; ngoại lệ/chuyển tiếp chưa rõ.
- Risk đúng catalog/rule và XOR source; citation không thay checklist/compliance.
- Recommendation đúng risk/action/basis; không tự nâng severity hoặc tự duyệt kết quả.
- Writer rollback, retry không nhân đôi, lịch sử run không bị ghi đè.

```bash
pytest -q -c backend/pyproject.toml backend/tests/contract/parallel/test_person_4_compliance.py
```

Test này dùng knowledge/fixtures cũ; thêm integration DB và adapter tests cho v7_4_9.
Bàn giao C07/C08/C10/C11, knowledge adapter, observations/provider,
mapper/writer và các test chứng minh lineage/grounding.

## 7. Nhóm D: bước 9: Report/UI và ghép hệ thống

### 7.1 Mục tiêu

Báo cáo trình bày profile, checklist/requirements, kết quả compliance, citations,
risks, recommendations, evidence/legal basis, uncertainty và trạng thái review.
Báo cáo không tự chạy lại reasoning để thay kết luận đã lưu.

Input chính: C01/C02/C03/C04/C05/C07/C08/C09/C10/C11 và C12 nếu có review thật.
Output: `FinalReport` / C13, bản report được lưu version và API/UI/export theo quyền.

### 7.2 Đọc và ghi bảng nào?

Đọc ca/profile, applicable requirements, criterion/requirement results và evidence,
citation findings, risks/recommendations; deployment metadata, quyền và review.
Ghi `runtime.bao_cao_danh_gia`; export PDF/DOCX lưu file trong storage và ghi `report_uri`.
Review events nếu nhóm D phụ trách thêm bước 8 thì ghi `runtime.nhat_ky_review`
qua service riêng, không sửa trực tiếp output máy để bỏ mất lịch sử.

Không JOIN một câu toàn bộ bảng kết quả: nhiều C07 × nhiều C09 × nhiều risks sẽ
nhân dòng. Đọc từng tập theo case/run rồi nhóm theo IDs để xây report.

Ví dụ đọc C07 và evidence đúng lần chạy:

```sql
SELECT k.ket_qua_id, k.tieu_chi_id, k.loai_phat_hien, k.giai_thich,
       b.doan_id, b.trich_dan, b.ky_tu_bat_dau, b.ky_tu_ket_thuc
FROM runtime.ket_qua_tieu_chi k
LEFT JOIN runtime.bang_chung_ket_qua b USING (ket_qua_id)
WHERE k.ca_id = 'SEED_CA_001'
  AND k.lan_chay_id = 'SEED_RUN_SEED_CA_001'
ORDER BY k.ket_qua_id, b.lien_ket_id;
```

Một C07 có nhiều evidence sẽ xuất hiện nhiều dòng; mapper nhóm lại thành
một `CriterionResult.evidence[]`, không tăng số findings theo số dòng JOIN.
Các bảng không có run ID cần cách chọn nhất quán như mục 8.4.

### 7.3 Làm lần lượt

1. **Reader:** kiểm tra quyền/tenant, chọn case + release + run/report version; lấy các
   tập kết quả và lý do chưa đủ dữ liệu của mỗi nhánh.
2. **Mapper:** dựng DTOs và `ReportContent`; ánh xạ đúng status, snapshots, dates/evidence.
   Thiếu kết quả phải hiển thị chưa chạy/chưa đủ dữ liệu, không mặc định COMPLIANT.
3. **Builder:** chia riêng compliance results, citation validation, compliance/citation/
   verification risks; giữ link risk → finding → evidence/legal basis.
4. **Summary:** tính coverage/counts từ danh sách thực, giải thích denominator nếu có score.
   UNKNOWN/INSUFFICIENT không được hiện như đã compliant; không bắt buộc score nếu
   chưa thống nhất công thức/version, có thể hiển thị counts/coverage trước.
5. **Review status:** tạo DRAFT/PENDING khi chưa có review cho đúng outputs;
   giữ kết quả máy gốc và effective reviewed result riêng khi C12 được triển khai.
6. **Persistence:** sinh report ID/version; lưu `report_json`, coverage, rule/knowledge hash,
   thời điểm và URI nếu export. Cùng input/retry không tạo report trùng; review mới
   tạo version mới, không ghi đè report đã xuất.
7. **API:** triển khai reader/status/report/export endpoints và quyền ở `api/v1/`.
   Các URL trong phụ lục A.6 BRD là API đề xuất; routes upload/report/review của repo
   hiện vẫn là skeleton, cần implement và cập nhật OpenAPI.
8. **UI:** gọi API, hiển thị progress và từng section; chọn finding mở đúng evidence
   và legal basis; hiển thị relevant/current citation status riêng và badge draft/review.
9. **Orchestration:** nối services trong `workflows/assessment_workflow.py`; API/worker
   dùng chung use cases. Worker/Celery hiện là skeleton, queue/retry/recovery cần code riêng.

UI không giữ database password, không gọi cloud DB bằng service/admin key,
không tự JOIN DB hay gọi LLM để đưa ra kết luận khác backend.

### 7.4 Dùng builder hiện có sao cho đúng?

`modules/reports/builder.py:build_draft_report` hiện nhận `IntegrationInput` của
bộ handoff 5 người: compliance output **chưa có citation risks**.
Builder tự thêm citation risks/actions nên dùng được với handoff cũ.

Với C10/C11 đã hợp nhất từ nhóm C, cần builder/reader path phù hợp đọc outputs đó,
hoặc thay đổi interface rõ ràng. Không vừa dùng outputs đã hợp nhất vừa chạy builder cũ
để bổ sung nhánh citation lần nữa. Giữ test chống risk/recommendation trùng.

`FinalReport.phien_ban_bao_cao` hiện là string (`draft-v1` trong helper),
SQL `bao_cao_danh_gia.phien_ban_bao_cao` là INTEGER. Chọn quy ước version/mapping
hoặc migration trước khi writer thật; không cast `draft-v1` thành số tùy ý.

### 7.5 Màn hình/báo cáo tối thiểu

| Section | Người xem cần hiểu được gì? |
|---|---|
| Contract Profile | Giao dịch/chủ thể/mốc nào được chọn, fact nào chưa rõ |
| Applicable Law | Requirement/version nào áp dụng; nguồn và lý do chưa resolve |
| Compliance | C08 và từng C07; quote/offset, basis, uncertainty |
| Citation Validation | Citation hợp đồng nêu, status/reason tại relevant date, current status riêng |
| Risks | Loại nguồn, severity, rule và finding nguồn |
| Recommendations | Hành động gắn với risk và evidence/basis; review status |
| Review/Audit | Kết quả máy/người, ai sửa, lý do, version/run đã dùng |

### 7.6 Test và bàn giao nhóm D

- Report không bỏ mất UNKNOWN, unresolved requirements hoặc nhánh citation.
- Không trộn case/tenant/run; không nhân số findings do nhiều evidence/JOIN.
- C10/C11 đã hợp nhất không bị tạo trùng; mỗi risk mở đúng finding nguồn.
- DRAFT/PENDING không hiện như report đã duyệt; seed review không duyệt kết quả mới.
- Relevant/current status citation được hiển thị riêng, source/version truy vết được.
- Report version mới khi review thay đổi; export/read đúng quyền.

```bash
pytest -q -c backend/pyproject.toml backend/tests/contract/parallel/test_person_5_integration.py
```

Bàn giao report reader/mapper/builder/writer/exporter, API/UI, wiring và integration/E2E tests.
Nếu chưa triển khai review, ghi rõ demo hiện chỉ phát hành report draft.

## 8. Các mapping cần thống nhất

### 8.1 SQL column và DTO có thể khác tên

| SQL | DTO hiện có | Lưu ý |
|---|---|---|
| `yeu_cau_ap_dung.ly_do` | `ApplicableRequirement.reason` | TEXT → dict lý do có tên key rõ |
| Retrieval score columns | `RetrievalEvidence.scores` | Gộp dict; NUMERIC/Decimal → float khi DTO yêu cầu |
| `ket_qua_tieu_chi.loai_phat_hien` | `CriterionResult.finding` | Enum C07 |
| C07 các cột flags | `CriterionResult.gates` | Dựng Gates; không tự bật verified từ sự tồn tại row |
| `ket_qua_tuan_thu.nhan` | `RequirementResult.status` | Enum C08 |
| `phat_hien_vien_dan.van_ban_id` | `normalized_van_ban_id` | Normalized target; có thể chưa xác định |
| `phat_hien_vien_dan.trang_thai` | `CitationValidation.status` | Enum C09 |
| `phat_hien_vien_dan.moc_ap_dung` | `relevant_date` | Ngày dùng kiểm tra, current status lấy snapshot riêng |
| `phat_hien_vien_dan.ma_ly_do` | `reason_code` | Không bỏ reason code |
| `ket_qua_rui_ro.ket_qua_id` | `RiskResult.ket_qua_rui_ro_id` | Khác với PK C07 cùng tên ket_qua_id ở bảng khác |
| `ket_qua_rui_ro.nguon_tieu_chi_id` | `source.ket_qua_tieu_chi_id` | Tham chiếu **PK kết quả C07**, không phải criterion ID |
| `ket_qua_rui_ro.nguon_vien_dan_id` | `source.citation_finding_id` | Tham chiếu finding C09; XOR với nguồn C07 |
| `ket_qua_rui_ro.severity_snapshot` | `RiskResult.severity` | Giữ severity đã chọn |
| `khuyen_nghi_danh_gia.noi_dung_snapshot` | `Recommendation.noi_dung` | Nội dung của lần đánh giá |
| `khuyen_nghi_danh_gia.dieu_kien_snapshot` | `Recommendation.dieu_kien_snapshot` | SQL TEXT có cả prose; DTO cần dict, phải có mapper |
| `bao_cao_danh_gia.phien_ban_bao_cao` | `FinalReport.phien_ban_bao_cao` | INTEGER ↔ string, thống nhất version policy |
| Timestamp SQL của ngày đánh giá | `AssessmentTiming.ngay_danh_gia` | DTO cần date; mapper chuyển có policy timezone |

Một số dữ liệu C07/C10 cần như `mandatory`, `excluded`, `evidence_ids`,
`legal_basis_ids`, risk snapshot đầy đủ không có cột riêng tương ứng ở mọi bảng.
Đọc từ snapshot/quan hệ có căn cứ hoặc bổ sung schema/snapshot có version;
không mặc định giá trị cho đủ Pydantic rồi gọi là kết quả đã xác minh.

### 8.2 Ví dụ map C05 chạy được với dữ liệu seed hiện tại

Ví dụ này chỉ map và validate **C05**, chưa tạo context/knowledge adapter để chạy engines.

```python
import os
from dotenv import load_dotenv
from legal_checker.core.postgres import connect_postgres
from legal_checker.shared.contracts.temporal import ApplicableRequirement

load_dotenv(".env")
with connect_postgres(os.environ["DATABASE_URL"]) as connection:
    rows = connection.execute(
        "SELECT * FROM runtime.yeu_cau_ap_dung WHERE ca_id=%s ORDER BY yeu_cau_ca_id",
        ("SEED_CA_001",),
    ).fetchall()

fields = set(ApplicableRequirement.model_fields) - {"reason"}
requirements = [
    ApplicableRequirement.model_validate({
        **{name: row[name] for name in fields},
        "reason": {"summary": row["ly_do"] or ""},
    })
    for row in rows
]
print([item.requirement_id for item in requirements])
```

48 dòng applicable requirements hiện đã được kiểm tra với mapping này.
C06 chưa thể map tương tự cho cả workbook vì criterion ID thiếu.

Profile có các flags SQL TEXT `CO/KHONG/UNKNOWN`; C02 cần bool nullable/strict.
Map CO → True, KHONG → False, UNKNOWN/null → None. Không gọi `bool('KHONG')`
vì Python trả True; giá trị lạ phải báo lỗi thay vì tự đoán.

### 8.3 BRD mới có trạng thái phong phú hơn contract hiện tại

- C05 hiện chỉ RESOLVED/UNKNOWN cho version. NO_VERSION/CONFLICT phải giữ reason
  và unknown đúng ý nghĩa, hoặc mở rộng DTO/version/tests thống nhất trước khi trả enum mới.
- C10 hiện có VERIFICATION; seed SQL đang giữ COMPLIANCE/CITATION và bản chất rủi ro
  trong rule/catalog/snapshots. Mapper phải xét provenance/context; không gán loại mới
  chỉ từ tên severity hay một chuỗi status chung.
- C07/C11 hiện review PENDING; luồng review nên lưu C12/effective result riêng,
  không tự đổi DTO AI output thành APPROVED.
- Khuyến nghị LLM và report version cần mapping/contract update như các mục trên.

Không sửa enum của một module riêng rồi để module kế tiếp nhận schema cũ.

### 8.4 Run lineage và snapshot là phần code chung còn phải bổ sung

**Schema seed hiện tại chưa đủ để bảo đảm mọi historical run bằng một phép lọc `lan_chay_id`.**

| Dữ liệu | Có run ID trực tiếp trong schema hiện tại? | Cách xử lý |
|---|---|---|
| Retrieval, C07, C09 | Có `lan_chay_id` | Luôn lọc cùng case/run và kiểm tra target IDs |
| Evidence C07 | Không; có `ket_qua_id` | JOIN qua C07 đã chọn đúng run |
| C08 | Không | Cần lineage bổ sung/snapshot run trước khi chạy nhiều runs cùng ca |
| C10 | Không; có source C07 hoặc C09 | JOIN theo finding nguồn đã pin; phải xử lý cả hai nhánh |
| C11 | Không; có risk ID | Theo risk đã chọn đúng lineage |
| C13 | Không; có report version | Report cần pin run/outputs trong snapshot hoặc metadata bổ sung |
| Profile/subjects/time markers | Không có run/extraction version đầy đủ | Re-extraction cần version/snapshot trước khi giữ nhiều kết quả lịch sử |
| C04/C05 checklist | Không có run ID | Chốt checklist snapshot/revision theo ca/lần chạy, không overwrite lịch sử |

Để phát triển logic, mỗi người có thể bắt đầu bằng **case dev mới cho mỗi lần thử**.
Trước khi triển khai rerun/retry đầy đủ cho cùng ca, người phụ trách phần chung
(thường nhóm D phối hợp nhóm C) cần migration tiếp theo: bảng run/checkpoints hoặc
các cột/quan hệ lineage phù hợp, unique constraints và reader/writer tests.
Đây là việc **cần viết**, không phải đã được migration 1 giải quyết.
Không sửa migration 1 đã áp dụng hoặc đoán C08 cùng run chỉ vì cùng `ca_id`.

**Knowledge version cũng cần reader phát hành snapshot:** `dev_meta.seed_imports.source_sha256`
là hash **file Excel nhập**, không phải hash knowledge của mọi ca.
`phien_ban_trien_khai` và runtime có pins/hashes lịch sử; các bảng knowledge SQL hiện
chứa một baseline nhập chung, chưa là kho nội dung đầy đủ của mọi release lịch sử.
Adapter phải chọn/tạo snapshot có nội dung rõ và hash đúng nội dung đó; giữ các cờ draft/
unverified, không tự gọi dataset dev là release đã chuyên gia duyệt.
Case seed dùng historical pins chỉ dùng để đối chiếu dữ liệu, không mặc định tái dựng
được toàn bộ historical knowledge từ các bảng mutable hiện tại.

### 8.5 Điểm nối kiến trúc hiện tại

Phụ lục BRD dùng các tên tầng `interfaces/adapters/bootstrap` để diễn tả trách nhiệm.
Repo đã tổ chức theo module: ports ở owning modules, implementations DB/OCR/LLM
ở repositories/providers, connection/transport dùng `core`/`shared`, wiring tại
`api/dependencies.py` hoặc factory dùng cho workflow/worker.
Không cần tạo lại các folder cũ đã bỏ để thực hiện hướng dẫn này.

Factory hiện chỉ build JSON Knowledge + SQLite Store.
Chuyển runtime API sang PostgreSQL cần inject reader/store mới và test endpoints;
không đưa query SQL trực tiếp vào route hoặc engine để bỏ qua ranh giới module.

## 9. Thứ tự làm và cách bàn giao

### 9.1 Khởi động song song

| Nhóm | Việc làm ngay bằng DB đã seed | Không cần đợi |
|---|---|---|
| A | PDF test + parser/extraction/chunker + C01/C02/C03 mapper/writer | Scope/Retrieval/Reasoning |
| B — Legal | Profile seed → scope/temporal/citation rules + C04/C05/C09 | DI thật |
| B — Retrieval | C05/chunks/criteria seed → search/select per-criterion + C06 | Scope/Temporal thật |
| C | SQL knowledge adapter, rule/gate tests, input mapper/writer; candidates seed để dựng test có criterion rõ | DI/Search/LLM thật |
| D | Report reader/mapper/UI layout với outputs mẫu; review/run/version/wiring design | Upstream implementations thật |

Riêng **test hiệu quả DI thật** cần PDF có annotation. **Test Retrieval/Reasoning thật**
cần evidence/finding đã annotation hoặc reviewer xác nhận. Các expected outputs seed
có thể kiểm tra mapping/joins; việc dùng chúng làm gold về pháp lý cần xác nhận trước.

### 9.2 Các phần chung nên chốt trước khi ghép

- Shared DTO/version và mapping khác biệt mục 8.
- DB knowledge snapshot reader/hash policy: nhóm C phối hợp người quản trị knowledge.
- Case/run/extraction/report lineage, transactions/idempotency: nhóm D phối hợp writers.
- Quyền tenant/case, source storage và LLM audit transport: phần dùng chung, owner rõ.
- Bước 8: owner/ports review và điều kiện report được publish; chưa có thì chỉ draft.

Các phần này không ngăn viết unit logic song song; chúng là điều kiện để input/output
thật ghép được mà không trộn dữ liệu hoặc sai snapshot.

### 9.3 Mỗi PR nên bàn giao gì?

1. Input/output contract và implementation theo đúng interface.
2. Repository/mappers + SQL/tables đọc/ghi; mapping thiếu dữ liệu có hành vi rõ.
3. Unit tests, DB integration tests và ca mẫu đã chạy.
4. Cách khởi tạo dependency/cách gọi module thật; cấu hình provider nếu cần.
5. Giới hạn còn lại: thiếu PDF, chưa có LLM, policy chưa hỗ trợ hoặc mới chạy fake provider.

Khi ghép, thay từng implementation trong `DraftModules`, giữ các module còn lại bằng
fake/fixtures để tìm lỗi interface; sau đó chạy cả upstream thật trên hợp đồng mới.
Workflow hiện tạo draft C01–C11, chưa tự tạo/publish C13 hoặc persist full assessment.

### 9.4 Tooling hiện có và cách dùng đúng

```bash
ruff check --config backend/pyproject.toml .
ruff format --check --config backend/pyproject.toml .
python -m scripts.parallel_dev --all-scenarios
```

`parallel_dev` dùng fixtures tổng hợp cũ ở `examples/parallel`, không tự đọc workbook DB.
Nó kiểm tra schema/handoff/wiring của baseline cũ, không đo OCR/search/LLM của module thật.
Có thể dùng `--person` và `--verify-output` theo [hướng dẫn parallel cũ](parallel_development.md),
nhưng dataset/case/hash phải đúng với bộ fixture đó. Không đưa output của case workbook
v7_4_9 vào validator của một scenario v7.3.2 rồi kỳ vọng tự khớp knowledge/context.

Chạy suite có PostgreSQL integration trên DB test riêng:

```bash
TEST_DATABASE_URL='postgresql://legal_checker:legal_checker_local_only@127.0.0.1:5433/legal_checker_test' \
  pytest -q -c backend/pyproject.toml
```

Tests DB hiện tạo DB con riêng và xóa sau khi chạy; không ghi DB dev.
Tests mới của mỗi module cũng dùng DB test/fake provider và seed nhỏ có refs đóng;
không phụ thuộc đường dẫn Downloads của một người hoặc truy cập cloud DB chung.
CI có PostgreSQL service; dữ liệu workbook gốc ở `data/private` không được commit public.

## 10. Tiêu chí hoàn thành và các test cần có

Một module đủ để bàn giao khi: nhận input đúng contract, xử lý bằng implementation thật,
trả output validate được, đọc/ghi đúng dữ liệu, retry có hành vi xác định và có tests cho
cả kết quả rõ ràng lẫn chưa đủ dữ liệu. Chạy fixtures pass chỉ là một phần của tiêu chí này.

| BRD / điều cần chứng minh | Nhóm chính | Test nên có |
|---|---|---|
| BR-01/02/19, AC-01/09 | A | Upload mới; profile/chunks/citation raw và evidence đúng PDF |
| BR-03..06/24, AC-10 | B | Scope độc lập citations; biên thời gian; ambiguity/transition |
| BR-07/08 | B + C | Criterion retrieval đúng case; miss không trở thành VIOLATED |
| BR-09/10/13/16, AC-02..04/08 | C | Gates, grounding, UNKNOWN, deterministic aggregation, basis/version |
| BR-11/12/25, AC-05/11 | C + D | Risk XOR provenance, recommendations đúng mapping, report tách nhánh |
| BR-21, AC-12 | B + D | VALID lịch sử không bị STALE chỉ vì current status |
| BR-14/18, AC-06 | D + owner bước 8 | Review có quyền, before/after, lý do, report version mới |
| BR-15, AC-07 | D + tất cả | Hợp đồng mới chưa có trong seed chạy upload → hai nhánh → report |
| Phụ lục A.6/A.8 | D + writers | Duplicate job, worker restart, timeout/retry, tenant isolation |

Có thể demo dần: module riêng → handoff bằng fake upstream → DB integration →
full pipeline draft trên hợp đồng mới → review và report đã xác nhận khi bước 8 hoàn thành.

Tài liệu liên quan:

- [DB local, seed và cấu hình](local_database.md)
- [Contracts gốc v7.3.2](data_contracts_v7_3_2.md)
- [Cách nối interfaces/workflow hiện có](module_integration.md)
- [Tooling phát triển song song theo 5 người](parallel_development.md)
- [Kiến trúc folder hiện tại](architecture.md)
