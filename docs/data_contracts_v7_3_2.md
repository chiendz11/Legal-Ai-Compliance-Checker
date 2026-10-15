# DATA CONTRACTS GIỮA CÁC MODULE
## AI Legal Compliance Checker
### Baseline: BRD v1.1 + Data Model v7.3.2

**Mục đích tài liệu:** chuẩn hóa interface dữ liệu giữa các module để các thành viên có thể phát triển độc lập nhưng vẫn ghép được thành pipeline end-to-end.

**Nguồn sử dụng**
- `BRD_AI_Legal_Compliance_Checker_v1.1(1).pdf`
- `bang_du_lieu_runtime_v7_3_KNOWLEDGE_REAL (2).xlsx`
- Sheet kỹ thuật chính trong workbook: `MODULE_READ_WRITE`, các bảng runtime và knowledge liên quan.

> Lưu ý: Contract trong tài liệu này là **logical/API contract**. Phần lớn contract đã có bảng persistence tương ứng trong v7.3.x, vì vậy **không cần tạo thêm một bảng DB cho mỗi contract**. Một số field được đề xuất thêm ở tầng API/schema dù DB hiện tại có thể tạm lưu trong JSON snapshot.

---

# 1. Nguyên tắc thiết kế contract

Một contract không chỉ là danh sách tên cột. Mỗi contract phải xác định:

1. **Producer** — module nào tạo dữ liệu.
2. **Consumer** — module nào được phép đọc và phụ thuộc vào dữ liệu.
3. **Persistent representation** — bảng DB nào lưu kết quả.
4. **Required fields** — field bắt buộc.
5. **Optional fields** — field có thể `null`.
6. **Enum** — tập giá trị hợp lệ.
7. **Validation rules / gate** — điều kiện để downstream được sử dụng record.
8. **Provenance** — record phải truy ngược được về evidence, legal source và version.
9. **Versioning** — schema/rule/model/knowledge version phải truy vết được.
10. **Uncertainty policy** — thiếu dữ liệu phải giữ `UNKNOWN/INSUFFICIENT`, không tự suy diễn.

Nguyên tắc kiến trúc quan trọng nhất:

```text
Module A
   |
   | produce contract
   v
Persistent table / API payload
   |
   | consume contract
   v
Module B
```

Module B **không được phụ thuộc vào implementation nội bộ** của Module A.

Ví dụ Reasoning không cần biết Retrieval đang dùng BM25, pgvector, Qdrant hay reranker nào. Reasoning chỉ phụ thuộc vào `RetrievalEvidenceContract`.

---

# 2. Hai nhánh nghiệp vụ phải tách độc lập

BRD xác định hai nhánh:

```text
                     DOCUMENT INTELLIGENCE
                            |
               +------------+------------+
               |                         |
               v                         v
      A. APPLICABLE LAW        B. CITATION VALIDATION
               |                         |
      Scope + Temporal          Validate citations
               |                         |
      Retrieval + Reasoning              |
               |                         |
      Compliance Result                  |
               |                         |
               +------------+------------+
                            |
                            v
                     RISK AGGREGATION
                            |
                     RECOMMENDATION
                            |
                         REPORT
```

Quy tắc:

```text
VALID citation != COMPLIANT contract
STALE citation != NON_COMPLIANT contract
INVALID citation != requirement bị loại khỏi checklist
```

Citation chỉ hội tụ với compliance ở **Risk Aggregation** và **Report**.

---

# 3. Tổng quan các contract

| ID | Contract | Producer | Consumer | Persistence chính |
|---|---|---|---|---|
| C01 | Assessment Case Contract | Intake / Backend | Document Intelligence | `ca_danh_gia`, `hop_dong`, `tep_nguon` |
| C02 | Contract Profile Contract | Document Intelligence | Scope Resolver, Temporal Resolver | `ho_so_hop_dong`, `chu_the_hop_dong`, `trich_xuat_truong`, `bang_chung_truong`, `moc_thoi_gian_hop_dong` |
| C03 | Contract Citation Extraction Contract | Document Intelligence | Citation Validator | `vien_dan_phap_ly_hop_dong`, `bang_chung_vien_dan` |
| C04 | Scope Resolution Contract | Scope Resolver | Temporal Resolver | `yeu_cau_ap_dung` |
| C05 | Applicable Requirement Contract | Temporal Resolver | Retrieval, Reasoning | `yeu_cau_ap_dung` |
| C06 | Retrieval Evidence Contract | Retrieval | Compliance Reasoning | `ket_qua_truy_xuat` |
| C07 | Criterion Reasoning Contract | Compliance Reasoning | Rule Aggregator, Risk Engine | `ket_qua_tieu_chi`, `bang_chung_ket_qua`, `bang_chung_ngoai` |
| C08 | Requirement Aggregation Contract | Rule Aggregator | Risk, Report/UI | `ket_qua_tuan_thu` |
| C09 | Citation Validation Contract | Citation Validator | Risk Engine, Report | `phat_hien_vien_dan` |
| C10 | Risk Contract | Risk Engine | Recommendation, Report | `ket_qua_rui_ro` |
| C11 | Recommendation Contract | Recommendation | Human Review, Report | `khuyen_nghi_danh_gia` |
| C12 | Human Review Contract | Reviewer | Report Publisher | `nhat_ky_review`, `phan_quyen_danh_gia` |
| C13 | Final Report Contract | Report Builder | UI / Export | `bao_cao_danh_gia` |
| X01 | Deployment & Knowledge Snapshot Contract | Knowledge/Release | Tất cả module | `phien_ban_trien_khai`, `ca_danh_gia` |
| X02 | LLM Audit Contract | Module gọi LLM | Audit / Observability | `nhat_ky_goi_llm` |

---

# 4. Common Contract Envelope

Khi truyền qua REST, queue hoặc function call, các contract nên dùng envelope chung:

```json
{
  "contract_name": "ApplicableRequirement",
  "contract_version": "1.0",
  "ca_id": "CA_001",
  "phien_ban_id": "DEPLOY_20261010",
  "rule_version": "RULE_20261010",
  "legal_knowledge_version": "LEGAL_20261010",
  "run_id": "RUN_001",
  "trace_id": "TRACE_001",
  "produced_at": "2026-10-10T12:00:00+07:00",
  "payload": {}
}
```

