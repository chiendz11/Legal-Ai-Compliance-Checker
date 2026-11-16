# 04 — Scope & Temporal Resolution (`C04`, `C05`)

> **Tài liệu thẩm quyền liên quan:** [Nhóm B — Legal & Retrieval](../modules/group_b_legal_and_retrieval.md) · [Knowledge Applicability Policy](../contracts/knowledge_applicability_policy.md) · [Legal Version Policy Schema](../contracts/legal_version_policy.schema.json)  
> **Source code trung tâm:** [`scope_resolver.py`](../../backend/src/legal_checker/modules/applicable_law/scope_resolver.py) · [`temporal_resolver.py`](../../backend/src/legal_checker/modules/applicable_law/temporal_resolver.py) · [`catalog_policy.py`](../../backend/src/legal_checker/modules/applicable_law/catalog_policy.py) · [`historical_coverage.py`](../../backend/src/legal_checker/modules/applicable_law/historical_coverage.py)

---

## 1. Tại sao phải tách `C04` (Scope) khỏi `C05` (Temporal), và cả hai khỏi `C03` (Citations)?

Trong catalog hiện hành có **323 requirement families** (từ nghĩa vụ công khai thông tin, đặt cọc, trần thanh toán đợt 1, bảo lãnh ngân hàng, bảo hành chung cư 60 tháng đến quy chế nhà chung cư...). Không phải cả 323 family đều áp dụng cho mọi hợp đồng, và ngay cả khi áp dụng, phiên bản áp dụng vào năm 2020 khác hoàn toàn năm 2024.

Hệ thống tách làm 2 bước liên tiếp trên **Nhánh A** (không bao giờ đọc `C03` citations mà hợp đồng tự viết):

1. **`C04` Scope Resolution (`CatalogScopeResolver`):** Trả lời câu hỏi *"Với bản chất giao dịch, loại tài sản và tư cách các bên trong `C02`, requirement family này **có thuộc phạm vi áp dụng không**?"* → Nhãn: `MATCH` / `NO_MATCH` / `UNKNOWN`.
2. **`C05` Temporal Resolution (`CatalogTemporalResolver`):** Trả lời câu hỏi *"Tại đúng **mốc thời gian pháp lý** của giao dịch (ví dụ ngày ký), phiên bản nào của family đó đang có hiệu lực và quy tắc chuyển tiếp có yêu cầu giữ lại ở chế độ cũ không?"* → Nhãn: `version_status` (`RESOLVED`/`UNKNOWN`) và `applicability_status` (`CONFIRMED`/`NOT_APPLICABLE`/`UNKNOWN`).

`workflows/handoffs.py` khóa cứng ranh giới: **Temporal tuyệt đối không được sửa `requirement_id`, `scope_status` hay checklist do Scope đã quyết định** (nếu cố sửa sẽ văng `ValueError("Temporal resolution changed scope-owned fields")`).

---

## 2. Cơ chế hoạt động của `C04` Scope Resolver

### 2.1. Ngôn ngữ điều kiện (`Predicate Engine`) và Chuẩn hóa dữ liệu

Mỗi hàng trong bảng `knowledge.pham_vi_ap_dung` mang một cấu trúc JSON `dieu_kien_json` dạng `{ "all": [ ... ] }` (và có thể lồng `{ "any": [ ... ] }` ở bên trong).

Khi đánh giá một điều kiện đơn lẻ trong [`evaluate_check()`](../../backend/src/legal_checker/modules/applicable_law/scope_resolver.py):
* **Đọc trường (`get_field`):** Hỗ trợ đọc trường phẳng trên `profile.profile` (ví dụ `tinh_trang_tai_san`, `la_nha_o_xa_hoi`) hoặc theo vai trò `ROLE.field` (ví dụ `BEN_BAN.la_chu_the_kinh_doanh`). Nếu có nhiều chủ thể cùng vai trò nhưng mâu thuẫn giá trị (`len(values) != 1`), `get_field` trả về `None` (`UNKNOWN`) kèm ghi chú xung đột — không đoán chọn chủ thể đầu tiên!
* **Hai toán tử được hỗ trợ:**
  * `EQ`: So sánh bằng sau khi `normalize()` quy đổi `True → "CO"`, `False → "KHONG"`, chuỗi rỗng / `"CHUA_RO"` / `"UNKNOWN"` / `"NONE"` → `None`.
  * `IS_OR_DESCENDANT_OF`: Duyệt ngược cây phân cấp `knowledge.loai_hop_dong` theo `loai_cha_id` qua hàm `is_descendant()`. Nếu một loại hợp đồng không có trong catalog, kết quả là `None` (`UNKNOWN`), không giả định `False`.
