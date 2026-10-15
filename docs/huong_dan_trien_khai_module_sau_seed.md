# Hướng dẫn phát triển từng module sau khi đã seed PostgreSQL local

Tài liệu dành cho các nhóm làm **bước 1–2**, **bước 3–4**, **bước 5–7** và **bước 9**.
Mục tiêu: mỗi nhóm mở repo, đọc đúng dữ liệu mẫu từ DB, viết phần của mình, test độc lập,
rồi bàn giao output có thể ghép với các nhóm khác.

Nguồn nghiệp vụ: `BRD_AI_Legal_Compliance_Checker_v1.1(5).pdf` người dùng cung cấp,
mục 6–8, tiêu chí nghiệm thu và phụ lục kiến trúc A.3–A.8 bổ sung ngày 13/10/2026.
Tên bảng/kiểu cột lấy từ migrations PostgreSQL đang có trong repo. Bộ
`v7.5.0-source-pdf360-r2-structured` giữ schema nghiệp vụ đã migrate từ `v7_4_9_RISK`.
Contract thực thi hiện tại lấy từ `backend/src/legal_checker/shared/contracts/`.
Phụ lục BRD có các API/kiến trúc đề xuất; những đề xuất đó chưa tự trở thành code đã chạy.

Dataset đang dùng: **v7.5.0-source-pdf360-r2-structured / supabase-public-v1**. Nhóm dev tải gói DEV_VALIDATION theo [hướng dẫn dataset](dataset_download.md), rồi seed vào DB riêng. Bộ chunks/citations tham chiếu được giải thích tại [r2 structured](v750_source_pdf360_r2_structured.md).

Các JOIN bên dưới dùng case/run r2: ví dụ `CA360_001` và `CA360_001_PDF360_LS2_REFERENCE`. Chọn IDs thực tế từ DB đã seed, giữ cùng knowledge hash và không trộn với IDs của dataset cũ.