### Quy tắc

- `contract_name`: tên logical schema.
- `contract_version`: version interface, **khác** version model.
- `ca_id`: assessment case.
- `phien_ban_id`: deployment snapshot.
- `rule_version`: version rules.
- `legal_knowledge_version`: snapshot tri thức pháp lý.
- `run_id`: một lần chạy module/pipeline.
- `trace_id`: nối log xuyên module.

DB không nhất thiết phải lưu toàn bộ envelope ở mọi bảng; các field có thể được pin qua `ca_danh_gia`, `phien_ban_trien_khai`, `lan_chay_id` và audit log.

---

# 5. C01 — Assessment Case Contract

## 5.1 Producer / Consumer

```text
Intake / Backend
      |
      v
Assessment Case Contract
      |
      v
Document Intelligence
```

## 5.2 Persistence

- `ca_danh_gia`
- `hop_dong`
- `tep_nguon`

### `ca_danh_gia` hiện có

```text
ca_id
hop_dong_id
moc_ap_dung
ngay_danh_gia
trang_thai
phien_ban_id
loai_moc_ap_dung
profile_snapshot_json
loai_du_lieu
rule_version
legal_knowledge_version
tenant_id
created_by
```

## 5.3 Payload đề xuất

```json
{
  "ca_id": "CA001",
  "hop_dong_id": "HD001",
  "source": {
    "tep_id": "TEP001",
    "url_nguon": null,
    "object_uri": "s3://bucket/contracts/HD001.pdf",
    "mime_type": "application/pdf",
    "sha256": "..."
  },
  "assessment_context": {
    "ngay_danh_gia": "2026-10-10",
    "moc_ap_dung": null,
    "loai_moc_ap_dung": null
  },
  "deployment": {
    "phien_ban_id": "DEPLOY001",
    "rule_version": "RULE001",
    "legal_knowledge_version": "LEGAL001"
  },
  "tenant_id": "TENANT001",
  "created_by": "USER001"
}
```

## 5.4 Validation

Bắt buộc:

```text
ca_id != null
hop_dong_id != null
phien_ban_id != null
rule_version != null
legal_knowledge_version != null
```

Ít nhất một nguồn file phải truy cập được:

```text
object_uri != null
OR url_nguon != null
```

Một assessment đã bắt đầu không được âm thầm đổi:

```text
phien_ban_id
rule_version
legal_knowledge_version
```

---

# 6. C02 — Contract Profile Contract

## 6.1 Producer / Consumer

```text
Document Intelligence
      |
      +--------------------+
      v                    v
Scope Resolver       Temporal Resolver
```

## 6.2 Persistence

- `ho_so_hop_dong`
- `chu_the_hop_dong`
- `trich_xuat_truong`
- `bang_chung_truong`
- `bang_chung_ho_so`
- `moc_thoi_gian_hop_dong`
- `doan_hop_dong`

## 6.3 Contract profile fields chính

Workbook v7.3.x hiện đã có các nhóm field:

### Identity / domain

```text
loai_hop_dong_id
doi_tuong
linh_vuc
he_phap_luat
muc_dich_giao_dich
```

### Temporal

```text
ngay_giao_ket
ngay_giao_ket_raw
do_chinh_xac_ngay
trang_thai_ngay
loai_moc_ap_dung
ngay_hieu_luc_hop_dong
ngay_ban_giao_du_kien
```

### Subject/context

```text
quan_he_chu_the
ben_ban_co_von_nuoc_ngoai
ben_ban_la_chu_dau_tu
ben_ban_la_ca_nhan
ben_mua_la_ca_nhan
```

### Transaction/object

```text
gia_tri_hop_dong
don_vi_tien
tinh_trang_tai_san
la_nha_o_xa_hoi
la_hop_dong_theo_mau
la_nha_xay_moi
che_do_giao_dich
muc_dich_su_dung_can_ho
```

## 6.4 Payload đề xuất

```json
{
  "hop_dong_id": "HD001",
  "profile": {
    "loai_hop_dong_id": "MB_CAN_HO_CHUNG_CU",
    "doi_tuong": "Căn hộ chung cư",
    "linh_vuc": "NHA_O",
    "he_phap_luat": "VIET_NAM",
    "muc_dich_giao_dich": "TIEU_DUNG_KHONG_THUONG_MAI",

    "ngay_giao_ket": "2026-01-15",
    "ngay_hieu_luc_hop_dong": "2026-01-15",
    "ngay_ban_giao_du_kien": null,

    "gia_tri_hop_dong": 2200000000,
    "don_vi_tien": "VND",

    "la_hop_dong_theo_mau": true,
    "la_nha_o_xa_hoi": false,
    "ben_ban_la_chu_dau_tu": true
  },

  "subjects": [
    {
      "chu_the_id": "CT001",
      "vai_tro": "BEN_BAN",
      "ten_chu_the": "Công ty A",
      "loai_chu_the": "DOANH_NGHIEP",
      "la_thuong_nhan": true,
      "la_chu_the_kinh_doanh": true,
      "human_verified": false,
      "doan_bang_chung_id": "D001"
    }
  ],

  "time_markers": [
    {
      "moc_id": "M001",
      "loai_moc": "NGAY_GIAO_KET",
      "gia_tri_raw": "Ngày 15 tháng 01 năm 2026",
      "ngay": "2026-01-15",
      "do_chinh_xac": "NGAY",
      "trang_thai": "EXTRACTED",
      "duoc_dung_phan_giai": true,
      "trich_xuat_id": "TX001"
    }
  ],

  "facts": [
    {
      "trich_xuat_id": "TX001",
      "ten_truong": "BEN_BAN.ten_chu_the",
      "gia_tri_raw": "CÔNG TY A",
      "gia_tri_chuan_json": "Công ty A",
      "trang_thai": "TRICH_XUAT_TU_TEXT",
      "phuong_phap": "RULE_LLM",
      "human_verified": false,
      "evidence_ids": ["BC001"]
    }
  ]
}
```

## 6.5 Provenance bắt buộc

