# Hướng dẫn Triển khai Nhóm C (Bước 5–7: Compliance Reasoning, Risk & Recommendation)

> **Người phụ trách**: Người 4 · **Input**: C05, C06, C09 · **Output**: C07, C08 (ComplianceFindings), C10 (Risks), C11 (Recommendations)

Tài liệu chung: [Tổng quan module & Quy tắc JOIN](README.md)

---

## 6. Nhóm C: bước 5–7: Compliance, Risk và Recommendation

### 6.1 Entrypoints và knowledge đã pin

Logic bước 5–7 đã có engines/services và tests nghiệp vụ. Các thành phần DB gồm:

1. `modules/legal_knowledge/repository.py:Knowledge(database_url, snapshot_sha256=None)`
   đáp ứng `KnowledgeSnapshot`, đọc 18 bảng nghiệp vụ và freeze nội dung trong DB.
2. `WorkbookKnowledgeRepository` vẫn là helper query, không phải full snapshot reader.
3. `modules/assessments/repository.py:Store(database_url)` lưu normalized outputs,
   case/run pins, toàn bộ input/output và DTO lineage của bước 5–7.

Mapper C05/C06/chunks, provider/review tách biệt, C07/C08 và C10/C11 đã triển khai.
`compliance.service.evaluate_compliance` chỉ xử lý compliance-sourced risks/actions;
`workflows.steps_5_7.evaluate` nhận C09 để tạo full pipeline. `DraftAssessmentWorkflow`
ghép upstream được inject; runner nhóm C hỗ trợ offline/replay/save/read/export.
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

#### Điểm đặt implementation

C07/C08 đã có provider, reasoner, grounding, aggregation và service trong
`modules/compliance/`; runner nhóm C mặc định offline, không gọi API trả phí.
Xem [README compliance](../backend/src/legal_checker/modules/compliance/README.md)
để chạy theo checklist, cấu hình OpenAI tùy chọn và thực hiện review/replay.

```text
modules/compliance/observations.py             Interface cung cấp Observation
modules/compliance/criterion_reasoner.py       Triển khai kiểm tra số liệu/nội dung ở đây hoặc helper do nhóm C bổ sung
modules/compliance/criterion_reasoner.py       reason(request, knowledge) → C07
modules/compliance/requirement_aggregator.py   aggregate(context, knowledge, C07, C05) → C08
modules/compliance/grounding_validator.py      Kiểm tra handoff/provenance
```

Policy `AGG_CAN_HO_V1` đã triển khai theo knowledge: chưa confirmed/thiếu rule/thiếu findings → INSUFFICIENT;
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
`policy.py`, `service.py`. C10 hiện hỗ trợ COMPLIANCE / CITATION / VERIFICATION.
UNKNOWN/chưa xác minh cần luồng yêu cầu thông tin phù hợp; không được biến thành
một kết luận vi phạm đã xác nhận.

### 6.4 Bước 7: Recommendation → C11

**Nhận:** C10 đã xác định + risk/template mappings + context/evidence/legal basis.
**Trả:** `list[Recommendation]` (C11), chờ review.

Đọc `knowledge.rui_ro_khuyen_nghi`, `danh_muc_khuyen_nghi`, criterion/requirement
và context liên quan. Ghi `runtime.khuyen_nghi_danh_gia`.

1. Theo `risk.rui_ro_id` tìm link → template; không viết một câu chung cho mọi risk.
2. Giữ action/priority/severity và các `required_elements_json`/`gioi_han_sinh_json`.
3. Template engine đã tạo nội dung theo policy ALL cho mọi mapped template. Nếu bổ sung LLM, chỉ cá thể hóa
   câu chữ từ facts/basis đã có; không tự tạo luật, ngày, số tiền hoặc danh tính.
4. UNKNOWN/chưa đủ căn cứ → yêu cầu xác minh đúng dữ kiện còn thiếu.
5. Validate C11: cùng risk ID, legal basis/evidence, template và knowledge/rule version.
6. Lưu nội dung, action, priority và snapshots; giữ review PENDING.

