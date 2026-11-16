# Dataset chung TEAM_BASELINE_20261107

> Bản ghi lịch sử: trạng thái dataset/approval trong đợt này đã được cập nhật bởi
> [release PDF360 v4 r2 và knowledge được chủ dự án duyệt](dataset_pdf360_v4r2_runtime_20261110.md).


Người 1 chốt baseline để người 3–5 dùng chung dữ liệu và khóa JOIN. Đọc cùng
[integration spec](../contracts/integration_spec.md),
[baseline extraction](../contracts/source_observed_extraction_baseline.md) và
[playbook](parallel_development_playbook.md).

## 1. Phiên bản và phạm vi

| Thành phần | Giá trị |
|---|---|
| Dataset | `v7.5.0-pdf360-team-baseline-20261107` |
| Knowledge | `V750_TEAM_KNOWLEDGE_20261107` |
| Deployment tham chiếu | `V750_TEAM_BASELINE_20261107` |
| Knowledge SHA-256 | `39d823fb72b886d88d55367e928f96a39218d16e4287899fc1a163d25458bc4d` |
| SQL schema / DTO | Giữ `v7.4.9` / `1.0`; khác phiên bản tri thức |
| Inventory | 323 families, 357 versions, 479 criteria |
| Scope QA corpus | `TEAM_CORE_REFERENCE_V1`: 36 atomic requirements/ca; xem ASSESSMENT_SCOPE.json trong gói |
| Corpus | 240 DEV + 60 VALIDATION + 60 TEST, giữ source groups/splits |
| Controlled | 32 ca SYNTHETIC_SPEC trong MASTER và DEV/VALIDATION |

Không thêm dữ kiện vào 360 PDF, đổi URL Supabase hoặc rechunk. Source text và
citation sheets được giữ nguyên. Dataset/PDF/DB tiếp tục ngoài Git.

## 2. Các quyết định đã chốt

Tám chủ đề có nguồn đồng thời được tổ chức thành 21 atomic families, thêm 13 IDs.
Giữ version IDs, criterion IDs và ngày hiệu lực; không cắt nguồn để hết chồng lấn.

```text
Topic FAM_PARTY_IDENTITY
  FAM_PARTY_IDENTITY         → BVNTD
  FAM_PARTY_IDENTITY__KDBDS  → KDBDS
  FAM_PARTY_IDENTITY__NHAO   → NHAO
```

ID gốc là anchor family; không thêm C05 cho parent. C05/C08 vẫn có một family và
một version, JOIN như cũ. [Topic mapping](../contracts/legal_topic_mapping.json)
quy định nhóm/đếm: DISTINCT topic_id cho chủ đề; giữ findings từng nguồn. Không
cộng mỗi nguồn thành một incident, cũng không dedup mọi risk chỉ vì cùng topic.
Family ngoài mapping dùng chính requirement_id làm topic_id.