Không được chỉ truyền:

```json
{
  "ben_ban_la_chu_dau_tu": true
}
```

mà phải truy được:

```text
profile fact
   ↓
trich_xuat_truong
   ↓
bang_chung_truong
   ↓
doan_hop_dong
   ↓
page / source document
```

## 6.6 Uncertainty

Nếu không chắc:

```text
null / UNKNOWN
```

Không được ép thành `false`.

Ví dụ:

```text
BEN_BAN.la_chu_the_kinh_doanh = UNKNOWN
```

thì Scope Resolver phải giữ uncertainty.

---

# 7. C03 — Contract Citation Extraction Contract

## 7.1 Producer / Consumer

```text
Document Intelligence
       |
       v
Citation Validator
```

## 7.2 Persistence hiện có

- `vien_dan_phap_ly_hop_dong`
- `bang_chung_vien_dan`
- `doan_hop_dong`

### `vien_dan_phap_ly_hop_dong`

```text
vien_dan_id
hop_dong_id
so_hieu
ten_van_ban
noi_dung_vien_dan_mau
trang_thai_trich_xuat
loai_du_lieu
```

## 7.3 Payload đề xuất

```json
{
  "vien_dan_id": "VD001",
  "hop_dong_id": "HD001",

  "raw_text": "Căn cứ Thông tư 02/2016/TT-BXD ...",

  "normalized": {
    "so_hieu": "02/2016/TT-BXD",
    "ten_van_ban": "Thông tư ...",
    "loai_van_ban": "THONG_TU",
    "nam": 2016,
    "ngay_ban_hanh": null,
    "dieu": null,
    "khoan": null
  },

  "extraction": {
    "status": "EXTRACTED",
    "confidence": 0.94
  },

  "evidence": [
    {
      "doan_id": "D001",
      "page_start": 3,
      "page_end": 3
    }
  ]
}
```

## 7.4 Gap cần chốt

DB hiện tại chưa có first-class field:

```text
loai_van_ban
nam
ngay_ban_hanh
dieu
khoan
confidence
```

### Khuyến nghị

**Không bắt buộc tạo bảng mới.**

Có hai lựa chọn:

**A. Bổ sung column vào `vien_dan_phap_ly_hop_dong`** — tốt nếu thường xuyên query/filter.

**B. Giữ DB hiện tại, schema API có `normalized` object** — tốt cho MVP; sau này migrate khi ổn định.

---

# 8. C04 — Scope Resolution Contract

## 8.1 Producer / Consumer

```text
Scope Resolver
     |
     v
Temporal Resolver
```

## 8.2 Input theo `MODULE_READ_WRITE`

Scope Resolver đọc:

```text
ho_so_hop_dong
chu_the_hop_dong
loai_hop_dong
pham_vi_ap_dung
yeu_cau_phap_ly
v_do_phu_requirement
```

Và ghi:

```text
yeu_cau_ap_dung
```

## 8.3 Logical contract

```json
{
  "yeu_cau_ca_id": "YCCA001",
  "ca_id": "CA001",

  "requirement_id": "FAM_PAYMENT_METHOD_DEADLINE",
  "nhom_phien_ban": "BVNTD",

  "scope_status": "MATCH",

  "profile_snapshot_json": {},
  "dieu_kien_snapshot_json": {},

  "scope_reason": "Loại hợp đồng, chủ thể và mục đích giao dịch thỏa điều kiện..."
}
```

## 8.4 Enum

```text
MATCH
NO_MATCH
UNKNOWN
```

## 8.5 Rule

```text
UNKNOWN != NO_MATCH
```

Nếu fact cần thiết chưa biết:

```text
BEN_BAN.la_chu_the_kinh_doanh = UNKNOWN
```

thì:

```text
scope_status = UNKNOWN
```

không được đoán `NO_MATCH`.

## 8.6 Independence rule

Scope **không lấy checklist từ citation**.

```text
vien_dan_phap_ly_hop_dong
      X
      |
      v
Scope Resolver
```

Citation có thể là tín hiệu bổ trợ khi thiết kế policy, nhưng không được là nguồn duy nhất quyết định applicable law.

---

# 9. C05 — Applicable Requirement Contract

## 9.1 Producer / Consumer

```text
Temporal Resolver
      |
      +------------+
      v            v
Retrieval       Reasoning
```

## 9.2 Persistence

`yeu_cau_ap_dung`

### Columns hiện tại

```text
yeu_cau_ca_id
ca_id
requirement_id
nhom_phien_ban
requirement_version_id
scope_status
version_status
applicability_status
moc_id
loai_moc
moc_ap_dung
resolution_method
profile_snapshot_json
dieu_kien_snapshot_json
nguon_snapshot_json
phien_ban_id
ly_do
loai_du_lieu
```

## 9.3 Payload

```json
{
  "yeu_cau_ca_id": "YCCA001",
  "ca_id": "CA001",

  "requirement_id": "FAM_PAYMENT_METHOD_DEADLINE",
  "requirement_version_id": "PV_GYC008",
  "nhom_phien_ban": "BVNTD",

  "scope_status": "MATCH",
  "version_status": "RESOLVED",
  "applicability_status": "CONFIRMED",

  "moc_id": "M001",
  "loai_moc": "NGAY_GIAO_KET",
  "moc_ap_dung": "2026-01-15",

  "resolution_method": "TEMPORAL_RANGE",

  "profile_snapshot_json": {},
  "dieu_kien_snapshot_json": {},
  "nguon_snapshot_json": {},

  "phien_ban_id": "DEPLOY001",

  "reason": {
    "scope": "...",
    "temporal": "PV_GYC008 có hiệu lực tại relevant date..."
  }
}
```

## 9.4 Enum

### `scope_status`

```text
MATCH
NO_MATCH
UNKNOWN
```

### `version_status`

```text
RESOLVED
UNKNOWN
```

### `applicability_status`

```text
CONFIRMED
NOT_APPLICABLE
UNKNOWN
```

## 9.5 Gate cho Retrieval

Normal retrieval chỉ chạy khi:

```text
scope_status == MATCH
AND version_status == RESOLVED
AND applicability_status == CONFIRMED
```

