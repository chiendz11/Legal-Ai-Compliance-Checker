# Bộ dữ liệu v7.5.0 cho dev và eval

Bản tối ưu có tên `v7.5.0-dev-eval-r1`. Workbook gốc giữ riêng để truy vết.
50 bảng nghiệp vụ vẫn dùng schema hiện tại; thêm 6 bảng QA để giữ split, contract artifacts,
assertions, source checks và lịch sử sửa dữ liệu. Knowledge nghiệp vụ không đổi và chưa được
human approval.

## Nhận đúng gói

| Gói | Ca corpus | Ca tổng hợp | Người dùng |
|---|---:|---:|---|
| MASTER | 90: 60 DEV, 15 VALIDATION, 15 TEST | 40 | Người quản lý dữ liệu/evaluator |
| DEV_VALIDATION | 75: 60 DEV, 15 VALIDATION | 40 | Các dev, mỗi người một DB riêng |
| TEST_INPUTS | 15 TEST, chỉ đầu vào intake | 0 | Chạy pipeline từ nguồn, không phát đáp án |

Mọi người dùng cùng split. Họ mẫu không vượt split. Thuật toán cân bằng theo metadata
input: độ dài text, có/không viện dẫn, requirement candidates và tài liệu gốc tải được.
Không dùng nhãn để lựa chọn split. Cần tiếp tục rà họ mẫu/near duplicates bằng người.

MASTER chứa nhãn TEST; chỉ phát DEV_VALIDATION cho người đang tinh chỉnh logic/prompt.
Không dùng TEST để chỉnh hệ thống. Nếu đã dùng nhãn TEST để tuning, cần holdout mới.
File XLSX và nguồn riêng không đưa vào repo public. ZIP chỉ chứa đúng workbook và các
source assets của gói; DEV ZIP không có TEST corpus, TEST ZIP không có outputs/legacy labels.

## Những thay đổi của dữ liệu

- C05 dùng UNKNOWN/UNKNOWN/UNKNOWN khi scope/date/version chưa xác minh; giữ candidate
  version và raw status trong provenance. Không biến candidate thành requirement confirmed.
- Các giá trị minh họa của 90 profiles về ngày, giá và boolean được đưa về null/UNKNOWN;
  3.126 facts MINH_HOA không còn được coi là giá trị trích xuất thật. Có QA_CHANGE_LOG.
- 74 chunks và 66 embeddings giả lập cũ được loại khỏi corpus hoạt động. 20 retrieval
  candidates dùng chúng cũng được loại; chọn lại top candidate còn hợp lệ theo từng criterion.
- 8 citations giả lập không có vị trí nguồn thật được loại; 704 citation findings còn lại
  vẫn UNKNOWN. Không suy STALE chỉ từ current status.
- 1.729 criterion outputs là UNKNOWN vì gates chưa đủ. Các nhãn SILVER cũ được lưu riêng
  dưới role PROPOSAL; không dùng làm đáp án C07.
- Criterion quotes có offsets đúng chunk. Native C07/C08/C10/C11 được tạo bằng engines hiện tại,
  giữ knowledge hash và provenance. Hash của 18 bảng knowledge không phải hash file Excel.
- C13 đầy đủ ở QA_ARTIFACTS; bao_cao_danh_gia giữ projection gọn để đọc trong Excel.
- Reference runs có IDs riêng; ca chạy mới đổi run/trace/retrieval/finding IDs, giữ input tham chiếu.

Đã tải được 7 PDF gốc, tính SHA từ bytes thật. Chưa chứng minh toàn bộ corpus chunks khớp
bản tải hay đây là giao dịch đã ký. Nguồn lỗi/HTML/unsupported được ghi trong QA_SOURCE_CHECKS.
Có 90 source-text files ghép từ chunks nguồn để dev các module text; chúng không phải PDF gốc.
`dataset://v750-r1/sources/...` là đường dẫn tới file trong gói. Storage adapter khi hoàn thành
cần đăng ký URI thật và giữ đúng hash.

## Phạm vi eval

**90 ca corpus: SILVER_GUARD_REFERENCE.** Output do engine deterministic hiện tại tạo;
hữu ích cho contract/persistence/regression replay, không phải benchmark legal accuracy độc lập.
Corpus vẫn chỉ phủ 23/441 criteria và 12/343 requirement versions; dates/scope chưa verified.

**32 ca tổng hợp: SYNTHETIC_SPEC, bước 5–7.** Assertions được viết trước khi chạy engine:
4 findings, 4 aggregation statuses, reliability/absence gates, N/A, foreign ownership/run,
citation risk routing, 30% gồm cọc, 70%/50% trước bàn giao, 95% trước GCN và missing facts.
Các source/gates/facts được ghi là giả định kiểm thử. Citation C09 trong suite là oracle input
của Risk, chưa chứng minh Citation Validator tự trích/xác thực đúng.

**8 ca PDF tổng hợp: SYNTHETIC_SPEC, Document Intelligence.** Có PDF bytes/SHA, C01 input,
C02/C03 output mẫu và assertions về tên, ngày rõ/placeholder/missing/conflicting/ambiguous,
boolean unknown/conflicting và có/không citation. PDF có text ASCII một trang, không đo chất
lượng OCR trên scan thực tế. Chunk IDs là IDs tham chiếu; khi chấm module thật, so field values,
span/ownership và citation content, không bắt module sinh cùng IDs/chunking tuỳ tiện.