* **Bảo vệ chống suy diễn thiếu bằng chứng:** Các trường nhạy cảm như `la_giao_dich_dien_tu`, `co_thoa_thuan_trong_tai` đòi hỏi phải có `ExtractedFact` khớp giá trị boolean và gắn `evidence_ids` hợp lệ trong registry.

### 2.2. Logic 3 giá trị Kleene (`kleene_and` & `kleene_or`)

Tại sao không dùng boolean Python `True/False` thông thường? Bởi vì **không biết (`UNKNOWN`) khác hoàn toàn với không áp dụng (`NO_MATCH`)**. `scope_resolver.py` cài đặt bảng chân trị Kleene chuẩn:

| Phép toán | Quy tắc trong `kleene_and` | Quy tắc trong `kleene_or` |
|---|---|---|
| Có ít nhất 1 `NO_MATCH` | Trả ngay **`NO_MATCH`** (chỉ cần 1 điều kiện loại trừ chắc chắn, ví dụ hợp đồng mua bán nhà ở thương mại nhưng family đòi `la_nha_o_xa_hoi = CO`) | Bỏ qua `NO_MATCH`, tiếp tục xét nhánh khác |
| Có ít nhất 1 `MATCH` | Cần tất cả các điều kiện còn lại cũng `MATCH` | Trả ngay **`MATCH`** |
| Có `UNKNOWN` (và chưa bị chặn/thỏa mãn) | Trả **`UNKNOWN`** (không dám loại trừ!) | Trả **`UNKNOWN`** |

**Ví dụ hợp đồng mua bán căn hộ:**
Một family áp dụng cho nhà ở xã hội có điều kiện: `all: [tinh_trang_tai_san == HINH_THANH_TRONG_TUONG_LAI, la_nha_o_xa_hoi == CO]`.
* Trường hợp A: Hợp đồng thiếu thông tin về tình trạng hình thành trong tương lai (`UNKNOWN`), nhưng đã chứng minh rõ đây là căn hộ **thương mại** (`la_nha_o_xa_hoi = KHONG` → `NO_MATCH`). Nhờ `kleene_and(["UNKNOWN", "NO_MATCH"]) == "NO_MATCH"`, hệ thống loại trừ chính xác mà không bị vướng vào dữ kiện thiếu kia.
* Trường hợp B: Hợp đồng chưa rõ có phải nhà ở xã hội hay không (`la_nha_o_xa_hoi = None` → `UNKNOWN`). Nhờ `kleene_and(["MATCH", "UNKNOWN"]) == "UNKNOWN"`, hệ thống giữ nguyên trạng thái `UNKNOWN` để tránh bỏ sót nghĩa vụ pháp lý quan trọng.

### 2.3. Hai chính sách bảo vệ quan trọng trong `evaluate_clause` & `combine_clauses`