Nếu không resolve version:

```text
version_status = UNKNOWN
applicability_status = UNKNOWN
```

và downstream phải đi uncertainty path.

## 9.6 Gap

DB hiện chỉ có:

```text
ly_do
```

nhưng logic có hai provenance:

```text
scope_reason
temporal_reason
```

### Khuyến nghị

Ở API contract:

```json
"reason": {
  "scope": "...",
  "temporal": "..."
}
```

DB MVP có thể serialize vào `ly_do`; về sau cân nhắc tách column.

---

# 10. C06 — Retrieval Evidence Contract

## 10.1 Producer / Consumer

```text
Retrieval
   |
   v
Compliance Reasoning
```

## 10.2 Input theo workbook

```text
yeu_cau_ap_dung
tieu_chi_danh_gia
phien_ban_yeu_cau
doan_hop_dong
fts_doan
embedding_doan_hop_dong
```

## 10.3 Persistence

`ket_qua_truy_xuat`

### Columns hiện tại

```text
truy_xuat_id
yeu_cau_ca_id
doan_id
giai_doan
bm25_score
vector_score
rerank_score
thu_hang
query_text
retrieval_version
embedding_model
index_version
rerank_model
ngay_truy_xuat
loai_du_lieu
tieu_chi_id
duoc_chon
lan_chay_id
```

## 10.4 Payload

```json
{
  "truy_xuat_id": "RTX001",
  "yeu_cau_ca_id": "YCCA001",
  "tieu_chi_id": "TC001",

  "doan_id": "D001",
  "giai_doan": "FINAL",

  "scores": {
    "bm25": 3.92,
    "vector": 0.83,
    "rerank": 0.91
  },

  "thu_hang": 1,
  "duoc_chon": true,

  "query_text": "...",

  "retrieval_version": "RET_V1",
  "embedding_model": "BGE_M3",
  "index_version": "IDX_20261010",
  "rerank_model": "RERANK_V1",

  "lan_chay_id": "RUN001"
}
```

## 10.5 Rule quan trọng

```text
Không tìm được evidence != VIOLATED
Không tìm được evidence != MISSING
```

Retrieval chỉ trả candidate/evidence status.

Reasoning mới được phép kết luận `MISSING`, sau khi kiểm tra evidence coverage và policy.

---

# 11. C07 — Criterion Reasoning Contract

## 11.1 Producer / Consumer

```text
Compliance Reasoning
       |
       +----------------+
       v                v
Rule Aggregator     Risk Engine
```

## 11.2 Persistence

- `ket_qua_tieu_chi`
- `bang_chung_ket_qua`
- `bang_chung_ngoai`

## 11.3 Columns hiện tại của `ket_qua_tieu_chi`

```text
ket_qua_id
ca_id
tieu_chi_id
giai_thich
model_version
prompt_version
yeu_cau_ca_id
loai_phat_hien
coverage_complete
absence_verified
evidence_validated
tieu_chi_snapshot_json
ngay_danh_gia
loai_du_lieu
uncertainty_reason
pham_vi_ket_luan
lan_chay_id
review_status
source_verified
scope_confirmed
version_resolved
evidence_conflict
exceptions_resolved
```

## 11.4 Payload

```json
{
  "ket_qua_id": "KQ001",
  "ca_id": "CA001",
  "yeu_cau_ca_id": "YCCA001",
  "tieu_chi_id": "TC001",

  "finding": "MISSING",
  "giai_thich": "...",

  "gates": {
    "coverage_complete": true,
    "absence_verified": true,
    "evidence_validated": true,
    "source_verified": true,
    "scope_confirmed": true,
    "version_resolved": true,
    "evidence_conflict": false,
    "exceptions_resolved": true
  },

  "uncertainty_reason": null,
  "pham_vi_ket_luan": "CURRENT_CRITERION",

  "evidence": [
    {
      "doan_id": "D001",
      "trich_dan": "...",
      "ky_tu_bat_dau": 100,
      "ky_tu_ket_thuc": 230
    }
  ],

  "external_evidence": [],

  "model_version": "...",
  "prompt_version": "...",
  "lan_chay_id": "RUN001",
  "review_status": "PENDING"
}
```

## 11.5 Enum finding

```text
SATISFIED
MISSING
VIOLATED
UNKNOWN
```

## 11.6 Gate cho `MISSING`

`MISSING` chỉ hợp lệ khi:

```text
coverage_complete = true
absence_verified = true
evidence_validated = true
source_verified = true
scope_confirmed = true
version_resolved = true
exceptions_resolved = true
evidence_conflict = false
```

Pseudo-code:

```python
if finding == "MISSING":
    assert coverage_complete
    assert absence_verified
    assert evidence_validated
    assert source_verified
    assert scope_confirmed
    assert version_resolved
    assert exceptions_resolved
    assert not evidence_conflict
```

## 11.7 Gate cho `VIOLATED`

```text
VIOLATED
= có evidence cho thấy nội dung trái criterion / requirement
```

Không được:

```text
retrieval empty -> VIOLATED
```

## 11.8 Khi nào `UNKNOWN`

Ví dụ:

```text
scope chưa chắc
version chưa resolve
evidence conflict
external document còn thiếu
ngoại lệ chưa resolve
source legal chưa xác minh
```

Khi đó:

```text
finding = UNKNOWN
uncertainty_reason != null
```

---

# 12. C08 — Requirement Aggregation Contract

## 12.1 Producer / Consumer

```text
Rule Aggregator
      |
      v
Risk / Report / UI
```

## 12.2 Persistence

`ket_qua_tuan_thu`

### Columns

```text
tuan_thu_id
yeu_cau_ca_id
nhan
so_tieu_chi_ap_dung
so_tieu_chi_da_danh_gia
so_unknown
rule_version
giai_thich
requirement_snapshot_json
ngay_tong_hop
loai_du_lieu
```

## 12.3 Payload

```json
{
  "tuan_thu_id": "TT001",
  "yeu_cau_ca_id": "YCCA001",

  "status": "PARTIAL",

  "so_tieu_chi_ap_dung": 3,
  "so_tieu_chi_da_danh_gia": 3,
  "so_unknown": 0,

  "rule_version": "AGG_V1",

  "giai_thich": "...",
  "requirement_snapshot_json": {}
}
```