Scope/Temporal/Citation services, OCR và LLM implementations thật vẫn cần hoàn thiện.
QA_TODO chỉ rõ phần thiếu. Module 9 dùng C13 draft để dev UI; review/auth/publish chưa được
chứng minh bằng nhãn dataset. Không tự tạo sự kiện human approval.

Các ngưỡng kiểm thử theo giả định giao dịch phù hợp scope tại 01/09/2024 đã đối chiếu
[Điều 25 Luật 29/2023/QH15](https://datafiles.chinhphu.vn/cpp/files/vbpq/2024/01/luat29.pdf)
và [Luật 43/2024/QH15](https://datafiles.chinhphu.vn/cpp/files/vbpq/2024/9/43-2024-qh15.pdf).
Nguồn/bytes hash, phạm vi và giới hạn kiểm tra có trong QA_LEGAL_CHECKS; đây không phải duyệt
90 hợp đồng hoặc toàn bộ knowledge. Muốn GOLD cần xác minh nguồn, mốc nghĩa vụ/chuyển tiếp,
scope, evidence, ngoại lệ và nhãn độc lập.

## Tạo DB local

Giải nén gói phù hợp vào data/private. Dùng DB mới để không trộn workbook checksum hoặc
outputs giữa dataset versions. PostgreSQL role cần CREATEDB nếu CLI phải tạo database.

```bash
python -m scripts.local_db \
  --database-url 'postgresql://legal_checker:legal_checker_local_only@127.0.0.1:5433/legal_checker_dev_v750_r1' init
python -m scripts.local_db \
  --database-url 'postgresql://legal_checker:legal_checker_local_only@127.0.0.1:5433/legal_checker_dev_v750_r1' \
  seed --workbook data/private/bang_du_lieu_runtime_v7_5_0_DEV_VALIDATION.xlsx
```

Để API dùng DB mới, đặt DATABASE_URL trong .env tương ứng. Trên máy chuẩn bị dữ liệu đã tạo:
`legal_checker_dev_v750_r1` (75 corpus), `legal_checker_eval_v750_r1` (90 corpus MASTER).
Cấu hình/DB cũ không bị thay dataset.

## Query input và expected output

```sql
SELECT case_id, split, case_kind, label_quality, module_scope
FROM qa.case_manifest ORDER BY case_id;

SELECT case_id, role, contract_name, record_id,
       string_agg(content, '' ORDER BY part_number)::jsonb AS payload
FROM qa.artifacts
WHERE case_id = 'CA90_001' AND role = 'INPUT'
GROUP BY case_id, role, contract_name, record_id;
```

QA_ARTIFACTS được chia fragments để không bị Excel cắt cell vượt 32.767 ký tự.
Helper devtools.qa_validation.join_artifacts kiểm tra thứ tự/phần/hash trước khi parse.
Đổi role thành EXPECTED chỉ trong evaluator; business modules không query đáp án của chính mình.
QA manifest/artifacts/assertions bị chặn update/delete; curation tạo dataset/label version mới.
QA_SOURCE_CHECKS và QA_CHANGE_LOG là audit data, không là bằng chứng human approval.

Module riêng có thể nhận output chuẩn của module trước làm oracle input. E2E phải chạy từ
source file qua module implementations thật; đọc các output seed rồi hiển thị chỉ kiểm tra ghép dữ liệu.
Các repository hiện tại và QA inputs giúp mỗi người bắt đầu độc lập; mapper vẫn cần lọc đúng
case/run/version và validate contract. C05 ly_do trong bản này là canonical JSON của reason.

## Chạy kiểm tra và một run thật của bước 5–7

```bash
python -m scripts.eval_local_db \
  --database-url 'postgresql://legal_checker:legal_checker_local_only@127.0.0.1:5433/legal_checker_dev_v750_r1' \
  --split REGRESSION
python -m scripts.eval_local_db \
  --database-url 'postgresql://legal_checker:legal_checker_local_only@127.0.0.1:5433/legal_checker_dev_v750_r1' \
  --split VALIDATION
python -m scripts.run_case_from_db \
  --database-url 'postgresql://legal_checker:legal_checker_local_only@127.0.0.1:5433/legal_checker_dev_v750_r1' \
  --case CA90_001 --run DEV_RUN_001
```

Chọn case có split DEV/VALIDATION trên máy mình; CA90_001 thuộc DEV trong release r1.
Runner từ chối dùng TEST
và run ID trùng reference. Một run mới lưu trong runtime.assessment_runs và normalized outputs;
retry cùng input/run là idempotent. Đổi run để thử lần khác; không ghi đè expected output.

Eval CLI chỉ chạy engines bước 5–7 hiện có: REGRESSION báo independent spec checks,
corpus báo deterministic reference replay. Nó liệt kê 8 document specs đang chờ DI implementation,
không tính chúng thành pass OCR. TEST_INPUTS không chứa target/PipelineRequest để replay;
evaluator dùng MASTER để so output pipeline thật với nhãn/rubric phù hợp.

## Tái tạo workbook

```bash
python -m scripts.optimize_workbook \
  --input /path/bang_du_lieu_runtime_v7_5_0_90_ca_danh_gia_SILVER.xlsx \
  --output-dir data/private/legal_compliance_v750_dev_eval_r1 \
  --source-audit /path/source_audit.json \
  --legal-checks /path/legal_checks.json
```

Builder yêu cầu DB knowledge khớp nội dung workbook và quyền tạo DB tạm. Tất cả runtime
reference outputs được tạo/validate trong DB tạm, rồi xuất XLSX và đọc kiểm tra lại. Source audit
chỉ được đánh dấu downloaded khi có file bytes thực cùng hash; workbook không tự tạo nguồn đã ký.
