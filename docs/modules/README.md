# Hướng dẫn Tích hợp & Quy chuẩn Chung cho các Module

Tài liệu này chứa các quy tắc thiết kế chung, quy ước kết nối database, quy tắc JOIN và các lớp kiểm thử giữa các module.

## Tài liệu chi tiết theo từng nhóm phát triển:
- [Nhóm A: Bước 1–2: Tiếp nhận & Document Intelligence](group_a_document_intelligence.md)
- [Nhóm B: Bước 3–4: Applicable Law, Citation Validation & Retrieval](group_b_legal_and_retrieval.md)
- [Nhóm C: Bước 5–7: Compliance Reasoning, Risk & Recommendation](group_c_compliance_and_risk.md)
- [Nhóm D: Bước 8–9: Report Aggregation & UI/Frontend](group_d_report_and_frontend.md)

---


Tài liệu dành cho các nhóm làm **bước 1–2**, **bước 3–4**, **bước 5–7** và **bước 9**.
Mục tiêu: mỗi nhóm mở repo, đọc đúng dữ liệu mẫu từ DB, viết phần của mình, test độc lập,
rồi bàn giao output có thể ghép với các nhóm khác.

Nguồn nghiệp vụ: `BRD_AI_Legal_Compliance_Checker_v1.1(5).pdf` người dùng cung cấp,
mục 6–8, tiêu chí nghiệm thu và phụ lục kiến trúc A.3–A.8 bổ sung ngày 13/10/2026.
Tên bảng/kiểu cột lấy từ migrations PostgreSQL đang có trong repo. Bộ
`v7.5.0-source-pdf360-r2-structured` giữ schema nghiệp vụ đã migrate từ `v7_4_9_RISK`.
Contract thực thi hiện tại lấy từ `backend/src/legal_checker/shared/contracts/`.
Phụ lục BRD có các API/kiến trúc đề xuất; những đề xuất đó chưa tự trở thành code đã chạy.

Dataset đang dùng: **v7.5.0-source-pdf360-r2-structured / supabase-public-v1**. Nhóm dev tải gói DEV_VALIDATION theo [hướng dẫn dataset](../database/dataset_and_corpus.md), rồi seed vào DB riêng. Bộ chunks/citations tham chiếu được giải thích tại [quy trình cập nhật reviewed](../database/reviewed_dataset_update.md).

Các JOIN bên dưới dùng case/run r2: ví dụ `CA360_001` và `CA360_001_PDF360_LS2_REFERENCE`. Chọn IDs thực tế từ DB đã seed, giữ cùng knowledge hash và không trộn với IDs của dataset cũ.

**Cập nhật ngày 05/11/2026:** đã có code cho intake/upload, parser PDF có text,
scope/temporal/citation, BM25, C07–C11, orchestrator Celery, review/report và frontend.
Các điểm nối và nghiệm thu còn thiếu được ghi trong
[bàn giao cho 5 người](../guides/team_onboarding_and_next_steps.md).
Có implementation không đồng nghĩa mọi nhánh đã đạt chất lượng nghiệm thu.
Dataset đã có revision `user-reviewed-20261105`; DB cũ dùng `local_db update`,
DB mới dùng `seed`. Giữ các recipe JOIN bên dưới để phát triển độc lập, sau đó
đối chiếu với output thật và cùng case/run/hash khi tích hợp.

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

| Phần | Hiện trạng trong code | Cần hoàn thiện / nghiệm thu |
|---|---|---|
| PostgreSQL và dataset | Alembic, tải/seed/update, receipt và snapshot bất biến | Phân phối ZIP reviewed; kiểm tra restore và cùng release trên từng máy |
| Bước 1–2 | Upload, PDF text parser, chunks, profile/facts và citation extractor; có DocumentRepository | OCR/DOCX còn thiếu; nối lưu extraction đầy đủ trước Retrieval; đo chất lượng extraction |
| Bước 3–4 | Catalog Scope/Temporal/Citation và BM25; có các tùy chọn embedding/reranking | Marker catalog còn thiếu/chồng lấn, profile không đủ, nối metadata evidence và C09 provenance |
| Bước 5–7 | LLM proposals, grounding, rules/aggregation, risks/recommendations và persistence | Tạo/truyền CriterionVerification, xử lý quote/rate limit/budget, phân biệt lỗi kỹ thuật với thiếu nội dung |
| Workflow | API khởi tạo run, Celery/Redis/Beat, lease/recovery, SSE/polling | Đóng các điểm nối Documents → Retrieval → verification; nghiệm thu nhiều PDF |
| Bước 8–9 | Review events, report versions, UI/history và export | Nghiệm thu quyền truy cập, review/publish/export và nguồn/provenance xuyên suốt |

Snapshot knowledge và lịch sử run nằm trong PostgreSQL. Cấu hình bằng `DATABASE_URL`,
optional `KNOWLEDGE_SNAPSHOT_SHA256` để pin snapshot cũ. Runtime mới trích xuất từ PDF
cần kiểm tra riêng; flags reviewed trong workbook không tự duyệt output mới của parser.

### 1.3 Phân công 5 người theo kế hoạch hiện tại

| Người | Nhóm / BRD | Folder chính | Bàn giao |
|---|---|---|---|
| 1 | Data, DB, CI/CD, hạ tầng | `devtools/`, migrations, `scripts/`, ba repo app/infra/GitOps | Dataset/version, schema, môi trường, CI và runbook |
| 2 | A — bước 1–2 | `modules/documents/` | C01, C02 + chunks, C03, source evidence và extraction được lưu |
| 3 | B — bước 3A/3B/4 | `applicable_law/`, `citation_validation/`, `retrieval/` | C04, C05, C09, C06 |
| 4 | C — bước 5–7 | `compliance/`, `risks/`, `recommendations/` | C07/C08, C10/C11 và verification logic |
| 5 | D — bước 8–9 và ghép hệ thống | `assessments/`, `reports/`, `reviews/`, API/workflows/frontend | Run orchestration, review, C13 và UI |

Đây là ownership theo kế hoạch, không khẳng định cá nhân nào đã viết từng commit.
Chi tiết việc ưu tiên và tiêu chí bàn giao ở [hướng dẫn cả nhóm](../guides/team_onboarding_and_next_steps.md).

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

Làm theo [hướng dẫn DB local](../database/local_setup.md). Sau khi seed:

```bash
source .venv/bin/activate
python -m scripts.local_db check
```

Cấu hình local đã dùng: host `127.0.0.1`, port `5433`, user `legal_checker`,
password local `legal_checker_local_only`. Chọn đúng DB bằng `DATABASE_URL`; tên mặc định
`legal_checker_dev_v750_r2_supabase` được đặt trong `.env.example`. Cách seed bộ hiện tại xem
[hướng dẫn DB](../database/local_setup.md#3-tạo-bảng-kiểm-tra-và-seed).
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



---

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

- [DB local, seed và cấu hình](../database/local_setup.md)
- [Contracts gốc v7.3.2](../contracts/data_contracts_v7_3_2.md)
- [Cách nối interfaces/workflow hiện có](../guides/team_onboarding_and_next_steps.md)
- [Module schemas](../contracts/module_contracts.schema.json)
- [Kiến trúc folder hiện tại](../architecture/system_architecture.md)