## 12.4 Enum requirement status

```text
COMPLIANT
PARTIAL
NON_COMPLIANT
INSUFFICIENT
```

## 12.5 Rule

`NOT_APPLICABLE` không phải compliance result.

```text
NOT_APPLICABLE
```

thuộc:

```text
C05 — Applicable Requirement Contract
```

chứ không nằm trong `ket_qua_tuan_thu`.

---

# 13. C09 — Citation Validation Contract

## 13.1 Producer / Consumer

```text
Citation Validator
       |
       +----------------+
       v                v
Risk Engine          Report
```

## 13.2 Input

```text
vien_dan_phap_ly_hop_dong
bang_chung_vien_dan
van_ban_phap_ly
quan_he_van_ban
```

## 13.3 Persistence

`phat_hien_vien_dan`

### Columns hiện tại

```text
finding_id
ca_id
vien_dan_id
van_ban_id
trang_thai
ly_do
finding_verified
moc_ap_dung
domain_status
source_snapshot_json
loai_du_lieu
lan_chay_id
knowledge_version
```

## 13.4 Payload

```json
{
  "finding_id": "CF001",
  "ca_id": "CA001",
  "vien_dan_id": "VD001",

  "normalized_van_ban_id": "VBPL001",

  "relevant_date": "2026-01-15",

  "status": "STALE",

  "reason_code": "REPLACED_BEFORE_RELEVANT_DATE",
  "ly_do": "...",

  "domain_status": "MATCH",

  "finding_verified": true,

  "current_status": "REPEALED",
  "replacement_van_ban_id": "VBPL002",

  "source_snapshot_json": {},

  "lan_chay_id": "RUN001",
  "knowledge_version": "LEGAL001"
}
```

## 13.5 Enum

```text
VALID
STALE
INVALID
UNKNOWN
```

## 13.6 Rule

Citation status tại relevant date và current status phải tách.

Ví dụ:

```text
Ngày ký hợp đồng: 2023
Luật A còn hiệu lực năm 2023
Luật A bị thay thế năm 2025

Historical citation status = VALID
Current status = REPEALED / REPLACED
```

Không được gắn `STALE` chỉ vì hiện tại văn bản đã bị thay thế.

## 13.7 Gap

Schema hiện tại chưa first-class hóa:

```text
reason_code
current_status
replacement_van_ban_id
```

MVP có thể lưu trong `source_snapshot_json`, nhưng contract API nên có riêng.

---

# 14. C10 — Risk Contract

## 14.1 Producer / Consumer

```text
Risk Engine
    |
    +------------+
    v            v
Recommendation Report
```

## 14.2 Persistence

`ket_qua_rui_ro`

### Columns hiện tại

```text
ket_qua_id
ca_id
rui_ro_id
giai_thich
quy_tac_id
yeu_cau_ca_id
nguon_tieu_chi_id
nguon_vien_dan_id
severity_snapshot
ten_snapshot
mo_ta_snapshot
rule_snapshot_json
loai_du_lieu
```

## 14.3 Payload

```json
{
  "ket_qua_rui_ro_id": "RISK001",
  "ca_id": "CA001",

  "risk_type": "COMPLIANCE",

  "rui_ro_id": "RR001",
  "severity": "HIGH",

  "source": {
    "yeu_cau_ca_id": "YCCA001",
    "ket_qua_tieu_chi_id": "KQ001",
    "citation_finding_id": null
  },

  "quy_tac_id": "RULE001",

  "giai_thich": "...",

  "risk_snapshot": {
    "ten": "...",
    "mo_ta": "...",
    "severity": "HIGH"
  },

  "rule_snapshot_json": {}
}
```

## 14.4 `risk_type`

Nên dùng tối thiểu:

```text
COMPLIANCE
CITATION
VERIFICATION
```

- `COMPLIANCE`: phát sinh từ criterion/requirement.
- `CITATION`: phát sinh từ Citation Validation.
- `VERIFICATION`: uncertainty/review-required.

## 14.5 Provenance

Mỗi risk phải có **một nguồn cụ thể**:

```text
COMPLIANCE risk
 -> ket_qua_tieu_chi / yeu_cau_ca

CITATION risk
 -> phat_hien_vien_dan

VERIFICATION risk
 -> source UNKNOWN cần human verification
```

## 14.6 Gap

Trong DB hiện tại, `risk_type` thường phải suy từ `rui_ro_id` / rule snapshot.

Khuyến nghị contract luôn truyền:

```json
"risk_type": "CITATION"
```

để downstream không cần suy ngược.

---

# 15. C11 — Recommendation Contract

## 15.1 Producer / Consumer

```text
Recommendation Engine
       |
       v
Human Review / Report
```

## 15.2 Persistence

`khuyen_nghi_danh_gia`

### Columns hiện tại

```text
khuyen_nghi_ca_id
ket_qua_rui_ro_id
khuyen_nghi_id
noi_dung_snapshot
loai_hanh_dong
uu_tien
dieu_kien_snapshot
trang_thai
loai_du_lieu
model_version
prompt_version
evidence_ids_json
legal_basis_ids_json
review_status
rule_version
template_snapshot_json
knowledge_snapshot_sha256
```

## 15.3 Payload

```json
{
  "khuyen_nghi_ca_id": "KNCA001",
  "ket_qua_rui_ro_id": "RISK001",
  "khuyen_nghi_id": "KN001",

  "noi_dung": "Bổ sung ...",

  "loai_hanh_dong": "ADD",
  "uu_tien": "HIGH",

  "dieu_kien_snapshot": {},

  "evidence_ids": ["D001"],
  "legal_basis_ids": [
    "PV_GYC001",
    "DKPL001"
  ],

  "template_snapshot_json": {},

  "rule_version": "RULE001",
  "knowledge_snapshot_sha256": "...",

  "model_version": "...",
  "prompt_version": "...",

  "review_status": "PENDING"
}
```

## 15.4 Rule

Recommendation **không được chỉ map từ status**.

Sai:

```text
MISSING -> "Bổ sung điều khoản"
```