`Recommendation.model_version` hiện bị giới hạn `TEMPLATE_ENGINE_NO_LLM`,
`prompt_version` là `NOT_USED`; generator/validator đã kiểm tra mapping, C10 instance,
required elements/facts, constraints, evidence/legal basis và priority theo contract.
Policy/template/fact chưa hỗ trợ giữ diagnostics, không chọn template đầu hoặc tự bịa dữ kiện.
Muốn có LLM-generated C11 cần cập nhật contract/version/validator/tests có chủ đích;
không ghi output LLM nhưng để metadata “NO_LLM”.

#### Hai entrypoint đã triển khai cần phân biệt

- `evaluate_compliance` trong `compliance/service.py` phục vụ handoff compliance-only:
  C07/C08 + risks/actions chỉ từ compliance. `ComplianceOutput` không nhận citation-sourced risks.
- `workflows/steps_5_7.evaluate` nhận cả C09 và hợp nhất hai nhánh để trả C07–C11 đầy đủ.

Nếu nhóm C hiện phụ trách toàn bộ 5–7, dùng luồng đầy đủ. Nhóm D lấy C10/C11 đã hợp nhất
để làm report; không tạo lại citation risks/recommendations một lần nữa.

### 6.5 LLM và audit: khi nào cần?

Không bắt buộc LLM cho mọi criterion. Numeric rules, C08, C10 và C11 chạy deterministic;
C07 có semantic provider và OpenAI client tùy chọn. Prompt/schema/provider thuộc module;
`shared/llm` có transport/config/types và `audit_llm_call`/`PostgresLlmAuditSink` cho X02.
Runner nhóm C không tạo paid client; muốn dùng LLM-generated C11 phải đổi contract có
chủ đích. [Ví dụ dùng audit](llm_audit.md).

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
criterion ID. `citation_mapper.py` đã đọc rule nhánh CITATION, các ID `RULE_CITATION_*`
và guards tương ứng. Thiếu C09 provenance có diagnostic, STALE/INVALID không tạo risk
khẳng định; UNKNOWN chỉ tạo VERIFICATION khi policy cho phép. Không tự gán pins còn thiếu.

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

`new_run` chỉ là helper đổi identity cho dữ liệu thử nghiệm, không cấp verification,
review hoặc provenance cho run mới. Review, external registry và C09 source snapshot
gắn với run/digest cũ không được tự đổi pins để nhận là đã xác minh. Adapter upstream
phải cung cấp provenance đáng tin cho context mới; C07 legacy thiếu context/contract/hash
bị từ chối, còn C09 thiếu provenance giữ diagnostics và không tạo risk khẳng định.

Implementation hiện xử lý observations rỗng bằng UNKNOWN và uncertainty cụ thể, giữ
toàn bộ criteria của version resolved và requirement chưa resolve trong C08. Provider
theo `ObservationProvider.observe` phải giữ nguồn/gates thực tế. Khi test
Risk riêng, C07/C09 reference được phép là upstream; khi test Reasoning thì C07 là expected.

Runner `legal_checker.modules.assessments.run_group_c` đã hỗ trợ offline/replay,
`--save`, `--read-run` và export atomic vào thư mục mới. Metadata/hash/counts/lineage
phản ánh DTO thật; read kiểm tra dữ liệu đã lưu và không chạy lại engines. Xem
[lệnh PowerShell](../backend/src/legal_checker/modules/compliance/README.md#runner-nhóm-c-bước-57)
và [bàn giao nhóm C](group_c_handoff.md). Không dùng observations/EXPECTED đã seed
làm kết quả của provider mới rồi báo metric pass.

**Bàn giao nhóm C:** C07/C08/C10/C11 cùng Context/run/hash, rows + DTO lineage đã lưu,
observations/provider thật, nguồn/chứng từ/gates và cách gọi. Nhóm D chỉ đọc các outputs
đã hợp nhất; không chạy lại reasoning/risk để đổi đáp án khi render report.

