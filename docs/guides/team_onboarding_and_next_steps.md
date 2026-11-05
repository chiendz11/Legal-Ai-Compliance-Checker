# Bàn giao main và công việc tiếp theo cho 5 người

Cập nhật ngày **05/11/2026**. Áp dụng cho app repo sau khi PR phase-two được merge
vào `main`. Ownership theo `docs/business/ke_hoach_10_tuan.xlsx`; không suy ra tác giả
thực tế của từng commit hoặc phần trăm hoàn thành từ tên người phụ trách.

## 1. Baseline chung mà cả nhóm cần lấy

| Thành phần | Baseline |
|---|---|
| Code ứng dụng | `origin/main`, gồm phase-two worker, C07/C08 draft checks và tooling cập nhật dataset |
| Dataset | `v7.5.0-source-pdf360-r2-structured`, storage `supabase-public-v1`, review `user-reviewed-20261105` |
| Dữ liệu cho dev | DEV_VALIDATION: 240 DEV + 60 VALIDATION, thêm 32 QA regression |
| Legal knowledge version | `V750_LEGAL_KNOWLEDGE_USER_REVIEWED_20261105` |
| Knowledge hash | `df6ed7aa9f5100bfe68430b950d55542db752e7255c324e18be171ce0d0d3ade` |
| File để tải | ZIP DEV/VALIDATION đúng hash trong `configs/dataset_dev_validation.json` |
| DB mỗi người | PostgreSQL local riêng; không kết nối DB k3d của người khác để chạy test/seed |

MASTER có đáp án của 360 ca để quản lý/evaluate; không thay gói phát cho dev bằng
MASTER. TEST_INPUTS có 60 ca chỉ input. Giữ split theo nhóm nguồn, không dùng đáp án
TEST để điều chỉnh prompts/rules hoặc chọn cấu hình.

Hai việc độc lập: merge code giúp người khác lấy tooling/manifest; chủ dataset phải
thay **ZIP** trên Drive để lệnh tải nhận bytes mới. Thay riêng `.xlsx` không cập nhật
ZIP. Dùng Manage versions → Upload new version trên ZIP cũ để giữ file ID; nếu có ID
mới thì cập nhật `archive.url` trong manifest và đưa thay đổi đó lên main.

## 2. Mỗi thành viên cần chạy gì?

### 2.1 Lấy code và chuẩn bị môi trường

Commit/stash phần đang làm trước khi đổi nhánh hoặc ghép main. Không reset nhánh dev.

```bash
git fetch origin
git switch main
git pull --ff-only origin main
source .venv/bin/activate
python -m pip install -e './backend[dev,dataset]' -c constraints.txt
```

Người tiếp tục trên nhánh riêng ghép `origin/main` vào nhánh đó rồi xử lý xung đột
nếu có. Máy chưa có `.venv` làm theo [dev_setup.md](dev_setup.md). Giữ `.env` hiện có;
chỉ tạo từ `.env.example` trên máy chưa có cấu hình. Giữ `DATABASE_URL` và API key riêng.

### 2.2 Đã có dataset/DB cũ

Giữ folder và workbook gốc đã seed. Tải revision mới vào folder khác, tránh `.env`
cũ khiến downloader chọn nhầm tên workbook:

```bash
python -m scripts.dataset pull \
  --destination data/private/v750_source_pdf360_r2_supabase_user_reviewed_20261105
```

Nếu Drive chưa được thay file hoặc không tải tự động được, thêm
`--archive /path/to/ZIP_moi.zip`. Không đổi hash để dùng ZIP cũ.

Đặt trong `.env` (và cập nhật biến đã export trong shell nếu đang dùng):

```dotenv
SEED_WORKBOOK_PATH=data/private/v750_source_pdf360_r2_supabase_user_reviewed_20261105/bang_du_lieu_runtime_v7_5_0_360_STRUCTURED_R2_SUPABASE_DEV_VALIDATION_USER_REVIEWED_20261105.xlsx
```

Sau khi xác nhận `DATABASE_URL` là DB riêng và PostgreSQL đang chạy:

```bash
python -m scripts.dataset check
python -m scripts.local_db init
python -m scripts.local_db update \
  --previous-workbook data/private/v750_source_pdf360_r2_supabase/bang_du_lieu_runtime_v7_5_0_360_STRUCTURED_R2_SUPABASE_DEV_VALIDATION.xlsx \
  --dry-run
```