Đúng:

```text
requirement
+ criterion
+ finding
+ risk
+ evidence
+ legal basis
+ context
        |
        v
recommendation
```

Với:

```text
SATISFIED
VALID
```

recommendation khắc phục có thể `null`.

---

# 16. C12 — Human Review Contract

## 16.1 Producer / Consumer

```text
Human Reviewer
      |
      v
Report Publisher / Effective Result
```

## 16.2 Persistence

- `nhat_ky_review`
- `phan_quyen_danh_gia`

### `nhat_ky_review`

```text
review_id
ca_id
doi_tuong_loai
doi_tuong_id
actor_id
hanh_dong
gia_tri_truoc_json
gia_tri_sau_json
ly_do
ngay_review
phien_ban_id
```

## 16.3 Payload

```json
{
  "review_id": "REV001",
  "ca_id": "CA001",

  "target": {
    "doi_tuong_loai": "ket_qua_tieu_chi",
    "doi_tuong_id": "KQ001"
  },

  "actor_id": "LEGAL_REVIEWER_01",

  "action": "CONFIRM",

  "before": {},
  "after": {},

  "reason": "...",
  "reviewed_at": "2026-10-10T12:00:00+07:00",

  "phien_ban_id": "DEPLOY001"
}
```

## 16.4 Enum action đề xuất

```text
CONFIRM
OVERRIDE
REQUEST_MORE_EVIDENCE
REJECT
COMMENT
```

## 16.5 Audit rule

Không được sửa đè AI result rồi mất lịch sử.

```text
AI result
   +
Review Event
   =
Effective Reviewed Result
```

---

# 17. C13 — Final Report Contract

## 17.1 Producer / Consumer

```text
Report Builder
      |
      v
UI / PDF / Export / API
```

## 17.2 Persistence

`bao_cao_danh_gia`

### Columns hiện tại

```text
bao_cao_id
ca_id
phien_ban_bao_cao
report_json
so_yeu_cau_ung_vien
so_yeu_cau_da_phan_giai
so_yeu_cau_da_danh_gia
mau_so_score
score_method
report_uri
model_version
prompt_version
ngay_tao
loai_du_lieu
report_status
review_status
so_unknown
coverage_ratio
knowledge_snapshot_sha256
rule_version
```

## 17.3 `report_json` schema đề xuất

```json
{
  "case": {},

  "contract_profile": {},

  "applicable_legal_scope": [],

  "checklist": [],

  "compliance": {
    "requirement_results": [],
    "criterion_results": [],
    "evidence": [],
    "legal_basis": []
  },

  "citation_validation": {
    "citations": [],
    "findings": []
  },

  "risks": {
    "compliance": [],
    "citation": [],
    "verification": []
  },

  "recommendations": [],

  "overall_summary": {
    "candidate_requirement_count": 10,
    "resolved_requirement_count": 9,
    "evaluated_requirement_count": 8,
    "unknown_count": 2,
    "coverage_ratio": 0.8,
    "score": null
  },

  "audit": {
    "phien_ban_id": "DEPLOY001",
    "schema_version": "1.0",
    "rule_version": "RULE001",
    "knowledge_snapshot_sha256": "...",
    "model_version": "...",
    "prompt_version": "..."
  }
}
```

## 17.4 Report phải tách hai nhánh

```text
Compliance
  - requirement results
  - criterion results
  - compliance risks

Citation Validation
  - contract citations
  - citation findings
  - citation risks
```

Sau đó mới có:

```text
Overall Risk Summary
```

Không flatten tất cả thành một status duy nhất.

---

# 18. X01 — Deployment & Knowledge Snapshot Contract

## 18.1 Producer / Consumer

```text
Knowledge Curation / Release
          |
          v
All Runtime Modules
```

## 18.2 Persistence

- `phien_ban_trien_khai`
- snapshot fields trong `ca_danh_gia`

### `phien_ban_trien_khai`

```text
phien_ban_id
ten_phien_ban
ngay_tao
legal_snapshot_sha256
contract_snapshot_sha256
schema_version
model_reasoning
model_embedding
prompt_version
ghi_chu
loai_du_lieu
```

## 18.3 Payload

```json
{
  "phien_ban_id": "SNAPSHOT_V732_20261007",
  "schema_version": "v7.3.2",

  "legal_snapshot_sha256": "...",
  "contract_snapshot_sha256": "...",

  "model_reasoning": "...",
  "model_embedding": "...",
  "prompt_version": "...",

  "rule_version": "..."
}
```

## 18.4 Reproducibility rule

Một `ca_danh_gia` phải pin snapshot:

```text
ca_danh_gia.phien_ban_id
ca_danh_gia.rule_version
ca_danh_gia.legal_knowledge_version
```

Sau khi assessment bắt đầu:

```text
knowledge update
```

không được làm thay đổi âm thầm kết quả case cũ.

Muốn chạy theo knowledge mới:

```text
re-run / new report version
```

---

# 19. X02 — LLM Audit Contract

## 19.1 Producer

Bất kỳ module nào thực sự gọi LLM:

```text
Document Intelligence
Compliance Reasoning
Recommendation
...
```

## 19.2 Persistence

`nhat_ky_goi_llm`

### Columns hiện tại

```text
lan_goi_id
ca_id
module
provider
model_version
prompt_version
schema_version
input_sha256
output_sha256
input_tokens
output_tokens
latency_ms
chi_phi
don_vi_tien
trang_thai
ma_loi
so_lan_thu
trace_id
ngay_goi
loai_du_lieu
```

## 19.3 Payload

```json
{
  "lan_goi_id": "LLM001",
  "ca_id": "CA001",
  "module": "COMPLIANCE_REASONING",

  "provider": "OPENAI",
  "model_version": "...",
  "prompt_version": "...",
  "schema_version": "CriterionReasoning/1.0",

  "input_sha256": "...",
  "output_sha256": "...",

  "input_tokens": 4200,
  "output_tokens": 900,

  "latency_ms": 1800,
  "chi_phi": 0.03,
  "don_vi_tien": "USD",

  "trang_thai": "SUCCESS",
  "ma_loi": null,
  "so_lan_thu": 1,

  "trace_id": "TRACE001",
  "ngay_goi": "2026-10-10T12:00:00+07:00"
}
```