1. **Xác minh tư cách các bên (`CAN_XAC_MINH_TU_CACH_CAC_BEN`):** Nếu một điều khoản scope được đánh dấu `loai_chu_the = "CAN_XAC_MINH_TU_CACH_CAC_BEN"` nhưng câu JSON chưa viết điều kiện kiểm tra `BEN_BAN.*` / `BEN_MUA.*`, hệ thống đối chiếu `DEFAULT_PARTY_CAPACITY_CHECKS`:
   * Nhóm `NHAO`: yêu cầu `ben_ban_la_chu_dau_tu = CO` và `la_nha_xay_moi = CO`.
   * Nhóm `KDBDS`: yêu cầu `BEN_BAN.la_chu_the_kinh_doanh = CO` và `che_do_giao_dich = KINH_DOANH_BDS`.
   * Nhóm `FAM_PRE_CERT_CAP` / `FAM_PRE_HANDOVER_CAP`: bổ sung điều kiện `HINH_THANH_TRONG_TUONG_LAI` và `la_nha_o_xa_hoi = KHONG`.
   Chính sách này **chỉ giúp xác nhận (`MATCH`) khi đủ bằng chứng hoặc giữ `UNKNOWN`**, không bao giờ tự ép thành `NO_MATCH`.
2. **Tổ hợp theo nhóm nguồn (`THEO_NHOM_PHIEN_BAN_KHONG_LOAI_TRU_NGUON_DONG_THOI`):** Khi một family có nhiều nhóm nguồn song hành (ví dụ nguồn Luật Nhà ở và nguồn Luật KDBĐS): các clause trong cùng một `nhom_phien_ban` nối bằng `kleene_and`, sau đó các nhóm nối với nhau bằng `kleene_or`, đồng thời **giữ lại `group_status` chi tiết của từng nhóm** để truyền sang cho Temporal chọn phiên bản theo đúng nhóm hiệu lực tại thời điểm ký.

---

## 3. Cơ chế hoạt động của `C05` Temporal Resolver

### 3.1. Bốn loại mốc áp dụng (`loai_moc_ap_dung`) & Quy tắc cấm thay thế mốc

Mỗi phiên bản yêu cầu khai báo cột `loai_moc_ap_dung` (`SIGNING`, `TEMPLATE_USE`, `DEPOSIT_AGREEMENT`, `COLLECTION`). `CatalogTemporalResolver` ánh xạ sang marker tương ứng trong `C02` (ví dụ `FAM_PRE_CERT_CAP` → `PRE_CERTIFICATE_COLLECTION`, `FAM_PRE_HANDOVER_CAP` → `PRE_HANDOVER_COLLECTION`).

* **Quy tắc vàng:** Nếu một requirement yêu cầu `TEMPLATE_USE` (ngày công khai mẫu hợp đồng) nhưng hợp đồng chỉ có `SIGNING` (ngày ký), Temporal trả `UNKNOWN` với thông điệp rõ: *"`TEMPLATE_USE` date unknown; another marker is not used as a substitute"* — không tự mượn ngày ký thay thế.
* **Mốc do caller khai báo ở `C01` (`C01_DECLARED`):** Nếu người dùng nhập ngày giả định lúc tạo ca (`case.assessment_context.moc_ap_dung`), `resolve_one()` chỉ dùng khi ngày đó khớp đúng loại marker yêu cầu và **không xung đột** với ngày ký đã trích xuất từ PDF `C02`. Nếu `C01` khai `2024-08-15` nhưng trong PDF lại ghi ký ngày `2024-05-10`, hệ thống đánh dấu `C01 date conflicts with evidenced C02 marker` và giữ `UNKNOWN`.

### 3.2. Khoảng hiệu lực nửa mở `[hieu_luc_tu, hieu_luc_den)`

Hàm `in_force(version, day)` (`temporal_resolver.py`) kiểm tra:
```
start <= day  AND  (end is None  OR  day < end)
```
Tại sao dùng nửa mở? Vì ngày luật mới bắt đầu có hiệu lực (`hieu_luc_tu`, ví dụ `2024-08-01`) chính là ngày hết hiệu lực của văn bản cũ (`hieu_luc_den = 2024-08-01`). Khoảng nửa mở đảm bảo tại đúng ngày `2024-08-01`, **chỉ có đúng 1 phiên bản khớp** chứ không bị chồng lấn 2 phiên bản tại ngày chuyển giao.