Sao lưu DB trước lần update thật, dừng tạo assessment mới và đợi run đang chạy kết
thúc. Khi dry-run đúng, chạy lại lệnh update bỏ `--dry-run`, rồi:

```bash
python -m scripts.local_db check
```

Đường dẫn workbook cũ có thể thay theo máy, nhưng bytes phải khớp receipt đã seed.
`update` giữ hợp đồng upload, lịch sử run/report, review/audit và snapshot cũ; từ chối
ghi đè các dòng baseline đã được dev sửa khác cả hai release. Nếu có xung đột, review
PK được báo hoặc dùng DB mới riêng, giữ DB cũ để không mất công việc.

### 2.3 Máy mới hoặc DB trống

Với `.env` đã trỏ workbook reviewed và DB riêng đang chạy:

```bash
python -m scripts.dataset pull
python -m scripts.dataset check
python -m scripts.local_db init
python -m scripts.local_db seed
python -m scripts.local_db check
```

`seed` dành cho baseline trong DB mới. `init` chỉ nâng schema Alembic. DB đã seed
bản cũ dùng `update`; không cần xóa DB để cả nhóm lấy revision mới.

### 2.4 Khởi động lại và tự xác nhận

Khởi động lại API/worker/Beat mà mình đang chạy; các tiến trình giữ snapshot trong bộ
nhớ. Với pin cấu hình riêng, cập nhật `KNOWLEDGE_SNAPSHOT_SHA256` và legal version cho
đúng revision muốn dùng. Không xóa snapshot cũ để cập nhật các run lịch sử.

```bash
curl http://127.0.0.1:8000/api/v1/knowledge
```

Đổi host/port theo môi trường. Kết quả cần có hash reviewed ở mục 1 và
`review_status: HUMAN_VERIFIED`; `dataset check` cần xác nhận 337 file. Cổng 5433 là
DB Compose/native của từng dev; DB trong k3d là môi trường riêng với kubeconfig/port
forward do infrastructure quản lý.

Tài liệu chi tiết bảo vệ dữ liệu và receipts: [reviewed_dataset_update.md](../database/reviewed_dataset_update.md).

## 3. Những gì baseline mới đã giải quyết và còn cần hoàn thiện

Đã có revision tri thức reviewed, công cụ update giữ lịch sử, API đọc review status
từ DB và triển khai worker/Redis. Việc upload ZIP trên Drive do chủ dataset thực hiện;
chỉ coi phân phối online đã hoàn tất sau khi tải thử đúng hash từ Drive.

Chưa thể suy ra chất lượng inference từ cờ review. Một ca upload kiểm tra ngày
05/11 đã đọc profile, tạo chunks và chạy đến report, nhưng còn các điểm nối/điều kiện
thiếu. Các số liệu bên dưới là chẩn đoán một run, không phải metric toàn corpus.

Một khác biệt cần chốt trước khi so metric: C05 tham chiếu trong DB có **10 family
mỗi ca**, trong khi `CatalogScopeResolver()` của luồng upload đang xét **306 family**
vì chưa truyền `requirement_ids`. Thống nhất assessment profile/phạm vi checklist và
báo cáo coverage giữa người 1, 3, 5; không dùng expected của 10 family để chấm trực
tiếp toàn bộ 306, cũng không tự bỏ yêu cầu chỉ để tăng tỷ lệ kết luận.

### Người 1 — Dataset, DB, CI/CD và hạ tầng

| Ưu tiên | Việc cần làm | Vì sao / đầu ra bàn giao |
|---|---|---|
| P0 | Thay ZIP reviewed trên Drive, kiểm tra tải online rồi công bố release cho nhóm | Manifest đã pin bytes mới; ZIP cũ sẽ bị từ chối. Bàn giao link, SHA và hướng dẫn update |
| P0 | Cùng người 3 bổ sung dữ liệu marker và phân định version family | Cờ `HUMAN_VERIFIED` đã có nhưng loại mốc/ngữ nghĩa phiên bản còn thiếu. Thay đổi nội dung cần release/hash mới, không sửa snapshot cũ |
| P1 | Nghiệm thu backup/restore và dựng lại môi trường từ runbook | Có backup/cluster chạy chưa thay thế được một lần restore/rebuild có bằng chứng |
| P1 | Đối chiếu signing/verify image, scan và gates với kế hoạch | Workflow build/publish hiện chưa có đủ bằng chứng cho mọi gate DevSecOps; không ghi đã hoàn thành từ sơ đồ |