Lưu ý: module chạy rule thuần không cần giả mạo một lần gọi LLM thật.

---

# 20. Dataflow hoàn chỉnh sau khi gắn contract

```text
                          C01
User Upload ─────────────────────────► Document Intelligence
                                           |
                         +-----------------+-----------------+
                         |                                   |
                        C02                                 C03
                         |                                   |
                         v                                   v
                  Scope Resolver                    Citation Validator
                         |                                   |
                        C04                                 C09
                         |                                   |
                         v                                   |
                Temporal Resolver                            |
                         |                                   |
                        C05                                  |
                         |                                   |
                         v                                   |
                     Retrieval                               |
                         |                                   |
                        C06                                  |
                         |                                   |
                         v                                   |
              Compliance Reasoning                           |
                         |                                   |
                        C07                                  |
                    +----+----+                              |
                    |         |                              |
                    v         v                              |
             Rule Aggregator  Risk Engine ◄──────────────────+
                    |             |
                   C08           C10
                    |             |
                    |             v
                    |      Recommendation
                    |             |
                    |            C11
                    +------┬------+
                           |
                           v
                       Human Review
                           |
                          C12
                           |
                           v
                      Final Report
                           |
                          C13
                           |
                           v
                        UI / PDF
```

Cross-cutting:

```text
X01 Deployment/Knowledge Snapshot -> mọi module
X02 LLM Audit -> mọi module gọi LLM
```

---

# 21. Mapping với `MODULE_READ_WRITE` của v7.3.x

Workbook hiện định nghĩa:

| Module | Bảng đọc chính | Bảng ghi chính |
|---|---|---|
| Document Intelligence | `hop_dong`, `tep_nguon` | `doan_hop_dong`, `ho_so_hop_dong`, `chu_the_hop_dong`, `trich_xuat_truong`, `bang_chung_truong`, `moc_thoi_gian_hop_dong`, `vien_dan_phap_ly_hop_dong`, `bang_chung_vien_dan` |
| Scope Resolver | hồ sơ + chủ thể + scope knowledge | `yeu_cau_ap_dung` |
| Temporal Resolver | versions + legal docs + relations + time markers | `yeu_cau_ap_dung` |
| Citation Validator | contract citations + legal DB | `phat_hien_vien_dan` |
| Retrieval | applicable requirements + criteria + chunks/index | `ket_qua_truy_xuat` |
| Compliance Reasoning | retrieval + evidence policy + exceptions | `ket_qua_tieu_chi`, `bang_chung_ket_qua`, `bang_chung_ngoai` |
| Rule Aggregator | aggregation rule + criterion result | `ket_qua_tuan_thu` |
| Risk Engine | criterion/citation findings + risk rules | `ket_qua_rui_ro` |
| Recommendation | risk + evidence + legal basis | `khuyen_nghi_danh_gia` |
| Report / Review | compliance + risk + recommendation + deployment | `bao_cao_danh_gia`, `nhat_ky_review` |
| Knowledge Curation | legal source + audit/gap | `duyet_tri_thuc`, `phien_ban_trien_khai` |

Tài liệu contract ở trên **không thay đổi flow này**; nó formalize interface giữa các hàng trong bảng này.

---

# 22. Contract ownership

Mỗi field phải có đúng một module sở hữu.

Ví dụ:

| Field | Owner | Module khác có được sửa? |
|---|---|---|
| `ho_so_hop_dong.loai_hop_dong_id` | Document Intelligence / human review | Không |
| `yeu_cau_ap_dung.scope_status` | Scope Resolver | Temporal không được đổi |
| `yeu_cau_ap_dung.requirement_version_id` | Temporal Resolver | Retrieval không được đổi |
| `ket_qua_truy_xuat.*score` | Retrieval | Reasoning không được đổi |
| `ket_qua_tieu_chi.loai_phat_hien` | Reasoning | Risk không được đổi |
| `ket_qua_tuan_thu.nhan` | Rule Aggregator | Report không được tự tính lại |
| `phat_hien_vien_dan.trang_thai` | Citation Validator | Risk không được đổi |
| `ket_qua_rui_ro.severity_snapshot` | Risk Engine | Recommendation không được tự nâng severity |
| `khuyen_nghi_danh_gia.noi_dung_snapshot` | Recommendation | Report chỉ render |
| review override | Human Reviewer | Không module AI nào được giả mạo |

---

# 23. Error / uncertainty policy chung

Contract không được dùng `null`, `UNKNOWN`, lỗi retrieval và `NO_MATCH` thay thế lẫn nhau.

## 23.1 Scope unknown

```text
scope_status = UNKNOWN
```

nghĩa là chưa đủ fact để quyết định applicability.

## 23.2 Version unknown

```text
version_status = UNKNOWN
```

nghĩa là chưa chọn được version legal requirement đúng mốc.

## 23.3 Retrieval miss

```text
không có candidate đủ tốt
```

chỉ là retrieval event, **không phải** legal finding.

## 23.4 Criterion unknown

```text
loai_phat_hien = UNKNOWN
```

nghĩa là Reasoning không đủ căn cứ.

## 23.5 Requirement insufficient

```text
nhan = INSUFFICIENT
```

nghĩa là aggregation không đủ cơ sở để kết luận requirement.

## 23.6 Citation unknown

```text
trang_thai = UNKNOWN
```

nghĩa là citation chưa xác minh được; không tự nâng thành `INVALID`.

---

# 24. Versioning contract

Mỗi schema nên có version riêng.

Ví dụ:

```text
ContractProfile/1.0
ApplicableRequirement/1.0
RetrievalEvidence/1.0
CriterionReasoning/1.0
CitationValidation/1.0
RiskResult/1.0
Recommendation/1.0
FinalReport/1.0
```

Breaking change:

```text
1.x -> 2.0
```

Ví dụ breaking:

```text
status: "COMPLIANT"
```

đổi thành object hoàn toàn khác.

Non-breaking:

```text
thêm field optional rerank_score
```

có thể:

```text
1.0 -> 1.1
```