**Trạng thái code:** bước 5–7 chỉ còn skeleton nội bộ; các POST chạy riêng module đã xóa. Các mô tả nghiệp vụ và JOIN là hướng dẫn để nhóm C tự triển khai. Dữ liệu seed/QA là references của release đã chốt. Các CLI placeholder đánh giá và công cụ rebuild release cũ đã xóa. [Trạng thái đầy đủ](architecture.md#trạng-thái-skeleton-bước-57).

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

Để bắt đầu viết repository, đọc [khóa JOIN/cách chạy SQL](#25-quy-ước-khóa-join-và-cách-chạy-sql-trong-tài-liệu)
và [cách đọc QA payload](#26-hai-nguồn-đọc-bảng-chuẩn-hóa-và-dto-tham-chiếu-trong-qa), rồi mở recipe của nhóm mình:

- [A — PDF/C01, profile, subjects, mốc, facts và citations](#46-recipe-đọcjoin-cho-nhóm-a-tách-pdf-input-khỏi-output-tham-chiếu)
- [B — scope, versions, citation metadata và retrieval targets](#56-recipe-đọcjoin-cho-nhóm-b-c02--c04--c05--c06-nhánh-c03--c09)
- [C — selected evidence, rules/basis, aggregation, risk và templates](#67-recipe-đọcjoin-cho-nhóm-c-từ-evidence-đến-findings-risks-và-actions)
- [D — run snapshots, lineage, report sections và review/version](#77-recipe-đọcjoin-cho-nhóm-d-chọn-run-rồi-đọc-từng-section)

## 1. Hiểu đúng phần đã có

### 1.1 DB đã giúp chúng ta điều gì?

Mỗi dev có PostgreSQL local riêng trên máy mình. Với bộ 360 PDF, dùng workbook
**DEV_VALIDATION** để seed, ví dụ đặt DB là `legal_checker_dev_v750_r2_supabase`:

| Schema | Chứa gì? | Ví dụ |
|---|---|---|
| `knowledge` | Luật, requirements, phiên bản, criteria, decision/risk rules, templates và quản trị knowledge | `tieu_chi_danh_gia`, `quy_tac_rui_ro` |
| `runtime` | Hợp đồng, profile, chunks, viện dẫn, ca đánh giá và các kết quả mẫu | `doan_hop_dong`, `yeu_cau_ap_dung`, `ket_qua_tieu_chi` |
| `qa` | Split, input/output tham chiếu và assertions kiểm thử | `case_manifest`, `artifacts`, `controlled_assertions` |
| `dev_meta` | Thông tin kỹ thuật của Alembic và seed | `alembic_version`, `seed_imports`; DB cũ giữ `schema_migrations` làm lịch sử |

Schema workbook có 50 bảng nghiệp vụ: 22 bảng `knowledge`, 28 bảng `runtime`;
các migrations còn bổ sung bảng snapshot/run/lineage và 6 bảng QA. Gói DEV_VALIDATION
có **240 DEV + 60 VALIDATION** và **32 ca regression riêng trong QA**. MASTER có 360
ca corpus; TEST_INPUTS có 60 ca chỉ PDF/intake. Không dùng số dòng của workbook cũ
để suy ra số dòng của bản mới. Phụ lục BRD chia bảng theo bốn **nhóm trách nhiệm**
(knowledge, runtime, quản trị, kỹ thuật); các bảng nghiệp vụ workbook nằm trong hai
schema `knowledge`/`runtime`, còn QA và metadata kỹ thuật có schema riêng như bảng trên.
Schema là nhóm bảng trong cùng PostgreSQL DB, không bắt buộc tách thành nhiều databases.

Ví dụ: người làm bước 5 có thể đọc profile/chunks/C05/kết quả retrieval mẫu trong DB
để phát triển, dù người làm bước 2 và bước 4 chưa hoàn thành implementation thật.
Khi ghép hệ thống, input đó được thay bằng output thật của các bước trước.

### 1.2 Những phần code nào đã có?

| Phần | Hiện trạng | Dev tiếp tục làm gì? |
|---|---|---|
| PostgreSQL local | Có server setup, migration 50 bảng, seed và integration tests | Dùng DB riêng; bổ sung query của module |
| Knowledge SQL | Có full `Knowledge` SQL reader/snapshots và helper `WorkbookKnowledgeRepository` | Dùng reader đã chọn snapshot; mở rộng policies cần thiết |
| Retrieval SQL | Có `RetrievalDatasetRepository` lấy source rows theo case/run | Map DTO; triển khai index/search/rerank và writer |
| Bước 1–4 | Có interfaces/DTOs và skeleton files | Triển khai intake, parser/OCR, extraction, scope, temporal, citation, retrieval |
| Bước 5–7 | Chỉ có skeleton và contracts; implementation cũ đã xóa | Triển khai toàn bộ mapper/reasoning/grounding/aggregation/risk/recommendation; Store dùng chung đã có |
| Workflow | Có `DraftAssessmentWorkflow` để nối implementations được inject | Ghép implementations thật; bổ sung orchestration/persistence/recovery |
| Bước 9 | Có `build_draft_report` tạo C13 draft từ handoffs cũ | Đọc DB, ghép report, lưu version, export, API và UI |
| Bước 8 | Có C12 và interfaces review | Bổ sung review thật hoặc giữ báo cáo draft khi chưa có review |

**Không có API POST chạy riêng bước 5–7.** Snapshot knowledge và run lịch sử nằm trong DB.
Cấu hình bằng `DATABASE_URL`, optional `KNOWLEDGE_SNAPSHOT_SHA256` để pin snapshot cũ.
Mapper các bước upstream, OCR/search/LLM/review/export vẫn cần implementations thật.

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
Hướng dẫn này nhóm theo bước; nếu chia 5 người thì giữ ranh giới trên.

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

Cấu hình local đã dùng: host `127.0.0.1`, port `5433`, user `legal_checker`,
password local `legal_checker_local_only`. Chọn đúng DB bằng `DATABASE_URL`; tên mặc định
`legal_checker_dev_v750_r2_supabase` được đặt trong `.env.example`. Cách seed bộ hiện tại xem
[hướng dẫn DB](local_database.md#3-tạo-bảng-kiểm-tra-và-seed).
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

Một cặp trong bộ 360 PDF đã kiểm tra:
`ca_id = 'CA360_001'`, `lan_chay_id = 'CA360_001_PDF360_LS2_REFERENCE'`.
Đây là ca mẫu đọc dữ liệu, không phải ca mới do module của bạn đã xử lý.

Mỗi người ghi lại ít nhất: `ca_id`, `hop_dong_id`, `tenant_id`, `lan_chay_id`,
`phien_ban_id`, `rule_version`, `legal_knowledge_version`.
Khi chạy implementation thật, tạo case/run của dev riêng để giữ baseline mẫu.

### 2.3 Seed là dữ liệu mẫu, chưa phải bộ contract hoàn chỉnh

Một dòng SQL có thể chứa nhiều cột audit hơn DTO, hoặc thiếu trường DTO cần.
Vì vậy, `SELECT *` rồi đưa cả row vào Pydantic thường không đúng.
Phải có mapper chọn trường, đổi tên/kiểu và xử lý dữ liệu chưa đủ.

Trong bộ cũ, từng có retrieval rows thiếu `tieu_chi_id`; không áp dụng nhận xét đó
cho toàn bộ bộ 360 PDF mới. C06 mới có liên kết per-criterion và DTO tham chiếu trong QA.
Vẫn phải kiểm tra ownership, criterion/version, selected flag và run khi đọc. Nếu dùng
bộ cũ hoặc gặp NULL, giữ row như candidate chưa map được; không gán criterion tùy ý.

Dữ liệu `SYNTHETIC_DEMO`, `AI_DRAFT`, các cờ chưa human-verified giữ nguyên ý nghĩa.
Seed thành công chứng minh dữ liệu nhập được vào SQL; không chứng minh parser/OCR,
retrieval hay LLM đã xử lý đúng hợp đồng.

### 2.4 Trước mỗi query: chốt case, run và vai trò dữ liệu

**Một cách hiểu đơn giản:** DB seed chứa một dây chuyền đã có sẵn các sản phẩm mẫu.
Bạn lấy sản phẩm mẫu của công đoạn trước để viết công đoạn của mình. Sản phẩm mẫu
của chính công đoạn mình chỉ được dùng để đối chiếu sau khi chạy.

| Đang phát triển | Input có thể đọc từ seed để làm độc lập | Output tham chiếu để đối chiếu sau khi chạy |
|---|---|---|
| Bước 1–2 | C01 + bytes PDF | C02, chunks, C03 |
| Scope 3A.1 | C02 + catalog phạm vi | C04 |
| Temporal 3A.2 | C02/mốc + C04 + versions | C05 |
| Citation 3B | C03 + C02/mốc + metadata luật | C09 |
| Retrieval 4 | C05 + chunks + criteria | C06 |
| Reasoning 5 | C05 + C06 + chunks/facts + knowledge | C07; C08 để kiểm tra aggregation |
| Risk 6 | C07 + C09 + risk rules | C10 |
| Recommendation 7 | C10 + C05/context + templates | C11 |
| Report 9 | C01–C11 và C12 nếu có thật | C13 draft |

Khi test riêng Aggregator của bước 5, C07 seed được phép là input để tạo C08.
Khi test cả Reasoning + Aggregation, C07/C08 seed là expected, không phải input.
`qa.artifacts.role='EXPECTED'` là vai trò trong **pipeline tham chiếu**, nên C05 EXPECTED
vẫn có thể làm fake upstream cho người phát triển Retrieval. Quyền sử dụng phụ thuộc
module đang test; không gửi expected của chính module đó vào prompt.

Chọn một ca DEV, PDF chính và run tham chiếu bằng query dưới đây:

```sql
-- Q00_CASE: đọc danh sách để chọn; không cần parameters.
SELECT m.case_id, m.split, m.group_id, ca.hop_dong_id, ca.tenant_id,
       ca.phien_ban_id, ca.rule_version, ca.legal_knowledge_version,
       m.knowledge_snapshot_sha256, t.tep_id, t.object_uri, t.sha256,
       ARRAY(SELECT DISTINCT k.lan_chay_id
             FROM runtime.ket_qua_tieu_chi k
             WHERE k.ca_id=ca.ca_id ORDER BY k.lan_chay_id) AS runs_co_c07
FROM qa.case_manifest m
JOIN runtime.ca_danh_gia ca ON ca.ca_id=m.case_id
JOIN runtime.hop_dong h ON h.hop_dong_id=ca.hop_dong_id
JOIN runtime.tep_nguon t
  ON t.tep_id=h.tep_nguon_id AND t.hop_dong_id=h.hop_dong_id
WHERE m.case_kind='CORPUS' AND m.split='DEV'
ORDER BY m.case_id;
```

`runs_co_c07` có thể gồm reference và run bạn chạy sau này. Chọn rõ một run;
không lấy `MAX(lan_chay_id)` vì thứ tự chữ không biểu diễn thời gian.
Không hardcode CA360_001 cho mọi bộ seed; dùng case thực sự có trong DB của bạn.

### 2.5 Quy ước khóa JOIN và cách chạy SQL trong tài liệu

| Khóa | Đại diện cho | Dùng khi nào? |
|---|---|---|
| `hop_dong_id` | Một tài liệu/hợp đồng | Profile, subjects, facts, chunks, C03, mốc |
| `ca_id` | Một lần/hồ sơ đánh giá với pin | Checklist, findings, report, quyền |
| `yeu_cau_ca_id` | Một requirement thuộc một case | C05 → retrieval → C07 → C08 |
| `requirement_id` | Family nghĩa vụ pháp lý | Scope → các versions; không trực tiếp chọn criteria |
| `requirement_version_id` | Phiên bản family đã chọn | C05 → đúng tập criteria và basis |
| `tieu_chi_id` | Criterion trong một version | C06/C07 và decision/risk rules |
| `doan_id` | Chunk nguồn | Evidence/facts/citation/retrieval; kiểm tra thêm hợp đồng |
| `lan_chay_id` / `run_id` | Lần chạy module/workflow | C06/C07/C09; input/output snapshots, lineage |
| `ket_qua_id` ở C07 | Một finding criterion | Evidence C07, nguồn compliance của C10 |
| `finding_id` ở C09 | Một finding citation | Nguồn citation của C10 |
| `ket_qua_id` ở C10 | Một risk instance | C11 qua `ket_qua_rui_ro_id`; khác ID C07 |

**Không JOIN chỉ theo tên gần giống hoặc theo `ca_id` ở tất cả các bảng.** Ví dụ một case
có nhiều criteria và nhiều citations; JOIN chúng qua case sẽ tạo tích số dòng, không tạo
liên kết nghiệp vụ. Liên kết của risk phải theo finding nguồn.

Các query mới bên dưới dùng **named parameters của psycopg**:
`%(case_id)s`, `%(run_id)s`, `%(criterion_id)s`, `%(knowledge_sha)s`.
Chạy từ root repo, venv đã cài backend, dùng mẫu Python này:

```python
import os
from dotenv import load_dotenv
from legal_checker.core.postgres import connect_postgres

load_dotenv(".env")
params = {
    "case_id": "CA360_001",
    "run_id": "CA360_001_PDF360_LS2_REFERENCE",  # Khi đọc baseline.
}
sql_text = """
SELECT * FROM runtime.yeu_cau_ap_dung
WHERE ca_id=%(case_id)s ORDER BY yeu_cau_ca_id
"""
with connect_postgres(os.environ["DATABASE_URL"]) as connection:
    rows = connection.execute(sql_text, params).fetchall()
print(len(rows))
```

Copy query ở đúng mục vào `sql_text`. Nếu chạy trong DBeaver/pgAdmin, thay placeholder
bằng literal của ca mẫu, ví dụ `%(case_id)s` → `'CA360_001'`; cú pháp placeholder này
không phải cú pháp PostgreSQL chạy trực tiếp. Trong code ứng dụng luôn bind parameters.
Các query là ví dụ repository sau khi đã kiểm tra quyền; không tự là lớp authorization.

Quy tắc chung khi map:

1. Chọn case được phép đọc và pin; xác định contract ID từ case.
2. Đọc từng tập 1:N riêng: subjects, facts, citations, criteria…
3. JOIN evidence về đúng parent; dùng `LEFT JOIN` để giữ parent chưa có evidence/version.
4. Nhóm rows theo PK parent; ví dụ 3 quotes vẫn là **1 fact với 3 evidence**, không phải 3 facts.
5. Map rõ tên/kiểu/null/status, validate DTO rồi kiểm tra ownership/gates.

### 2.6 Hai nguồn đọc: bảng chuẩn hóa và DTO tham chiếu trong QA

**Bảng chuẩn hóa** cho bạn luyện repository, kiểm tra FK và truy vết từng dòng.
**QA artifacts** cung cấp payload đã dựng theo contract, giúp viết logic trước khi mapper
SQL hoàn thành. Cả hai đều nằm trong DB. Chúng không thay thế output thật của module.

```sql
-- Q01_QA: xem payload nào có sẵn; mỗi payload có thể bị chia nhiều phần.
SELECT role, contract_name, record_id, count(*) AS so_parts,
       max(part_count) AS part_count
FROM qa.artifacts WHERE case_id=%(case_id)s
GROUP BY role, contract_name, record_id
ORDER BY role, contract_name, record_id;
```

Đọc full payload bằng helper đang có; không parse JSON từng ô `content` riêng:

```python
from devtools.qa_validation import join_artifacts
from legal_checker.core.postgres import connect_postgres
from legal_checker.shared.contracts.document_intelligence import DocumentIntelligenceResult


def load_reference(database_url, case_id, role, contract_name):
    with connect_postgres(database_url) as connection:
        rows = connection.execute(
            """SELECT * FROM qa.artifacts
               WHERE case_id=%s AND role=%s AND contract_name=%s""",
            (case_id, role, contract_name),
        ).fetchall()
    payloads = join_artifacts(rows)  # Sort parts, kiểm tra đủ phần và SHA256, rồi parse JSON.
    if len(payloads) != 1:
        raise ValueError("Cần đúng một payload; kiểm tra case/role/contract/record_id")
    return next(iter(payloads.values()))


# Nhóm B có thể dùng đây làm fake C02/chunks/C03 của nhóm A trong DEV.
raw = load_reference(database_url, case_id, "EXPECTED", "DocumentIntelligenceResult")
document = DocumentIntelligenceResult.model_validate(raw)
```

Ở đoạn cuối, `database_url` và `case_id` lấy từ cấu hình/ca đã chọn như mục 2.5.
Bộ 360 dùng tên artifact `C02`, `C03`, …, `C13`, `DocumentIntelligenceResult`,
`PipelineRequest`, `PipelineResponse`, `DocumentInput`. R2 còn có `DocumentStructure`
cho parents/chunk paths/source ranges/layout/internal links; đây là QA artifact bổ sung,
không phải một contract nghiệp vụ mới. `C02` là ContractProfile;
`DocumentIntelligenceResult` còn có chunks/C03. `PipelineRequest` có cả observations
tham chiếu; chỉ dùng nguyên payload này cho replay deterministic, không dùng observations
tham chiếu để chấm khả năng reasoner/LLM tự suy luận.

Với run dev đã lưu bằng Store, đọc `assessment_runs`/`assessment_output_lineage` như mục
7.7, thay vì lấy QA expected làm output mới. Seed workbook chưa tự tạo các run dev đó.

### 2.7 Knowledge phải khớp snapshot của lần chạy

Các query `knowledge.*` bên dưới giúp xem/join **catalog hiện tại**. Khi đánh giá lịch sử,
catalog có thể đã đổi. Dùng `Knowledge(database_url, snapshot_sha256=...)` từ pin của
input/run để tránh dùng luật/rules hiện tại cho kết quả quá khứ.

**Lưu ý sau khi seed DB mới:** seeder nhập các bảng knowledge và QA, nhưng không tự
capture mọi `knowledge_snapshots`. Trên DB DEV vừa seed, bảng snapshot có thể còn rỗng.
Chuẩn bị snapshot một lần trước khi chạy engine với hash pin:

```python
from legal_checker.modules.legal_knowledge.repository import Knowledge

# expected_sha đọc từ qa.case_manifest của case/reference đã chọn.
# Đây là bước setup: capture catalog hiện tại vào DB, không sửa cờ duyệt pháp luật.
current = Knowledge(database_url)
if current.sha256 != expected_sha:
    raise ValueError("Knowledge hiện tại khác release của ca; không đổi pin để ép chạy")
knowledge = Knowledge(database_url, snapshot_sha256=expected_sha)
```

Nếu DB đã có snapshot được pin thì đọc trực tiếp. Nếu catalog đã thay đổi và snapshot cũ
chưa có, cần khôi phục/import đúng release đó vào DB phù hợp; không coi snapshot mới là cũ.

```python
from legal_checker.modules.legal_knowledge.repository import Knowledge

knowledge = Knowledge(database_url, snapshot_sha256=knowledge_sha)
criteria = knowledge.criteria_for(requirement_version_id)
# knowledge.versions / .articles / .documents / .tables giữ cùng snapshot.
```

`knowledge_sha` lấy từ Context/input snapshot (hoặc manifest để đọc reference), không
phải SHA256 Excel/PDF. Query kiểm tra snapshot và cách xem criteria của snapshot:

```sql
-- Q02_SNAPSHOT: params thêm knowledge_sha từ pin đã chọn.
SELECT s.sha256, s.review_status, item AS criterion
FROM knowledge.knowledge_snapshots s
CROSS JOIN LATERAL jsonb_array_elements(s.content->'tables'->'tieu_chi_danh_gia') item
WHERE s.sha256=%(knowledge_sha)s
  AND item->>'tieu_chi_id'=%(criterion_id)s;
```

Không có snapshot đó thì báo lỗi/chọn release hợp lệ; không gắn dữ liệu mới vào hash cũ.

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
Connection dùng chung ở `core/postgres.py`. SDK/client/provider do từng module sở hữu; `shared/llm/` chỉ giữ audit X02 thống nhất.
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
        ("CA360_001",),
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
Có thể dùng `shared/ids.py` để tạo ID ổn định cho implementation mới.
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
WHERE a.ca_id = 'CA360_001'
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
WHERE f.ca_id = 'CA360_001'
  AND f.lan_chay_id = 'CA360_001_PDF360_LS2_REFERENCE'
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
inputs = repository.load_input_rows("CA360_001")
candidates = repository.load_seeded_evidence("CA360_001", "CA360_001_PDF360_LS2_REFERENCE")
print(len(inputs["requirements"]), len(inputs["chunks"]), len(candidates))
```

`candidates` là rows mẫu, cần map/validate C06; với bộ 360 đã có criterion ID.
Khi chạy Retrieval thật, module của bạn phải tự tìm/chọn evidence per-criterion.
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
pytest -q -c backend/pyproject.toml backend/tests/contract/test_db_handoffs.py -k legal
pytest -q -c backend/pyproject.toml backend/tests/contract/test_db_handoffs.py -k retrieval
```

Đây là tests DB handoff/provenance; bổ sung query/mapping riêng của implementation và eval.
Bàn giao C04/C05 cho Retrieval/Compliance, C09 cho Risk/Report, C06 cho Compliance.

### 5.6 Recipe đọc/join cho nhóm B: C02 → C04 → C05 → C06, nhánh C03 → C09

#### B1 — Scope: đọc profile trước, JOIN family với điều kiện phạm vi

**Input upstream:** C02 của nhóm A. Khi dev riêng, đọc Q11–Q14 hoặc C02 QA; không đọc
`yeu_cau_ap_dung.scope_status` để trả chính trạng thái Scope của implementation mình.

```sql
-- Q20_SCOPE_CATALOG: family → N scope clauses; chưa chọn version/criterion.
SELECT r.requirement_id, r.ten_nhom_yeu_cau, r.nhom_nghia_vu, r.che_do_ket_hop,
       s.pham_vi_id, s.nhom_phien_ban, s.loai_hop_dong_id,
       s.doi_tuong, s.loai_chu_the, s.linh_vuc,
       s.dieu_kien_scope, s.dieu_kien_json, s.trang_thai,
       l.ten_loai, l.loai_cha_id
FROM knowledge.yeu_cau_phap_ly r
LEFT JOIN knowledge.pham_vi_ap_dung s ON s.requirement_id=r.requirement_id
LEFT JOIN knowledge.loai_hop_dong l ON l.loai_hop_dong_id=s.loai_hop_dong_id
ORDER BY r.requirement_id, s.pham_vi_id;
```

Vì UNKNOWN loại hợp đồng vẫn cần được xử lý, ví dụ đọc catalog trước rồi interpreter
đánh giá trên C02. Nếu tối ưu query theo loại/subtype, phải xét scope tổng quát, loại cha
và nhóm chưa đủ facts; không lọc mất chúng chỉ vì giá trị profile NULL. Nhiều scope clauses
của một family cần đọc `che_do_ket_hop`/policy để quyết định AND/OR, không coi mỗi row là
một requirement độc lập. Với dataset 360, adapter tham chiếu chỉ xét 10 families;
module thật cần khai báo phạm vi catalog được hỗ trợ, không tự hiểu đó là toàn bộ luật.

**Output:** C04 giữ `requirement_id`, group, trạng thái và lý do/predicate/profile snapshot.
Sinh `yeu_cau_ca_id` ổn định cho family thuộc case. Ghi phần scope của `yeu_cau_ap_dung`.
Temporal tiếp tục trên chính IDs/checklist này. Không JOIN citations để tạo checklist.

#### B2 — Temporal: từ C04 lấy tất cả candidate versions và đúng mốc

Q13_MARKERS là output DI cung cấp các mốc. Với một C04, JOIN bằng **requirement_id**
để xem candidates; `requirement_version_id` là kết quả của resolver, chưa có từ đầu.

```sql
-- Q21_VERSION_CANDIDATES: a là C04 đã lưu của run/checklist đang chọn.
SELECT a.yeu_cau_ca_id, a.requirement_id, a.nhom_phien_ban AS scope_group,
       a.scope_status, v.requirement_version_id, v.nhom_phien_ban AS version_group,
       v.hieu_luc_tu, v.hieu_luc_den, v.loai_moc_ap_dung,
       v.quy_tac_chuyen_tiep, v.dieu_kien_ap_dung, v.trang_thai_runtime,
       v.can_xac_minh_scope, v.can_xac_minh_chuyen_tiep,
       vb.van_ban_id, vb.so_hieu, vb.trang_thai_xac_minh
FROM runtime.yeu_cau_ap_dung a
LEFT JOIN knowledge.phien_ban_yeu_cau v ON v.requirement_id=a.requirement_id
LEFT JOIN knowledge.van_ban_phap_ly vb ON vb.van_ban_id=v.source_van_ban_id
WHERE a.ca_id=%(case_id)s
ORDER BY a.yeu_cau_ca_id, v.hieu_luc_tu, v.requirement_version_id;
```

Query trả candidates, **không tự giải quyết version**. Service phải:

1. Giữ group/phạm vi từ C04; đọc loại mốc và policy của candidate.
2. Chọn ngày có provenance tương ứng từ C02; nếu ngày NULL thì giữ UNKNOWN.
3. Kiểm tra interval, amendment/replacement, transition và ngoại lệ.
4. Nếu nhiều candidates còn hợp lệ/chưa rõ ưu tiên, giữ UNKNOWN + lý do; không `LIMIT 1`.
5. Trả C05 với version đã chọn hoặc candidate giữ rõ là chưa resolve.

Nếu C04 đang ở memory, gọi `knowledge.versions` theo IDs của C04; query Q21 chỉ là cách
đọc các rows đã lưu trong DB. `yeu_cau_ap_dung` không có run column; khi thay checklist,
tạo case/checklist version phù hợp hoặc dùng snapshot đã pin, không ghi đè baseline.

Nguồn/version và ngoại lệ đọc thành tập riêng để không nhân dòng:

```sql
-- Q22_VERSION_BASIS: 1 version → N nguồn/điều khoản. Thêm param version_id.
SELECT v.requirement_version_id, v.requirement_id, v.noi_dung,
       n.lien_ket_id, n.vai_tro, n.vi_tri_cu_the,
       d.dieu_khoan_id, d.vi_tri, d.noi_dung_nguon, d.trang_thai_xac_minh,
       vb.van_ban_id, vb.so_hieu, vb.url_nguon
FROM knowledge.phien_ban_yeu_cau v
LEFT JOIN knowledge.nguon_yeu_cau n ON n.requirement_version_id=v.requirement_version_id
LEFT JOIN knowledge.dieu_khoan_phap_ly d ON d.dieu_khoan_id=n.dieu_khoan_id
LEFT JOIN knowledge.van_ban_phap_ly vb ON vb.van_ban_id=d.van_ban_id
WHERE v.requirement_version_id=%(version_id)s
ORDER BY n.lien_ket_id;
```

`v.dieu_khoan_id`/`source_van_ban_id` còn là basis trực tiếp của version; đọc cả basis này
và quan hệ `nguon_yeu_cau` theo policy. Ngoại lệ lấy ở Q34 dưới đây. Candidate hay row có
nguồn không tự là source_verified/human-approved.

#### B3 — Citation: C03 → candidate legal identity → C09

**Input upstream:** C03/Q15, C02/mốc/Q13. C09 seed chỉ dùng để kiểm tra writer/mapping
hoặc đối chiếu sau classifier. Một citation có thể chưa có số hiệu hoặc tên đầy đủ.

```sql
-- Q23_IDENTITY_CANDIDATES: chuẩn hóa số hiệu trong code rồi bind normalized_number.
SELECT vb.van_ban_id, vb.so_hieu, vb.so_hieu_chuan, vb.ten_van_ban,
       vb.linh_vuc, vb.hieu_luc_tu, vb.hieu_luc_den, vb.van_ban_thay_the_id,
       vb.identity_verified, vb.temporal_verified, vb.domain_verified,
       vb.trang_thai_xac_minh,
       s.nguon_id, s.url, s.duong_dan, s.sha256, s.trang_thai AS source_status
FROM knowledge.van_ban_phap_ly vb
LEFT JOIN knowledge.nguon_phap_ly s ON s.van_ban_id=vb.van_ban_id
WHERE vb.so_hieu_chuan=%(normalized_number)s OR vb.so_hieu=%(normalized_number)s
ORDER BY vb.van_ban_id, s.nguon_id;
```

Số hiệu khớp là **candidate định danh**, chưa là VALID. Nhóm theo `van_ban_id` (mỗi văn bản
có thể nhiều nguồn), đối chiếu tên/loại/ngày, rồi đọc quan hệ thay thế/sửa đổi:

```sql
-- Q24_LEGAL_RELATIONS: thêm param document_id của candidate đã chọn.
SELECT * FROM knowledge.quan_he_van_ban
WHERE van_ban_nguon_id=%(document_id)s OR van_ban_dich_id=%(document_id)s
ORDER BY moc_hieu_luc, quan_he_id;
```

Nếu số hiệu chưa rõ, thêm candidate search theo tên/context trong module; không tự sửa
OCR để ép Q23 có kết quả. Không dùng Q24 như bằng chứng sửa đổi toàn bộ văn bản khi quan
hệ chỉ ảnh hưởng một phạm vi. C09 giữ relevant/current status riêng, nguồn evidence và run.

#### B4 — Retrieval: requirement instance → version → criteria; chunks đọc riêng

**Input upstream:** C05 của Temporal + chunks của DI. Đọc Q25 để dựng danh sách targets:

```sql
-- Q25_RETRIEVAL_TARGETS: giữ cả unresolved requirements khi LEFT JOIN chưa có criteria.
SELECT a.yeu_cau_ca_id, a.requirement_id, a.requirement_version_id,
       a.scope_status, a.version_status, a.applicability_status, a.moc_ap_dung,
       v.noi_dung AS requirement_text,
       c.tieu_chi_id, c.thu_tu, c.noi_dung AS criterion_text,
       c.bang_chung_can_thiet, c.loai_kiem_tra, c.pham_vi_kiem_tra,
       c.noi_dung_bat_buoc_trong_hd
FROM runtime.yeu_cau_ap_dung a
LEFT JOIN knowledge.phien_ban_yeu_cau v
  ON v.requirement_version_id=a.requirement_version_id AND v.requirement_id=a.requirement_id
LEFT JOIN knowledge.tieu_chi_danh_gia c ON c.requirement_version_id=v.requirement_version_id
WHERE a.ca_id=%(case_id)s
ORDER BY a.yeu_cau_ca_id, c.thu_tu, c.tieu_chi_id;
```

```sql
-- Q26_CHUNKS: toàn bộ chunks đúng contract; không cần có citation hoặc evidence sẵn.
SELECT d.doan_id, d.hop_dong_id, d.section_path, d.page_start, d.page_end,
       d.noi_dung, d.chunk_quality, d.sha256_text, d.phien_ban_chunk, d.thu_tu
FROM runtime.ca_danh_gia ca
JOIN runtime.doan_hop_dong d ON d.hop_dong_id=ca.hop_dong_id
WHERE ca.ca_id=%(case_id)s ORDER BY d.thu_tu, d.doan_id;
```

Map Q25 → C05/target criteria, Q26 → `Chunk[]`, dựng `RetrievalInput(context, hop_dong_id,
requirements, chunks)`. Criteria/catalog inject qua Knowledge. **Không JOIN mọi target
với mọi chunk trong SQL để gửi hàng nghìn dòng trùng text**; index chunks một lần rồi
search/rerank theo từng criterion. NOT_APPLICABLE bỏ search có lý do; UNKNOWN vẫn giữ
trạng thái trong C05, candidate version chưa được coi là resolved chỉ vì có criteria.

C06 không chứa quote/offset; nó chỉ định chunk, scores/rank/stage/model/run. Quote được
reasoner chọn và kiểm chứng khi tạo C07. Nếu không tìm thấy selected evidence, C06 có thể
rỗng cho target nhưng cần checkpoint/coverage của lần retrieval để phân biệt chưa chạy
với chạy rồi không tìm thấy; một bảng evidence rỗng tự nó không phân biệt được hai việc.

**Nơi ghi và bên dùng tiếp:** Scope/Temporal → `yeu_cau_ap_dung` (C04/C05), Citation →
`phat_hien_vien_dan` (C09), Retrieval → `ket_qua_truy_xuat` (C06). Nhóm C lấy C05/C06 cho
bước 5 và C09 cho bước 6; nhóm D lấy cả hai nhánh. Writer upstream và checkpoint thật
vẫn cần triển khai, các query trên không tự tạo chúng.

## 6. Nhóm C: bước 5–7: Compliance, Risk và Recommendation

### 6.1 Việc nên làm đầu tiên

Logic bước 5–7 chưa triển khai. Các thành phần DB dùng chung đã có:

1. `modules/legal_knowledge/repository.py:Knowledge(database_url, snapshot_sha256=None)`
   đáp ứng `KnowledgeSnapshot`, đọc 18 bảng nghiệp vụ và freeze nội dung trong DB.
2. `WorkbookKnowledgeRepository` vẫn là helper query, không phải full snapshot reader.
3. `modules/assessments/repository.py:Store(database_url)` lưu normalized outputs,
   case/run pins, toàn bộ input/output và DTO lineage của bước 5–7.

Nhóm C cần triển khai mapper C05/C06/chunks/facts, observations/provider và toàn bộ logic bước 5–7.
Nạp JSONB rule được reader chuẩn hóa tại boundary cho implementation mới;
không thực thi chuỗi bằng eval. Hash lấy từ nội dung snapshot, không mượn hash workbook.
Cờ draft/unverified giữ nguyên; snapshot capture không phải phê duyệt chuyên gia.

Nếu muốn replay knowledge cũ, truyền hash snapshot đã có trong DB. Đổi source tables
không đổi reader đã khởi tạo; reader mới capture snapshot mới có hash tương ứng.

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

Ví dụ query evidence đã chọn; nếu dùng bộ cũ thì kiểm tra criterion ID thiếu:

```sql
SELECT r.truy_xuat_id, a.yeu_cau_ca_id, a.requirement_version_id,
       r.tieu_chi_id, r.doan_id, r.thu_hang, d.noi_dung
FROM runtime.ket_qua_truy_xuat r
JOIN runtime.yeu_cau_ap_dung a USING (yeu_cau_ca_id)
JOIN runtime.ca_danh_gia ca USING (ca_id)
JOIN runtime.doan_hop_dong d
  ON d.doan_id = r.doan_id AND d.hop_dong_id = ca.hop_dong_id
WHERE ca.ca_id = 'CA360_001'
  AND r.lan_chay_id = 'CA360_001_PDF360_LS2_REFERENCE'
  AND r.duoc_chon IS TRUE AND r.giai_doan = 'FINAL'
ORDER BY a.yeu_cau_ca_id, r.thu_hang, r.truy_xuat_id;
```

Quote check thực thi theo text chunk:

```python
assert chunk.noi_dung[evidence.ky_tu_bat_dau : evidence.ky_tu_ket_thuc] == evidence.trich_dan
```

`chunk`/`evidence` trong ví dụ là DTO đã dựng. Offset là vị trí ký tự trong text chunk,
không phải byte PDF hoặc vị trí trên text đã bị chuẩn hóa khác.

#### Điểm đặt implementation mới (hiện chỉ là skeleton)

```text
modules/compliance/observations.py             Interface cung cấp Observation
modules/compliance/criterion_reasoner.py       Triển khai kiểm tra số liệu/nội dung ở đây hoặc helper do nhóm C bổ sung
modules/compliance/criterion_reasoner.py       reason(request, knowledge) → C07
modules/compliance/requirement_aggregator.py   aggregate(context, knowledge, C07, C05) → C08
modules/compliance/grounding_validator.py      Kiểm tra handoff/provenance
```

Policy `AGG_CAN_HO_V1` trong knowledge để nhóm C triển khai: chưa confirmed/thiếu rule/thiếu findings → INSUFFICIENT;
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
3. Triển khai template engine để tạo nội dung cơ bản. Nếu bổ sung LLM, chỉ cá thể hóa
   câu chữ từ facts/basis đã có; không tự tạo luật, ngày, số tiền hoặc danh tính.
4. UNKNOWN/chưa đủ căn cứ → yêu cầu xác minh đúng dữ kiện còn thiếu.
5. Validate C11: cùng risk ID, legal basis/evidence, template và knowledge/rule version.
6. Lưu nội dung, action, priority và snapshots; giữ review PENDING.

`Recommendation.model_version` hiện bị giới hạn `TEMPLATE_ENGINE_NO_LLM`,
`prompt_version` là `NOT_USED`; validator nghiệp vụ mới cần được nhóm C triển khai theo contract.
Muốn có LLM-generated C11 cần cập nhật contract/version/validator/tests có chủ đích;
không ghi output LLM nhưng để metadata “NO_LLM”.

#### Hai entrypoint dự kiến cần phân biệt (hiện đều là skeleton)

- `evaluate_compliance` trong `compliance/service.py` dự kiến phục vụ handoff **người 4 cũ**:
  C07/C08 + risks/actions chỉ từ compliance. `ComplianceOutput` không nhận citation-sourced risks.
- `workflows/steps_5_7.evaluate` dự kiến nhận cả C09 và hợp nhất hai nhánh để trả C07–C11 đầy đủ.

Nếu nhóm C hiện phụ trách toàn bộ 5–7, dùng luồng đầy đủ. Nhóm D lấy C10/C11 đã hợp nhất
để làm report; không tạo lại citation risks/recommendations một lần nữa.

### 6.5 LLM và audit: khi nào cần?

Không bắt buộc LLM cho mọi criterion. Rule số liệu, aggregation và risk mapping có thể
chạy deterministic; LLM phù hợp extraction fallback, semantic reasoning và viết khuyến nghị.
Client LLM do từng module cấu hình; placeholder client chung đã xóa. `shared/llm/audit.py` có `audit_llm_call` và `PostgresLlmAuditSink` để ghi X02. [Ví dụ dùng audit](llm_audit.md).

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
pytest -q -c backend/pyproject.toml backend/tests/contract/test_db_handoffs.py -k compliance
```

Tests dùng SQL seed nhỏ trên DB test; thêm eval độc lập với workbook corpus cho implementation mới.
Bàn giao C07/C08/C10/C11, knowledge adapter, observations/provider,
mapper/writer và các test chứng minh lineage/grounding.

### 6.7 Recipe đọc/join cho nhóm C: từ evidence đến findings, risks và actions

#### C1 — Bước 5: lấy C05 và C06 đúng criterion/version/run

**Output upstream cần đọc:** `yeu_cau_ap_dung` là C05 của Temporal; `ket_qua_truy_xuat`
là C06 của Retrieval; `doan_hop_dong`/facts là output DI. Q25/Q26 là hai tập đầu tiên.
Sau đó đọc selected evidence:

```sql
-- Q30_SELECTED_RETRIEVAL: selected C06 + nguồn text + xác nhận criterion đúng version.
SELECT r.*, a.ca_id, a.requirement_version_id,
       d.hop_dong_id, d.noi_dung AS chunk_text, d.page_start, d.page_end,
       c.noi_dung AS criterion_text
FROM runtime.ket_qua_truy_xuat r
JOIN runtime.yeu_cau_ap_dung a ON a.yeu_cau_ca_id=r.yeu_cau_ca_id
JOIN runtime.ca_danh_gia ca ON ca.ca_id=a.ca_id
JOIN runtime.doan_hop_dong d
  ON d.doan_id=r.doan_id AND d.hop_dong_id=ca.hop_dong_id
JOIN knowledge.tieu_chi_danh_gia c
  ON c.tieu_chi_id=r.tieu_chi_id AND c.requirement_version_id=a.requirement_version_id
WHERE a.ca_id=%(case_id)s AND r.lan_chay_id=%(run_id)s
  AND r.duoc_chon IS TRUE AND r.giai_doan='FINAL'
ORDER BY a.yeu_cau_ca_id, r.tieu_chi_id, r.thu_hang, r.truy_xuat_id;
```

Q30 là query truy vết vào catalog hiện tại; khi dùng snapshot lịch sử, đọc rows C06/chunks
từ runtime nhưng đối chiếu criterion/version bằng Knowledge đã pin. JOIN catalog hiện tại
không được âm thầm loại finding hợp lệ của snapshot cũ. Dùng Q48 kiểm tra rows sai trước
khi tin vào danh sách đã được JOIN lọc. Chỉ JOIN thành công chưa chứng minh relevance.

Map row C06:

| DTO field | SQL nguồn |
|---|---|
| IDs, stage, rank, selected, query/version/model/run | Cột tương ứng của `r` |
| `scores` | Dict gồm `bm25_score`, `vector_score`, `rerank_score`; Decimal → float/None |
| Text | Không đưa vào C06; dựng `Chunk` riêng từ Q26, tra bằng `doan_id` |

Giữ C05 **đầy đủ**, kể cả UNKNOWN/NOT_APPLICABLE. Query selected evidence không có row
cho một criterion thì gán **list evidence rỗng cho target đó**, không xóa criterion khỏi
input chỉ vì INNER JOIN không có evidence.

#### C2 — Criterion cần rules, basis, ngoại lệ và facts nào?

Từ version của C05, `knowledge.criteria_for(version_id)` trả criteria đúng snapshot.
Chọn một criterion để viết logic trước; thêm `criterion_id` vào parameters.

```sql
-- Q31_CRITERION_RULES: 1 criterion → N decision rules; đọc riêng khỏi evidence.
SELECT c.tieu_chi_id, c.requirement_version_id, c.noi_dung,
       c.loai_kiem_tra, c.bat_buoc, c.missing_policy, c.noi_dung_bat_buoc_trong_hd,
       c.bang_chung_can_thiet, c.source_dieu_khoan_id,
       q.quy_tac_id, q.finding, q.dieu_kien_json, q.ly_do_chuan,
       q.uu_tien, q.trang_thai, q.human_verified, q.rule_version
FROM knowledge.tieu_chi_danh_gia c
LEFT JOIN knowledge.quy_tac_quyet_dinh q ON q.tieu_chi_id=c.tieu_chi_id
WHERE c.tieu_chi_id=%(criterion_id)s
ORDER BY q.uu_tien DESC, q.quy_tac_id;
```

```sql
-- Q32_CRITERION_BASIS: criterion → article → legal document; khác chunk hợp đồng.
SELECT c.tieu_chi_id, c.requirement_version_id,
       d.dieu_khoan_id, d.vi_tri, d.noi_dung_nguon, d.url_nguon, d.trang_thai_xac_minh,
       vb.van_ban_id, vb.so_hieu, vb.ten_van_ban
FROM knowledge.tieu_chi_danh_gia c
LEFT JOIN knowledge.dieu_khoan_phap_ly d ON d.dieu_khoan_id=c.source_dieu_khoan_id
LEFT JOIN knowledge.van_ban_phap_ly vb ON vb.van_ban_id=d.van_ban_id
WHERE c.tieu_chi_id=%(criterion_id)s;
```

```sql
-- Q33_EVIDENCE_POLICIES: service phải diễn giải pham_vi/điều kiện; không áp dụng mọi row.
SELECT chinh_sach_id, ten, dieu_kien_json, hanh_dong, pham_vi, trang_thai
FROM knowledge.chinh_sach_bang_chung ORDER BY chinh_sach_id;
```

```sql
-- Q34_EXCEPTIONS: ngoại lệ theo version, chung hoặc riêng criterion.
SELECT e.* FROM knowledge.ngoai_le_ap_dung e
JOIN knowledge.tieu_chi_danh_gia c ON c.requirement_version_id=e.requirement_version_id
WHERE c.tieu_chi_id=%(criterion_id)s
  AND (e.tieu_chi_id IS NULL OR e.tieu_chi_id=c.tieu_chi_id)
ORDER BY e.ngoai_le_id;
```

Facts dùng Q14; chọn trường cần cho criterion, như giá/diện tích/ngày, kèm trạng thái và
quotes. Đừng biến JSON NULL thành số 0 hoặc chỉ nhận giá trị đã chọn mà bỏ CONFLICT.
Q31–Q34 xem source catalog; engine chạy dùng các tables/indexes cùng snapshot đã pin.
`Context.rule_version` và version từng rule trong catalog có thể khác nhau (rules lịch
sử/risk có nhãn riêng). Không thêm `q.rule_version=ca.rule_version` một cách máy móc làm
mất rules; policy release phải định nghĩa tập rules, và audit giữ các nhãn gốc.

Nếu cần chứng từ ngoài, đọc tập riêng theo case:

```sql
-- Q35_EXTERNAL_DOCUMENTS: chứng từ đăng ký cho case; chưa là evidence đã verified.
SELECT ct.chung_tu_id, ct.loai_chung_tu, ct.noi_dung, ct.ngay_chung_tu,
       ct.trang_thai_xac_minh, ct.human_verified,
       t.tep_id, t.object_uri, t.sha256, t.mime_type
FROM runtime.chung_tu_bo_sung ct
LEFT JOIN runtime.tep_nguon t ON t.tep_id=ct.tep_id
WHERE ct.ca_id=%(case_id)s ORDER BY ct.chung_tu_id;
```

Chứng từ có thể là tệp riêng, không buộc có `t.hop_dong_id` giống PDF chính; quyền và
quan hệ thuộc **case** phải được kiểm tra. `bang_chung_ngoai` là liên kết chứng từ với
finding C07 sau khi reasoning, không dùng C07 seed để lấy kết luận ngược vào reasoner.

**Gói đưa cho provider:** criterion + requirement/version + basis/rules/ngoại lệ đã chọn
+ selected chunks + facts/chứng từ liên quan + scope/date/coverage thực tế. Provider trả
`Observation`, backend kiểm tra spans/IDs/gates. `ReasoningRequest.payload` hiện chỉ có
requirements, chunks, retrieval, observations và contract ID; facts/profile không phải
field tùy ý thêm vào payload. Mapper/provider chuyển facts thành observations đúng DTO.

**Nơi ghi:** C07 → `ket_qua_tieu_chi`; quote → `bang_chung_ket_qua`; evidence ngoài →
`bang_chung_ngoai`. Lưu DTO đầy đủ qua Store/lineage để giữ mandatory/excluded/legal basis
không có cột riêng trong workbook. Writer riêng mới phải giữ cùng các thông tin đó.

#### C3 — Aggregation: gom C07 theo requirement instance, không theo contract chung

```sql
-- Q36_AGGREGATION_INPUT: C05 → selected run C07 + aggregation policy của version.
SELECT a.yeu_cau_ca_id, a.requirement_id, a.requirement_version_id,
       a.scope_status, a.version_status, a.applicability_status,
       k.ket_qua_id, k.tieu_chi_id, k.loai_phat_hien, k.uncertainty_reason,
       v.quy_tac_tong_hop_id, g.dieu_kien_json AS aggregation_conditions,
       g.thu_tu_uu_tien_json, g.rule_version AS aggregation_rule_version
FROM runtime.yeu_cau_ap_dung a
LEFT JOIN runtime.ket_qua_tieu_chi k
  ON k.yeu_cau_ca_id=a.yeu_cau_ca_id AND k.ca_id=a.ca_id
 AND k.lan_chay_id=%(run_id)s
LEFT JOIN knowledge.phien_ban_yeu_cau v ON v.requirement_version_id=a.requirement_version_id
LEFT JOIN knowledge.quy_tac_tong_hop g ON g.quy_tac_tong_hop_id=v.quy_tac_tong_hop_id
WHERE a.ca_id=%(case_id)s ORDER BY a.yeu_cau_ca_id, k.tieu_chi_id;
```

Điều kiện run đặt **trong ON** để vẫn thấy requirement chưa có C07. Không chuyển thành
WHERE `k.lan_chay_id=...` rồi mất những requirements đó. Đọc full C07 DTO từ lineage/QA
khi cần `mandatory`, `excluded`, evidence/basis (Q36 chỉ là projection để xem).

Nhóm theo `yeu_cau_ca_id`, đối chiếu tập criteria dự kiến từ version để phát hiện thiếu
finding. Gọi `aggregate(context, knowledge, criteria, applicable_requirements)`, không
tự đếm tỷ lệ SATISFIED để thay policy. Output C08 ghi `ket_qua_tuan_thu` + lineage đúng run.
Một requirement có nhiều quotes/risks vẫn chỉ có một C08 của run đó.

#### C4 — Bước 6: đọc C07 và C09 riêng rồi match risk rules

**C07 input:** Q36 hoặc `CriterionResult` DTO. **C09 input:** query sau.

```sql
-- Q37_CITATION_FINDINGS: C09 đúng case/run, kèm citation gốc để truy vết.
SELECT f.*, v.noi_dung_vien_dan_mau, v.so_hieu, v.ten_van_ban
FROM runtime.phat_hien_vien_dan f
JOIN runtime.ca_danh_gia ca ON ca.ca_id=f.ca_id
JOIN runtime.vien_dan_phap_ly_hop_dong v
  ON v.vien_dan_id=f.vien_dan_id AND v.hop_dong_id=ca.hop_dong_id
WHERE f.ca_id=%(case_id)s AND f.lan_chay_id=%(run_id)s
ORDER BY f.finding_id;
```

Có C07 mà chưa có C09 thì ghi nhánh citation chưa chạy/coverage chưa đủ; không tự giả
tạo C09 VALID/UNKNOWN để cho workflow đủ dòng. Khi nhánh C09 chạy riêng khác run ID,
workflow phải pin rõ ID nhánh vào input snapshot; các query ở đây giả định đã hợp nhất
input dưới cùng run. Không lấy C09 run mới nhất để ghép với C07 lịch sử.

```sql
-- Q38_RISK_RULE_CANDIDATES: tìm trigger ứng viên, chưa phải danh sách risk đã kết luận.
SELECT k.ket_qua_id AS criterion_finding_id, k.tieu_chi_id, k.loai_phat_hien,
       q.quy_tac_id, q.trigger_status, q.trigger_json, q.rule_version,
       r.rui_ro_id, r.ten_rui_ro, r.muc_do_co_so, r.ban_chat_rui_ro
FROM runtime.ket_qua_tieu_chi k
JOIN knowledge.quy_tac_rui_ro q
  ON q.tieu_chi_id=k.tieu_chi_id AND q.nhanh='COMPLIANCE'
 AND q.trigger_status=k.loai_phat_hien
JOIN knowledge.danh_muc_rui_ro r ON r.rui_ro_id=q.rui_ro_id
WHERE k.ca_id=%(case_id)s AND k.lan_chay_id=%(run_id)s
ORDER BY k.ket_qua_id, q.quy_tac_id;
```

Engine còn kiểm tra enabled/gates/mandatory/excluded, nên query này không thay engine.
Nhánh citation lấy `knowledge.quy_tac_rui_ro WHERE nhanh='CITATION'`, rồi dùng C09 status,
reason, domain, verification và metadata để chọn rule; không JOIN trực tiếp C09 với
criterion ID. Khi triển khai `citation_mapper.py`, đọc rule nhánh CITATION, các ID `RULE_CITATION_*` và guards tương ứng; file hiện chỉ là skeleton.

**Output C10:** ghi `ket_qua_rui_ro`. `nguon_tieu_chi_id` = **C07.ket_qua_id**, hoặc
`nguon_vien_dan_id` = **C09.finding_id**, chỉ một trong hai. C08 là tổng hợp requirement,
không thay nguồn finding của C10. UNKNOWN tạo VERIFICATION theo policy, không tự là vi phạm.

#### C5 — Bước 7: risk instance → risk catalog ID → links → templates

```sql
-- Q39_RECOMMENDATION_TEMPLATES: params risk_id là catalog ID (rui_ro_id), không instance ID.
SELECT r.rui_ro_id, r.ten_rui_ro, l.lien_ket_id,
       t.khuyen_nghi_id, t.noi_dung, t.loai_hanh_dong, t.uu_tien,
       t.required_elements_json, t.gioi_han_sinh_json,
       t.kiem_tra_sau_khac_phuc, t.bang_chung_khac_phuc_can_luu
FROM knowledge.danh_muc_rui_ro r
LEFT JOIN knowledge.rui_ro_khuyen_nghi l ON l.rui_ro_id=r.rui_ro_id
LEFT JOIN knowledge.danh_muc_khuyen_nghi t ON t.khuyen_nghi_id=l.khuyen_nghi_id
WHERE r.rui_ro_id=%(risk_id)s ORDER BY l.lien_ket_id, t.khuyen_nghi_id;
```

Một risk có thể liên kết nhiều templates; phát hành theo policy, không lấy template
đầu tiên tùy ý. Tạo C11 gắn với **instance** `C10.ket_qua_rui_ro_id`; ghi FK này vào
`khuyen_nghi_danh_gia.ket_qua_rui_ro_id` (tham chiếu `ket_qua_rui_ro.ket_qua_id`).
Không JOIN khuyến nghị qua criterion ID vì sẽ mất citation risks và có thể gán sai actions.
Không có mapping/template thì báo knowledge gap; không dùng câu chung để che mất gap.

#### C6 — Bắt đầu nhanh với QA, rồi thay input/observations bằng implementation thật

Sau khi có `load_reference` ở mục 2.6:

```python
from devtools.qa_runs import new_run
from legal_checker.modules.legal_knowledge.repository import Knowledge
from legal_checker.shared.contracts.pipeline import PipelineRequest

raw = load_reference(database_url, case_id, "INPUT", "PipelineRequest")
request = PipelineRequest.model_validate(raw)
knowledge = Knowledge(database_url, request.knowledge_snapshot_sha256)

# Khi chuẩn bị chạy dev: thay IDs của retrieval/citation và context sang run mới.
dev_request = new_run(raw, "DEV_REASONING_001")
dev_request.payload.observations = []  # Không dùng kết luận tham chiếu làm kết quả reasoner mới.
# Bổ sung observations từ provider/rules của bạn trước khi evaluate/save.
```

Implementation mới cần xử lý observations rỗng bằng uncertainty theo policy; stub hiện tại phát sinh `NotImplementedError` chứ chưa trả UNKNOWN. Viết provider bằng `ObservationProvider.observe`, giữ nguồn/gates thực tế. Khi test
Risk riêng, C07/C09 reference được phép là upstream; khi test Reasoning thì C07 là expected.

Chưa có runner/evaluator CLI cho nhóm C; các placeholder cũ đã xóa. Nhóm C triển khai producer/mapper, logic module, persistence và bộ tests/evaluator của mình. Không dùng observations/EXPECTED đã seed làm kết quả của provider mới rồi báo metric pass.

**Bàn giao nhóm C:** C07/C08/C10/C11 cùng Context/run/hash, rows + DTO lineage đã lưu,
observations/provider thật, nguồn/chứng từ/gates và cách gọi. Nhóm D chỉ đọc các outputs
đã hợp nhất; không chạy lại reasoning/risk để đổi đáp án khi render report.

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
WHERE k.ca_id = 'CA360_001'
  AND k.lan_chay_id = 'CA360_001_PDF360_LS2_REFERENCE'
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

`modules/reports/builder.py:build_draft_report` nhận `IntegrationInput`, cộng thêm hai tham số bắt buộc `risks=merged_c10` và `recommendations=merged_c11`. Nhóm D đọc chúng từ output của đúng run hoặc nhận handoff nhóm C. Builder không tự tính citation risks/actions nữa. `validate_report` cũng cần hai tham số này để kiểm tra report giữ đúng input.

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
pytest -q -c backend/pyproject.toml backend/tests/contract/test_db_handoffs.py -k report
```

Bàn giao report reader/mapper/builder/writer/exporter, API/UI, wiring và integration/E2E tests.
Nếu chưa triển khai review, ghi rõ demo hiện chỉ phát hành report draft.

### 7.7 Recipe đọc/join cho nhóm D: chọn run rồi đọc từng section

#### D1 — Phân biệt report mẫu với report của run dev

| Cần gì? | Nguồn đúng |
|---|---|
| Dựng UI bằng report mẫu | Full C13 ở `qa.artifacts`, role EXPECTED, contract_name C13 |
| Xem normalized rows reference | Bảng runtime và QA DTO cùng reference case/run |
| Report cho run dev đã chạy bước 5–7 | `assessment_runs` + `assessment_output_lineage` + inputs upstream đã pin |
| Export/report đã lưu | `bao_cao_danh_gia` với report version/run pin đầy đủ do writer tạo |

Bộ 360 vừa seed có normalized reference outputs và QA artifacts; seed **chưa tự tạo**
`assessment_runs`/lineage cho các case corpus. Query lineage rỗng lúc này là bình thường.
Không fallback từ run dev chưa tồn tại sang QA expected rồi hiển thị như run đã hoàn thành.

```python
from legal_checker.modules.assessments.repository import Store
from legal_checker.shared.contracts.report import FinalReport

# Preview mẫu cho UI DEV, không phải report mới.
reference_report = FinalReport.model_validate(
    load_reference(database_url, case_id, "EXPECTED", "C13")
)

# Output bước 5–7 của run dev thực sự đã lưu; Store.get còn kiểm tra output checksum.
dev_output = Store(database_url).get(case_id, dev_run_id)
if dev_output is None:
    raise ValueError("Run chưa có kết quả; hiển thị pending/chưa chạy")
```

#### D2 — Đọc context/input snapshot và full output

```sql
-- Q40_RUN: 1 run chứa input C05/C06/chunks/C09 và output C07–C11 đã pin.
SELECT ca_id, run_id, input_sha256, output_sha256, input_json, response_json, created_at
FROM runtime.assessment_runs
WHERE ca_id=%(case_id)s AND run_id=%(run_id)s;
```

`PipelineRequest.model_validate(input_json)` và `PipelineResponse.model_validate(response_json)`
dựng lại DTO; dùng Store.get cho kiểm tra checksum output. Input snapshot chứa C05 của run,
tránh đọc `yeu_cau_ap_dung` hiện tại rồi trộn checklist mới với kết quả cũ. Snapshot này
**không chứa full C02/C03/C04/C01**; report reader phải pin thêm document/profile/extraction
và checklist output upstream. Với DEV có thể dùng reference cùng case để làm UI, nhưng
khi integration thật không lấy profile hiện tại thay profile lịch sử mà không có version.

#### D3 — C07/evidence: lấy membership run trước, rồi JOIN bằng finding ID

```sql
-- Q41_LINEAGE: full DTO của C07/C08/C10/C11, giữ cả fields không có cột workbook.
SELECT table_name, output_id, payload
FROM runtime.assessment_output_lineage
WHERE ca_id=%(case_id)s AND run_id=%(run_id)s
ORDER BY table_name, output_id;
```

Mapper dispatch `table_name` → `CriterionResult`, `RequirementResult`, `RiskResult`,
`Recommendation`. Bảng này ghi tên như `ket_qua_tieu_chi`, **không phải** chuỗi C07.
Để hiển thị quote và trang, dùng query mục 7.2, thêm JOIN `doan_hop_dong` theo `doan_id`
và contract của case. Nhóm quotes theo `ket_qua_id`; số findings đếm distinct PK/DTO,
không đếm số rows sau JOIN. Legal basis lấy IDs/snapshot DTO; đọc đúng Knowledge hash.

#### D4 — C08 không có run column: JOIN qua lineage

```sql
-- Q42_REQUIREMENT_OUTPUTS: membership của run → C08 → C05 instance.
SELECT t.*, a.requirement_id, a.requirement_version_id, l.payload AS full_c08
FROM runtime.assessment_output_lineage l
JOIN runtime.ket_qua_tuan_thu t ON t.tuan_thu_id=l.output_id
JOIN runtime.yeu_cau_ap_dung a
  ON a.yeu_cau_ca_id=t.yeu_cau_ca_id AND a.ca_id=l.ca_id
WHERE l.ca_id=%(case_id)s AND l.run_id=%(run_id)s
  AND l.table_name='ket_qua_tuan_thu'
ORDER BY t.tuan_thu_id;
```

Query phục vụ truy vết normalized rows; nội dung checklist/scope/version lịch sử lấy
từ `input_json`, full C08 lấy lineage. Không `SELECT ket_qua_tuan_thu WHERE
yeu_cau_ca_id IN (...)` rồi nhận tất cả outputs nhiều runs như một kết quả duy nhất.
Nếu reader cho baseline vừa seed chưa có lineage, đọc C08 QA theo reference case thay
vì áp quy tắc đọc run dev lên dữ liệu chưa có membership.

#### D5 — Risks: JOIN đúng finding nguồn, không JOIN C07 và C09 qua case

```sql
-- Q43_RISK_PROVENANCE: 1 risk → tối đa 1 finding của mỗi nhánh; XOR phải đúng.
SELECT r.ket_qua_id AS risk_instance_id, r.rui_ro_id, r.loai_rui_ro,
       r.severity_snapshot, r.giai_thich, r.nguon_tieu_chi_id, r.nguon_vien_dan_id,
       k.ket_qua_id AS resolved_criterion_finding, k.tieu_chi_id, k.loai_phat_hien,
       f.finding_id AS resolved_citation_finding, f.vien_dan_id, f.trang_thai AS citation_status,
       l.payload AS full_c10
FROM runtime.assessment_output_lineage l
JOIN runtime.ket_qua_rui_ro r ON r.ket_qua_id=l.output_id AND r.ca_id=l.ca_id
LEFT JOIN runtime.ket_qua_tieu_chi k
  ON k.ket_qua_id=r.nguon_tieu_chi_id AND k.ca_id=l.ca_id AND k.lan_chay_id=l.run_id
LEFT JOIN runtime.phat_hien_vien_dan f
  ON f.finding_id=r.nguon_vien_dan_id AND f.ca_id=l.ca_id AND f.lan_chay_id=l.run_id
WHERE l.ca_id=%(case_id)s AND l.run_id=%(run_id)s AND l.table_name='ket_qua_rui_ro'
ORDER BY r.ket_qua_id;
```

Với nguồn compliance, `resolved_criterion_finding` phải có; nguồn citation tương tự.
FK đơn lẻ không kiểm tra đủ cùng case/run, nên reader/writer kiểm tra các liên kết này.
VERIFICATION có thể đến từ **cả hai nhánh**, không thể xác định nguồn chỉ từ loại risk.
UI tách section theo `risk_type` nhưng link bằng finding nguồn của C10.

#### D6 — Recommendations: JOIN risk instance, cùng membership run

```sql
-- Q44_RECOMMENDATION_OUTPUTS: chỉ C11 và C10 cùng case/run.
SELECT n.*, r.rui_ro_id, r.loai_rui_ro, r.severity_snapshot,
       ln.payload AS full_c11
FROM runtime.assessment_output_lineage ln
JOIN runtime.khuyen_nghi_danh_gia n ON n.khuyen_nghi_ca_id=ln.output_id
JOIN runtime.ket_qua_rui_ro r ON r.ket_qua_id=n.ket_qua_rui_ro_id AND r.ca_id=ln.ca_id
JOIN runtime.assessment_output_lineage lr
  ON lr.table_name='ket_qua_rui_ro' AND lr.output_id=r.ket_qua_id
 AND lr.ca_id=ln.ca_id AND lr.run_id=ln.run_id
WHERE ln.ca_id=%(case_id)s AND ln.run_id=%(run_id)s
  AND ln.table_name='khuyen_nghi_danh_gia'
ORDER BY n.khuyen_nghi_ca_id;
```

Nội dung report dùng `noi_dung_snapshot`/full C11 đã lưu; template hiện tại chỉ để truy
vết catalog, không dùng thay câu khuyến nghị lịch sử. Giữ legal/evidence IDs và PENDING.

#### D7 — Review và report version

```sql
-- Q45_REVIEW_EVENTS: danh sách audit để xử lý; chưa chứng minh run này đã được duyệt.
SELECT review_id, doi_tuong_loai, doi_tuong_id, actor_id, hanh_dong,
       gia_tri_truoc_json, gia_tri_sau_json, ly_do, ngay_review, phien_ban_id
FROM runtime.nhat_ky_review WHERE ca_id=%(case_id)s
ORDER BY ngay_review, review_id;
```

Review service phải đối chiếu object ID với đúng outputs/report version và quyền actor.
Một review của case cũ không duyệt mọi output mới của case. Chưa có C12 thật thì report
DRAFT/PENDING. Nhiều rows review là lịch sử tuần tự, không JOIN trực tiếp vào từng risk
rồi nhân số recommendations.

```sql
-- Q46_REPORT_VERSIONS: xem versions đã lưu và run pin nếu report full có audit.context.
SELECT bao_cao_id, ca_id, phien_ban_bao_cao, report_status, review_status,
       report_uri, knowledge_snapshot_sha256, rule_version, ngay_tao,
       report_json->'audit'->'context'->>'run_id' AS pinned_run_id
FROM runtime.bao_cao_danh_gia
WHERE ca_id=%(case_id)s ORDER BY phien_ban_bao_cao, bao_cao_id;
```

Native report seed là projection gọn nên `pinned_run_id` có thể NULL; đọc full C13 QA
để preview. Writer report thật cần lưu full `ReportContent` với `audit.context`/upstream
version pins; đây là quy ước cần triển khai, không phải native projection đã tự có đủ.
Không chọn report mới nhất cho một run khác; khi export, chọn chính xác report ID/version.

#### D8 — Ghép section theo IDs rồi xây report

1. Case/source/deployment lấy Q10, C02/subjects/facts/Q11–Q14 hoặc snapshot DI đã pin.
2. C03 lấy Q15/snapshot DI; C04/C05 lấy upstream snapshot (C05 có trong run input).
3. C06/chunks dùng để mở evidence, C07/C08/C10/C11 lấy Store/lineage của run.
4. C09 lấy run input/Q37 đúng run; C12 lấy review service đúng targets nếu đã triển khai.
5. Dựng `ReportContent`; summary đếm từ DTOs, UNKNOWN/unresolved giữ nguyên.
6. Validate ownership/context/grounding; lưu C13 draft/version + URI nếu export.

Gọi `build_draft_report(integration_input, knowledge, risks=merged_c10, recommendations=merged_c11)` với C10/C11 đầy đủ. `IntegrationInput.compliance` vẫn là handoff compliance-only; truyền outputs đã hợp nhất qua hai tham số riêng để không mất nhánh citation. Report không chạy lại bước 6–7 hoặc cộng citation risks lần thứ hai. Writer/export/reader mới vẫn do nhóm D triển khai.

**Bàn giao nhóm D:** API chọn case/run/report version, report builder/reader/writer,
mapping mỗi section, export storage, UI mở evidence và các kiểm tra thiếu kết quả/trộn run.
UI chỉ gọi API; queries nằm trong repositories của backend.

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
        ("CA360_001",),
    ).fetchall()

fields = set(ApplicableRequirement.model_fields) - {"reason"}
requirements = [
    ApplicableRequirement.model_validate(
        {
            **{name: row[name] for name in fields},
            "reason": {"summary": row["ly_do"] or ""},
        }
    )
    for row in rows
]
print([item.requirement_id for item in requirements])
```

Ví dụ dùng cột hiện có của C05; số dòng phụ thuộc case và workbook đã seed.
`ly_do` có thể là prose hoặc JSON text: mapper production cần giữ cấu trúc reason nếu
parse được JSON, thay vì luôn bọc JSON thành một chuỗi `summary`.

Profile có các flags SQL TEXT `CO/KHONG/UNKNOWN`; C02 cần bool nullable/strict.
Map CO → True, KHONG → False, UNKNOWN/null → None. Không gọi `bool('KHONG')`
vì Python trả True; giá trị lạ phải báo lỗi thay vì tự đoán.

### 8.3 BRD mới có trạng thái phong phú hơn contract hiện tại

- C05 hiện chỉ RESOLVED/UNKNOWN cho version. NO_VERSION/CONFLICT phải giữ reason
  và unknown đúng ý nghĩa, hoặc mở rộng DTO/version/tests thống nhất trước khi trả enum mới.
- C10 hiện có VERIFICATION; bảng SQL hiện có `loai_rui_ro`, bộ 360 lưu cả loại này.
  Với dữ liệu cũ thiếu loại, mapper phải xét provenance/context; không gán loại mới
  chỉ từ tên severity hay một chuỗi status chung.
- C07/C11 hiện review PENDING; luồng review nên lưu C12/effective result riêng,
  không tự đổi DTO AI output thành APPROVED.
- Khuyến nghị LLM và report version cần mapping/contract update như các mục trên.

Không sửa enum của một module riêng rồi để module kế tiếp nhận schema cũ.

### 8.4 Run lineage và snapshot: phần đã có và phần còn phải bổ sung

**Các bảng workbook không có run column ở mọi nơi; dùng snapshots/output lineage bổ sung để chọn đúng kết quả lịch sử.**

| Dữ liệu | Có run ID trực tiếp trong schema hiện tại? | Cách xử lý |
|---|---|---|
| Retrieval, C07, C09 | Có `lan_chay_id` | Luôn lọc cùng case/run và kiểm tra target IDs |
| Evidence C07 | Không; có `ket_qua_id` | JOIN qua C07 đã chọn đúng run |
| C08 | Không | Dùng membership và DTO trong assessment_output_lineage |
| C10 | Không; có source C07 hoặc C09 | Theo finding nguồn đã pin hoặc assessment_output_lineage |
| C11 | Không; có risk ID | Theo risk đã chọn đúng lineage |
| C13 | Không; có report version | Report cần pin run/outputs trong snapshot hoặc metadata bổ sung |
| Profile/subjects/time markers | Không có run/extraction version đầy đủ | Re-extraction cần version/snapshot trước khi giữ nhiều kết quả lịch sử |
| C04/C05 checklist | Không có run ID | C05 trong assessment_runs input snapshot; full Temporal writer cần policy riêng |

Migration 002 đã bổ sung `runtime.assessment_case_pins`, `assessment_runs` và
`assessment_output_lineage`: writer bước 5–7 lưu raw input/output và bản DTO bất biến,
reader có thể truy membership theo case/run ngay cả khi bảng workbook không có run column.
Các incoming IDs đã tồn tại nhưng khác nội dung bị conflict; khi đổi checklist/chunk
hãy tạo IDs/version phù hợp thay vì ghi đè. Full DI/review/report writers vẫn cần lineage
và extraction/report version policies riêng như bảng trên.

`knowledge.knowledge_snapshots` lưu nội dung/hash của 18 bảng nghiệp vụ được capture
hiện tại hoặc hash lịch sử đã có. `dev_meta.seed_imports.source_sha256` chỉ là hash Excel.
Không mặc định hash lịch sử của một ca seed có snapshot tương ứng đã được nhập: reader
chọn hash không tồn tại sẽ báo lỗi, không gán nội dung hiện tại vào hash cũ.
Snapshot dev giữ status DEV_UNVERIFIED và flags nguồn; không tự biến dataset thành gold.

### 8.5 Điểm nối kiến trúc hiện tại

Phụ lục BRD dùng các tên tầng `interfaces/adapters/bootstrap` để diễn tả trách nhiệm.
Repo đã tổ chức theo module: ports ở owning modules, implementations DB/OCR/LLM
ở repositories/providers, connection/transport dùng `core`/`shared`, wiring tại
`api/dependencies.py` hoặc factory dùng cho workflow/worker.
Không cần tạo lại các folder cũ đã bỏ để thực hiện hướng dẫn này.

Factory khởi tạo Knowledge, Store, LLM audit sink và source storage; GET knowledge/run dùng DB.
API khởi chạy assessment toàn bộ chưa triển khai; không có POST chạy riêng bước 5–7.
Khi nối các services upstream vào full workflow, inject reader/provider/writer rõ ràng;
không đưa query SQL trực tiếp vào route hoặc engine để bỏ qua ranh giới module.

### 8.6 Kiểm tra JOIN có âm thầm làm mất hoặc nhân dữ liệu không?

Query selected evidence Q30 dùng INNER JOIN để đọc các liên kết đúng. Trước khi map,
kiểm tra các rows bị lỗi bằng LEFT JOIN để chúng không biến mất khỏi kết quả:

```sql
-- Q48_INVALID_RETRIEVAL: chỉ trả lỗi ownership/criterion/run source của case đã chọn.
SELECT r.truy_xuat_id, r.yeu_cau_ca_id, r.tieu_chi_id, r.doan_id,
       CASE WHEN d.doan_id IS NULL THEN 'CHUNK_MISSING_OR_FOREIGN'
            WHEN c.tieu_chi_id IS NULL THEN 'CRITERION_MISSING_OR_WRONG_VERSION'
       END AS error_code
FROM runtime.ket_qua_truy_xuat r
JOIN runtime.yeu_cau_ap_dung a ON a.yeu_cau_ca_id=r.yeu_cau_ca_id
JOIN runtime.ca_danh_gia ca ON ca.ca_id=a.ca_id
LEFT JOIN runtime.doan_hop_dong d
  ON d.doan_id=r.doan_id AND d.hop_dong_id=ca.hop_dong_id
LEFT JOIN knowledge.tieu_chi_danh_gia c
  ON c.tieu_chi_id=r.tieu_chi_id AND c.requirement_version_id=a.requirement_version_id
WHERE a.ca_id=%(case_id)s AND r.lan_chay_id=%(run_id)s
  AND (d.doan_id IS NULL OR c.tieu_chi_id IS NULL)
ORDER BY r.truy_xuat_id;
```

Với catalog hiện tại khớp pin, kết quả phải rỗng. Với snapshot lịch sử, thực hiện kiểm
tra criterion/version bằng Knowledge snapshot tương ứng thay JOIN catalog hiện tại.
Không tự sửa ID trong mapper để bỏ lỗi. Không có rows retrieval không chứng minh retrieval
đã chạy thành công; kiểm tra checkpoint/input snapshot của producer.

```sql
-- Q49_COUNTS: so số parent và evidence, không lấy count(*) của giant JOIN.
SELECT
  (SELECT count(*) FROM runtime.yeu_cau_ap_dung a WHERE a.ca_id=%(case_id)s) AS c05_count,
  (SELECT count(*) FROM runtime.ket_qua_tieu_chi k
   WHERE k.ca_id=%(case_id)s AND k.lan_chay_id=%(run_id)s) AS c07_count,
  (SELECT count(*) FROM runtime.bang_chung_ket_qua b
   JOIN runtime.ket_qua_tieu_chi k ON k.ket_qua_id=b.ket_qua_id
   WHERE k.ca_id=%(case_id)s AND k.lan_chay_id=%(run_id)s) AS c07_evidence_count,
  (SELECT count(*) FROM runtime.phat_hien_vien_dan f
   WHERE f.ca_id=%(case_id)s AND f.lan_chay_id=%(run_id)s) AS c09_count;
```

Mapper phải giữ `c07_count` findings dù `c07_evidence_count` lớn hơn/nhỏ hơn. Số C08
không nhất thiết bằng số C05 vì NOT_APPLICABLE được loại có lý do; danh sách excluded
và unresolved phải còn trong output/report. Không lấy số target có evidence làm mẫu số
coverage rồi bỏ qua targets chưa retrieval/không tìm được evidence.

### 8.7 Ví dụ đi hết một requirement để hiểu ai dùng dữ liệu nào

Giả sử bạn đã chọn một case DEV và một `yeu_cau_ca_id` trong case đó. IDs cụ thể đọc từ
Q25, không tự điền tên criterion của một version khác.

```text
ca_danh_gia.hop_dong_id
  → hop_dong.tep_nguon_id → tep_nguon (bytes PDF cho bước 1–2)
  → ho_so_hop_dong + subjects + facts/evidence + markers (C02)
  → doan_hop_dong (chunks), vien_dan_phap_ly_hop_dong (C03)

C02 + knowledge.pham_vi_ap_dung → Scope (C04)
C04.requirement_id + markers + knowledge.phien_ban_yeu_cau → Temporal (C05)
C05.requirement_version_id → knowledge.tieu_chi_danh_gia
  + chunks → Retrieval → ket_qua_truy_xuat (C06)
C05 + C06 + facts + rules/basis → Reasoning
  → ket_qua_tieu_chi + bang_chung_ket_qua (C07)
C07.yeu_cau_ca_id + C05 + policy → ket_qua_tuan_thu (C08)

C03 + ngày/profile + legal metadata → Citation Validation → phat_hien_vien_dan (C09)
C07 + C09 + risk rules → ket_qua_rui_ro (C10)
C10.rui_ro_id → rui_ro_khuyen_nghi → danh_muc_khuyen_nghi
  → khuyen_nghi_danh_gia gắn C10 instance (C11)

Pin case/run + C01–C11 (+ C12 thật nếu có) → Report (C13)
```

Trong dev độc lập, mỗi người bắt đầu từ **mũi tên đầu vào của phần mình** bằng seed,
rồi tạo output mới. Khi integration, thay output seed đó bằng output thật của người trước;
giữ schema/IDs/version/provenance thống nhất. Mỗi người không cần tự implement cả pipeline
chỉ để lấy input, cũng không dùng kết luận mẫu của chính module để tạo output giống expected.

## 9. Thứ tự làm và cách bàn giao

### 9.1 Khởi động song song

| Nhóm | Việc làm ngay bằng DB đã seed | Không cần đợi |
|---|---|---|
| A | PDF test + parser/extraction/chunker + C01/C02/C03 mapper/writer | Scope/Retrieval/Reasoning |
| B — Legal | Profile seed → scope/temporal/citation rules + C04/C05/C09 | DI thật |
| B — Retrieval | C05/chunks/criteria seed → search/select per-criterion + C06 | Scope/Temporal thật |
| C | Dùng C05/C06/chunks SQL hoặc QA input của bộ mới; viết observations/provider và dùng Knowledge/Store | DI/Search/LLM thật |
| D | Report reader/mapper/UI layout với outputs mẫu; review/run/version/wiring design | Upstream implementations thật |

Riêng **test hiệu quả DI thật** cần PDF có annotation. **Test Retrieval/Reasoning thật**
cần evidence/finding đã annotation hoặc reviewer xác nhận. Các expected outputs seed
có thể kiểm tra mapping/joins; việc dùng chúng làm gold về pháp lý cần xác nhận trước.

### 9.2 Các phần chung nên chốt trước khi ghép

- Shared DTO/version và mapping khác biệt mục 8.
- Dùng SQL snapshot reader/hash đã có; curation/release policy mới: nhóm C phối hợp người quản trị knowledge.
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
```

Mỗi module tự query rows từ DB qua repository, rồi map/validate contract trước khi chạy implementation.
Không còn bắt buộc folder fixture JSON để replay. Bộ mới có payload/reference trong
`qa.artifacts`; đọc bằng `join_artifacts` như mục 2.6. Các tests còn dựng DTO nhỏ
hoặc load run từ PostgreSQL test để kiểm tra module và conformance validators.

Chạy suite trên DB test riêng:

```bash
TEST_DATABASE_URL='postgresql://legal_checker:legal_checker_local_only@127.0.0.1:5433/legal_checker_test' \
  pytest -q -c backend/pyproject.toml
```

Tests tự tạo DB con, nạp SQL seed nhỏ có refs đóng và xóa sau khi chạy;
không ghi DB dev hoặc dùng đường dẫn Downloads/cloud DB. Thiếu biến TEST_DATABASE_URL
thì tests cần DB được skip. CI luôn có PostgreSQL service.
Module mới thêm tests và eval có annotation riêng; không coi SQL seed là legal gold.

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
- [Module schemas](module_contracts.schema.json)
- [Kiến trúc folder hiện tại](architecture.md)