### Người 2 — Bước 1–2: Documents

| Ưu tiên | Việc cần làm | Vì sao / đầu ra bàn giao |
|---|---|---|
| P0 | Cùng người 5 lưu đầy đủ DocumentExtraction trước Retrieval | Run có profile/chunks trong JSON nhưng DB normalized của hợp đồng upload chưa có extraction. Repository đã có; giữ chunk/fact/evidence IDs cùng version |
| P0 | Bàn giao nguồn, trạng thái, time markers và facts đủ để người 3/4 kiểm tra | 32 facts mới trích xuất đều chưa human-verified; fixture đã review không tự duyệt PDF upload |
| P1 | Đánh giá citation có năm, Điều/Khoản và câu qua trang cùng người 3 | C03 đã trích năm ở một số viện dẫn; validator hiện yêu cầu số hiệu. Bàn giao đủ field và thống nhất policy tên+năm với người 3 |
| P1 | OCR và DOCX theo phạm vi đã chốt; đo extraction/chunk quality | OCR chưa có implementation, đường chạy hiện nhận PDF text layer; công bố các loại tài liệu được hỗ trợ |

Tiêu chí bàn giao P0: cùng một run có DTO hợp lệ và DB rows tương ứng; Retrieval đọc
được section paths/fact evidence của chính extraction đó; chạy lại không trộn version.

### Người 3 — Bước 3–4: Scope, Temporal, Citation và Retrieval

| Ưu tiên | Việc cần làm | Vì sao / đầu ra bàn giao |
|---|---|---|
| P0 | Cùng người 1 xử lý catalog marker và version chồng lấn | Run có 80 family chưa xác định được loại mốc, 5 family có nhiều version cùng hiệu lực, 1 family thiếu coverage lịch sử. Giữ bằng chứng và lý do chọn version |
| P0 | Cùng người 2 xử lý profile/party-capacity mapping thiếu | Scope còn UNKNOWN do field thiếu hoặc nhóm chưa có policy đủ; không mặc định UNKNOWN thành MATCH |
| P0 | Nối C09 provenance với người 4–5 | C10 yêu cầu `knowledge_snapshot_sha256`, `context`, `hop_dong_id` trong source snapshot; 11 findings hiện thiếu các pin này |
| P0 | Đánh giá 5 criterion thiếu selected FINAL evidence | Tách trường hợp retrieval bỏ sót, đoạn có nhưng thiếu metadata, và nội dung thực sự không có |
| P1 | Identity theo tên/năm và nhánh domain UNKNOWN; báo cáo Recall@K/MRR và resolver/citation metrics | Run có 5 citation VALID, 6 UNKNOWN; kết quả này không đủ nghiệm thu mọi nhánh của classifier |

Phân biệt cờ review với nội dung: `trang_thai_ra_soat=HUMAN_VERIFIED` không thay cho
một giá trị nghiệp vụ cụ thể ở `loai_moc_ap_dung`. Sentinel `CHUA_XAC_MINH`, thiếu
ngày thu tiền hoặc khoảng hiệu lực chồng lấn cần bổ sung/phân giải đúng nghĩa.

### Người 4 — Bước 5–7: Compliance, Risk và Recommendation