`PV_HYC051` có thêm 19 criterion gắn toàn văn Điều 1–19 Mẫu số 01, trang và SHA
[NĐ02/2022 chính thức](https://datafiles.chinhphu.vn/cpp/files/vbpq/2022/01/02.signed.pdf).
Đã phân biệt Điều của mẫu với Điều trong thân Nghị định. Có tiêu đề không đủ
chứng minh phù hợp; phải xét khoản/điểm, chú thích và nội dung được thỏa thuận.

Tài khoản bảo trì có thêm version 2015 trong `[2015-12-10, 2021-03-26)` và 2021
trong `[2021-03-26, 2024-08-01)`; giữ version 2024. Phân biệt tài khoản bảo trì
với tài khoản trả tiền mua căn hộ, nội dung hợp đồng với chứng minh đã mở/nộp tiền.

NOXH_CORE_V1 gồm đối tượng mua, điều kiện nhà ở, thu nhập, căn cứ giá và hạn chế
bán lại. Bổ sung bốn families và version lịch sử/hiện hành; bổ sung lịch sử cho
family bán lại sẵn có. Nguồn: Luật Nhà ở 2014/2023, NĐ100/2024, NĐ261/2025,
NĐ54/2026 và [NĐ136/2026](https://datafiles.chinhphu.vn/cpp/files/vbpq/2026/4/136-ndcp.signed.pdf).
Các mốc thay đổi có version riêng, không áp một ngưỡng cho mọi thời kỳ/đối tượng.
Đây là phạm vi lõi, không tuyên bố đủ mọi thủ tục dự án/nguồn vốn/chương trình
đặc thù/mẫu hồ sơ hoặc quy định địa phương. Hồ sơ, ngày xác nhận và chuyển tiếp
vẫn cần kiểm tra theo ca; không tự thêm chúng vào PDF hoặc dùng ngày ký thay thế.

## 3. Runtime/QA và mức tin cậy

C01/context/deployment/hash được pin lại; C04/C05 chạy lại resolver. C02/chunks/
C03 theo nguồn cũ; loại giá trị bốn facts bảo hành 25 tháng do nhầm ngày văn bản,
không đoán duration thay thế. C06 có BM25 candidates và source-span references
có nhãn; references này không là gold để chấm chính BM25.

Dựng lại C07/C08/C09/C10/C11/C13 draft, không chỉ đổi hash trên kết luận cũ.
[Source reference policy](../contracts/source_reference_policy.json) chỉ hỗ trợ
predicates tường minh về tên các bên, căn hộ và bảo hành lịch sử; không phải
production verifier. Không gọi LLM mới để dựng reference.

Hai expected controlled được đổi có lý do: unresolved không có candidate version
không sinh criterion giả; STALE chưa verified chỉ tạo diagnostic, không tự thành
legal risk hoặc finding UNKNOWN khác. Changelog có trong gói.

Corpus là SILVER_GUARD_REFERENCE cho dev, JOIN/DTO và regression. Không lấy output
chính engine dựng làm gold độc lập để báo accuracy của engine. 32 SYNTHETIC_SPEC
kiểm rule/guard/biên số học, không đo OCR/LLM trên PDF thật.

Snapshot SOURCE_CHECKED: 441 criteria gốc giữ human flags đã có; 38 criteria và
152 decision rules mới không tự ghi human_verified=true. Đây là kiểm nguồn để
dev, không giả lập human review hoặc nghiệm thu phát hành khách hàng.

Corpus C07: 522 SATISFIED, 27 VIOLATED, 14.820 UNKNOWN. C08: 128 COMPLIANT,
27 NON_COMPLIANT, 9.832 INSUFFICIENT. MISSING/PARTIAL có trong controlled suite;
không ép vào corpus khi chưa có absence proof hoặc ép cân bằng nhãn.

## 4. Seed DB local mới

Giữ DB cũ và secrets riêng. Release thay identities/output nên dùng DB mới,
không dùng local_db update của reviewed-flags release lên DB cũ. CLI đã chặn
cách update đó cho manifest mới. Chỉnh hai biến `.env`, giữ các biến khác:

```dotenv
DATABASE_URL=postgresql://legal_checker:legal_checker_local_only@127.0.0.1:5433/legal_checker_dev_team_20261107
SEED_WORKBOOK_PATH=data/private/v750_team_baseline_20261107/bang_du_lieu_v7_5_0_TEAM_20261107_DEV_VALIDATION.xlsx
```

Từ root repo, trong `.venv` đã cài backend:

```bash
python -m scripts.dataset pull --archive /path/to/legal_compliance_v750_TEAM_20261107_DEV_VALIDATION.zip
python -m scripts.dataset check
python -m scripts.local_db init
python -m scripts.local_db seed
python -m scripts.local_db check
```

Workbook lớn được seed theo luồng và kiểm QA/hash trong transaction, không nạp
toàn bộ corpus vào RAM. Không seed dev bằng MASTER hoặc workbook nhỏ. Nếu pin
KNOWLEDGE_SNAPSHOT_SHA256, đổi sang hash mục 1 cho DB mới và restart backend/worker.

ZIP mới được chuẩn bị local. Theo lựa chọn trước của chủ dự án, việc thay version
file Drive do chủ dự án thực hiện. Manifest LOCAL_ARCHIVE_READY không tải nhầm
link còn bản cũ; --archive dùng được ngay. Sau upload đúng ZIP vào Manage versions
của file Drive đã cấu hình, dùng --url để tải/kiểm hash rồi maintainer đổi
publication_status thành PUBLISHED. Không đổi checksum để nhận ZIP cũ.

## 5. Người 3–5 sử dụng

- Người 3: JOIN family/version thực tế; không hardcode 10 parent families cũ.
  So reference theo ASSESSMENT_SCOPE; live dùng scope sản phẩm đã khai báo.
- Người 4: C05/C06/C09 cùng case/run/hash; đọc fixtures theo source policy,
  implement verifier theo dictionary/recipe. Không import builder dataset vào app.
- Người 5: QA chỉ cho dev/reference; live đọc PDF/output thật. Hiển thị đúng
  version/hash/review state; phân biệt chủ đề, atomic requirements và incidents.
  Không thay report lịch sử bằng reference mới.

Gói có ba distributions, knowledge workbook nhỏ, scope/mapping/policy, changelog
và validation. VALIDATION kiểm workbooks; DB_VALIDATION ghi seed/replay trên DB
tạm. Các bằng chứng này không thay đánh giá chất lượng độc lập hoặc deployment.