* Nếu ngày đánh giá nhỏ hơn `hieu_luc_tu` của mọi phiên bản và family chỉ có đúng 1 phiên bản khai sinh về sau → `applicability_status = "NOT_APPLICABLE"` (yêu cầu chưa ra đời tại thời điểm ký).
* Nếu chuỗi phiên bản trong catalog bắt đầu muộn hơn ngày ký hợp đồng (nhiều phiên bản lịch sử trước đó chưa được nhập vào catalog) → hệ thống giữ `UNKNOWN` (lỗ hổng độ phủ catalog), không nói là `NOT_APPLICABLE`.

### 3.3. Quy tắc chuyển tiếp `LEGAL_VERSION_POLICY_V1` & Điều 83(5) Luật KDBĐS 2023

Trong [`catalog_policy.py`](../../backend/src/legal_checker/modules/applicable_law/catalog_policy.py), hàm `selection_date()` xử lý tình huống chuyển tiếp phức tạp nhất của thị trường căn hộ năm 2024:

```
Hợp đồng căn hộ HTTTL có ngày ký >= 2024-08-01 (CUTOFF)?
   │
   ├── Không (< 2024-08-01) ──► Chọn trực tiếp theo [hieu_luc_tu, hieu_luc_den)
   │
   └── Có (>= 2024-08-01):
         ├── Ngoại lệ Điều 6 (ART_VBPL005_6 - Công khai thông tin): LUÔN áp dụng luật mới.
         └── Các nghĩa vụ chịu chuyển tiếp KDBDS_83:
               Kiểm tra fact `transition.future_sale_eligible_before_20240801` (human_verified + evidence):
               ├── Thiếu fact / chưa verify ──► UNKNOWN ("transition fact required (Article 83(5))")
               ├── True + policy SALE_PROCEDURE_ONLY ──► Lùi ngày chọn chế độ về 2024-07-31 (giữ chế độ cũ)
               └── False ──► Giữ ngày ký >= 2024-08-01 (áp dụng Luật KDBĐS 2023 & Luật Nhà ở 2023)
```

Tương tự với nhà ở xã hội ký từ `2024-08-01`, nhánh `HOUSING_198` kiểm tra `transition.housing_social_process_before_20240801` (Điều 198(5)(e) Luật Nhà ở 2023).

### 3.4. Bao phủ lịch sử có chứng cứ (`historical_coverage.py`)

Khi một requirement family mới được giới thiệu từ `01/08/2024` nhưng trước đó có một family tiền nhiệm tương đương đã được `CONFIRMED` ở cùng ngày ký (`historical_equivalent_family_id` + `historical_basis_article_ids`), `resolve_historical_branches()` tự động đối chiếu và tránh giữ nguyên trạng thái `UNKNOWN` gây nhiễu báo cáo.

### 3.5. Con trỏ `candidate_version_only` khi `version_status = UNKNOWN`

Nếu một requirement không thể chốt được phiên bản (ví dụ thiếu ngày ký hợp đồng), `TemporalResolver` **vẫn đặt một con trỏ `requirement_version_id` tham chiếu tạm** với cờ `nguon_snapshot_json["candidate_version_only"] = True` và `version_status = "UNKNOWN"`. Lý do là để các bước Retrieval hay Gold/UI vẫn biết tiêu chí nào đang bị treo vì thiếu mốc, nhưng tuyệt đối không cho phép `C07`/`C08` chấm thành `SATISFIED`/`NON_COMPLIANT`.

---

## 4. Đọc tiếp & Tham chiếu nhanh

* **Bước kế tiếp trong bộ Deep Dive:** [05 — Citation Validation & Retrieval](05-citation-validation-and-retrieval.md)
* **Đối chiếu code:**
  * [`CatalogScopeResolver`](../../backend/src/legal_checker/modules/applicable_law/scope_resolver.py) — Kleene 3-valued predicate evaluation và party capacity checks.
  * [`CatalogTemporalResolver`](../../backend/src/legal_checker/modules/applicable_law/temporal_resolver.py) — interval half-open, marker matching và candidate pointers.
  * [`selection_date()`](../../backend/src/legal_checker/modules/applicable_law/catalog_policy.py) — xử lý chuyển tiếp Điều 83(5) Luật KDBĐS 2023 và Điều 198(5)(e) Luật Nhà ở 2023.