| Ưu tiên | Việc cần làm | Vì sao / đầu ra bàn giao |
|---|---|---|
| P0 | Tạo CriterionVerification từ facts/evidence đúng criterion, case, run và hash | Luồng tích hợp chưa truyền `verifications`; cả 76 criterion của run còn thiếu xác minh facts/local applicability |
| P0 | Cùng người 5 nối verification vào provider trước C07 | Review của knowledge khác review dữ kiện mới. Không bật mọi gate chỉ vì snapshot đã được duyệt |
| P0 | Giảm quote mismatch, giữ quote/offset/chunk nguyên bản | Trong 14 lời gọi AI thành công, 8 phản hồi bị loại vì QUOTE_MISMATCH; cần kiểm tra selection, prompt và mapping thay vì bỏ grounding |
| P0 | Cùng người 5 thiết kế budget/retry và ưu tiên criterion đủ điều kiện | Giới hạn 20 criterion làm 51 criterion không được gọi; có thêm lỗi RATE_LIMIT/temporary HTTP. Ghi trạng thái kỹ thuật rõ ràng |
| P1 | Cùng người 3 hoàn thiện C09→C10 và phân biệt risk pháp lý/thiếu chứng cứ/lỗi xử lý | C09 provenance đang thiếu; không coi lỗi provider hoặc CALL_LIMIT là bằng chứng hợp đồng vi phạm |
| P1 | Đánh giá C07/C08, numeric rules, grounding và risk/rec trên validation | Một run completed và unit tests không tự chứng minh đúng nhãn pháp lý |

Tiêu chí bàn giao P0: ca đủ dữ liệu tạo được finding có căn cứ; ca thiếu dữ liệu vẫn
UNKNOWN đúng lý do; mỗi criterion thấy rõ được gọi/chưa gọi/lỗi/đã kiểm tra và có nguồn.

### Người 5 — Workflow, API, Review, Report và frontend

| Ưu tiên | Việc cần làm | Vì sao / đầu ra bàn giao |
|---|---|---|
| P0 | Nối lưu Documents → đọc metadata Retrieval; nối verification → C07 | Đây là việc ghép module, phối hợp người 2–4; không yêu cầu viết lại các engine |
| P0 | Tách nguyên nhân trên UI/report | Phân biệt thiếu loại mốc, nhiều version, thiếu hồ sơ, chưa gọi AI, lỗi quota/HTTP và đề xuất chưa đủ verification |
| P0 | Kiểm tra version label/hash của ca và run mới; giữ snapshot/report lịch sử | Ca mới phải pin cùng release; kết quả cũ không đổi chỉ vì knowledge hiện tại đã đổi |
| P1 | Nghiệm thu C09→risk, auth/tenant, review/publish/history/export và recovery | Có code và một đường demo chưa bao quát toàn hành trình lẫn các nhánh lỗi |
| P1 | Giới hạn reference fallback cho dev/eval, thông báo nguồn thật đang dùng | PDF khách hàng cần được xử lý từ bytes thật; QA reference không thay được extraction |

## 4. Thứ tự tích hợp và cách đóng task

1. Cả nhóm lấy main và đồng bộ dataset/DB đúng revision. Mỗi người xác nhận hash.
2. Người 2 + 5 nối persistence Documents; người 3 kiểm tra metadata Retrieval đọc được.
3. Người 1 + 3 sửa catalog marker/version; người 2 cung cấp profile/time markers còn thiếu.
4. Người 4 tạo verification; người 5 truyền vào C07; người 3 bảo đảm selected evidence.
5. Người 3 + 4 + 5 đóng provenance C09→C10. Người 4 + 5 xử lý budget/retry và thông điệp.
6. Chạy ca DEV đại diện sau từng điểm nối, lưu code SHA + dataset/hash + model/prompt +
   output/diagnostics. Sau đó chạy validation và công bố metrics theo từng module.

Mỗi task có PR, test hoặc bằng chứng phù hợp, input/output contract, IDs/version/hash
và lỗi còn lại. Phân biệt unit/fixture pass, provider thật, integration và đánh giá
chất lượng. Không dùng tỷ lệ hoàn thành tự đặt hoặc mọi trạng thái COMPLIANT làm gate.

## 5. Main ứng dụng và Argo CD

Merge app vào main giúp cả nhóm dùng baseline mới; không tự merge hai repo infra/GitOps
và không tự đổi nhánh Argo CD đang theo dõi. Cụm local hiện theo GitOps feature branch
phase-two. Workflow publish của app trên main mặc định cập nhật GitOps main; đó là
nhánh riêng với nhánh đang chạy local. Nếu cần rollout image mới lên local hiện tại,
dùng dispatch chỉ rõ `target_branch=feat/local-phase2-worker-verification` và kiểm tra
image/Argo health sau đó. Không tự chuyển Argo sang GitOps main còn cấu hình phase-one.

Không cần k3d để dev từng module. Cụm local là môi trường tích hợp; PostgreSQL local
riêng và contracts/fixtures là nền cho phần việc song song.
