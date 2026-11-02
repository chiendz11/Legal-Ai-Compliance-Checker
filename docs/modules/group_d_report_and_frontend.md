# Hướng dẫn Triển khai Nhóm D (Bước 8–9: Report Aggregation & UI/Frontend)

> **Người phụ trách**: Người 5 · **Input**: C07, C08, C09, C10, C11 · **Output**: C12 (ReviewEvents), C13 (FinalReport), UI Dashboard

Tài liệu chung: [Tổng quan module & Quy tắc JOIN](README.md)

---

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

# Output bước 5–7 đã lưu; Store kiểm tra graph/pins/checksums/normalized rows/lineage.
dev_output = Store(database_url).get(case_id, dev_run_id)
if dev_output is None:
    raise ValueError("Run chưa có kết quả; hiển thị pending/chưa chạy")
```

`Store.get/get_input/get_lineage` đọc exact case/run, kiểm tra input/output checksums,
case pins, knowledge đã pin, normalized rows và DTO lineage trong transaction đọc nhất
quán; không gọi reasoning/risk/recommendation. Dùng các hàm này cho reader sản phẩm.
Các SQL recipes dưới đây phục vụ kiểm tra/hiểu mapping, không thay thế integrity checks.
Dữ liệu legacy thiếu lineage không được ghép bằng “run mới nhất” hoặc QA EXPECTED.

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