---

# 25. JSON Schema / Pydantic layout đề xuất

Nếu backend Python/FastAPI:

```text
app/
└── contracts/
    ├── common.py
    ├── assessment.py
    ├── document_intelligence.py
    ├── scope.py
    ├── temporal.py
    ├── citation.py
    ├── retrieval.py
    ├── reasoning.py
    ├── aggregation.py
    ├── risk.py
    ├── recommendation.py
    ├── review.py
    └── report.py
```

Ví dụ:

```python
from typing import Literal
from pydantic import BaseModel


class ReasoningGates(BaseModel):
    coverage_complete: bool
    absence_verified: bool
    evidence_validated: bool
    source_verified: bool
    scope_confirmed: bool
    version_resolved: bool
    evidence_conflict: bool
    exceptions_resolved: bool


class CriterionReasoningResult(BaseModel):
    ket_qua_id: str
    ca_id: str
    yeu_cau_ca_id: str
    tieu_chi_id: str

    finding: Literal[
        "SATISFIED",
        "MISSING",
        "VIOLATED",
        "UNKNOWN",
    ]

    giai_thich: str
    gates: ReasoningGates
    uncertainty_reason: str | None = None
```

Validator:

```python
from pydantic import model_validator


class CriterionReasoningResult(BaseModel):
    ...

    @model_validator(mode="after")
    def validate_finding(self):
        if self.finding == "MISSING":
            assert self.gates.coverage_complete
            assert self.gates.absence_verified
            assert self.gates.evidence_validated
            assert self.gates.source_verified
            assert self.gates.scope_confirmed
            assert self.gates.version_resolved
            assert self.gates.exceptions_resolved
            assert not self.gates.evidence_conflict

        if self.finding == "UNKNOWN":
            assert self.uncertainty_reason is not None

        return self
```

---

# 26. Contract testing

Mỗi module cần có contract test riêng.

## 26.1 Scope

```text
Missing required profile fact
-> UNKNOWN
-> không được NO_MATCH
```

## 26.2 Temporal

```text
Mốc trước hieu_luc_tu
-> version đó không được RESOLVED
```

## 26.3 Retrieval

```text
empty result
-> không được tạo VIOLATED
```

## 26.4 Reasoning

```text
finding=MISSING
+ coverage_complete=false
-> schema validation fail
```

## 26.5 Citation

```text
valid tại ngày ký
+ repealed sau ngày ký
-> historical status VALID
-> current status REPEALED
```

## 26.6 Risk

```text
citation finding STALE
-> citation risk
-> không tự thay compliance result
```

## 26.7 Recommendation

```text
UNKNOWN
-> recommendation phải thiên về verify/request evidence
-> không được khẳng định vi phạm
```

---

# 27. Bốn gap cần ưu tiên trước khi code

## P0 — Citation normalization contract

Hiện citation table chưa đủ structured fields cho BRD.

Cần contract hỗ trợ:

```text
document type
number
year/date
article
clause
raw text
position
confidence
```

## P0 — Scope vs Temporal reason

`yeu_cau_ap_dung.ly_do` đang chứa chung.

Contract nên có:

```text
scope_reason
temporal_reason
```

## P0 — Citation validation reason

Cần:

```text
reason_code
current_status
replacement_van_ban_id
```

dù MVP có thể lưu trong snapshot JSON.

## P1 — Risk branch explicit

Contract cần:

```text
risk_type = COMPLIANCE | CITATION | VERIFICATION
```

không để consumer phải JOIN/suy ngược mới biết nguồn risk.

---

# 28. Những bảng không phải contract giữa module

Không phải bảng nào trong DB cũng là module contract.

Ví dụ knowledge tables:

```text
van_ban_phap_ly
dieu_khoan_phap_ly
yeu_cau_phap_ly
phien_ban_yeu_cau
pham_vi_ap_dung
ngoai_le_ap_dung
tieu_chi_danh_gia
quy_tac_quyet_dinh
quy_tac_rui_ro
danh_muc_rui_ro
danh_muc_khuyen_nghi
```

Đây là **knowledge/config inputs**.

Các table như:

```text
embedding_doan_hop_dong
fts_doan
```

là **technical index/storage**, không nên trở thành business contract cho Reasoning.

---

# 29. Contract nào quan trọng nhất cho team

Nếu phải đóng băng trước khi chia việc cho 5 thành viên, ưu tiên:

```text
1. C02 Contract Profile
2. C05 Applicable Requirement
3. C06 Retrieval Evidence
4. C07 Criterion Reasoning
5. C09 Citation Validation
6. C10 Risk
7. C11 Recommendation
8. C13 Final Report
```

Sau khi 8 schema này ổn định, các thành viên có thể code module độc lập.

---

# 30. Kết luận

Với Data Model v7.3.2 và BRD v1.1, kiến trúc không cần tạo thêm hàng loạt bảng mới chỉ để làm “contract”.

Cách phù hợp là:

```text
DB tables = persistent representation
Pydantic/JSON Schema = module interface contract
MODULE_READ_WRITE = ownership/read-write map
BRD = business semantics + acceptance rules
```

Pipeline chuẩn:

```text
Upload
  -> Document Intelligence
  -> Contract Profile
  -> Scope
  -> Temporal
  -> Applicable Requirements
  -> Retrieval
  -> Criterion Reasoning
  -> Requirement Aggregation
  -> Risk
  -> Recommendation
  -> Human Review
  -> Final Report
```

Song song:

```text
Document Intelligence
  -> Contract Citations
  -> Citation Validation
  -> Citation Risk
  -> Risk Aggregation
```

Hai nhánh chỉ hội tụ ở:

```text
Risk Aggregation
Final Report
```

Contract tốt phải bảo đảm ba thứ:

1. **Module sau không cần biết module trước được implement thế nào.**
2. **Mọi kết luận truy ngược được evidence + legal basis + version.**
3. **Thiếu dữ liệu được biểu diễn bằng uncertainty, không bị biến thành kết luận pháp lý giả.**

Đó là nền tảng để hệ thống Legal Compliance Checker ghép được end-to-end, audit được và thay đổi model/rule mà không phá toàn bộ pipeline.
