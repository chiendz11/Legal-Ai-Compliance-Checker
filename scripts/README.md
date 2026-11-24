# Các lệnh hỗ trợ phát triển

Chạy từ root repo, dùng Python trong `.venv` đã cài `backend[dev,dataset]`. Xem [tạo môi trường ảo](../docs/guides/dev_setup.md) trước khi chạy lệnh.

| Script | Mục đích | Lệnh ví dụ | Hiện trạng |
|---|---|---|---|
| `dataset.py` | Tải/kiểm tra dataset DEV_VALIDATION theo manifest/hash | `python -m scripts.dataset pull` hoặc `check` | Đang dùng |
| `local_db.py` | Tạo DB, Alembic upgrade, preview/seed/update/check workbook | `python -m scripts.local_db init` / `preview` / `seed` / `update` / `check` | Đang dùng |
| `local_postgres.py` | Bật/tắt/kiểm tra PostgreSQL native trên Linux/macOS | `python -m scripts.local_postgres start` / `status` / `stop` | Tùy chọn cho người không dùng Docker; cần extra `[local-server]` |
| `eval_assessment.py` | Chạy đủ bước 1–7 trên một split (mặc định VALIDATION) và so với tham chiếu bạc: phạm vi, áp dụng, kết luận quy định, kết luận điểm kiểm tra | `python -m scripts.eval_assessment` hoặc `--limit 3 --llm` (tốn phí AI) | Đang dùng; ghi JSON/CSV vào `data/private/eval/` |
| `ui_fixtures.py` | Xuất report C13 tham chiếu (QA EXPECTED, split DEV) làm mock cho frontend | `python -m scripts.ui_fixtures` hoặc `--case CA360_051` | Đang dùng; ghi vào `frontend/src/mocks/fixtures/` (Git bỏ qua) |

Ba script đầu phục vụ tải dataset, chạy PostgreSQL và setup/seed DB; `ui_fixtures` chỉ đọc DB để dựng giao diện. Mỗi module tự viết query/mapper
để dựng input từ DB theo [hướng dẫn JOIN sau seed](../docs/modules/README.md).
`eval_assessment` là evaluator đầu-cuối cho bước 1–7; tham chiếu QA là bạc (`legal_gold=false`) nên độ khớp không phải độ chính xác pháp lý. Đo theo đáp án Gold dùng `run_benchmark` và `score_benchmark` bên dưới.

Các script rebuild workbook/PDF của release cũ (`optimize_workbook`, `synthetic_workbook`, `source_pdf_workbook`) đã xóa. Dataset hiện được tải từ release đã chốt; không cần dựng lại để bắt đầu làm module.

`dataset pull` tải files local, `local_db seed` ghi DB. Đọc/seed workbook và kiểm tra QA nằm trong `backend/src/devtools/`; business logic nằm trong `backend/src/legal_checker/modules/`.

`local_db init` dùng Alembic trong `legal_checker/migrations/`; runner SQL cũ đã xóa. `seed` cập nhật schema trước, sau đó nhập dữ liệu trong transaction riêng. Xem [tạo revision và tiếp nhận DB cũ](../docs/database/migrations.md).

Xem [hướng dẫn contracts máy đọc được](../docs/contracts/README.md) để cập nhật trực tiếp đặc tả JSON. Tests kiểm tra tính hợp lệ và đối chiếu với models hiện tại mà không ghi lại files.

`docs/architecture/openapi.design.json` là đặc tả API được commit cùng tài liệu. Backend không đọc
file này để chạy handlers. Công cụ sinh contracts/OpenAPI đã được xóa sau khi xuất đặc tả.

`local_db update` dành cho các revision tương thích như reviewed-flags, áp dụng trên
baseline đúng checksum trong một transaction. TEAM_BASELINE_20261107 thay identities
và runtime nên CLI yêu cầu DB mới, giữ DB/lịch sử cũ. Xem
[hướng dẫn baseline](../docs/guides/dataset_team_baseline_20261107.md).

`python -m scripts.local_db align-runtime` tạo snapshot catalog bổ sung bất biến
từ đúng TEAM 20261107 đã seed; lệnh in SHA mới để cấu hình API/worker. Không ghi
đè workbook, snapshot hoặc reports cũ. [Chi tiết](../docs/guides/complete_runtime_alignment_20261108.md).

`python -m scripts.local_db align-content-defaults --parent-sha256 <SHA>` tạo
revision source-checked cho rule phương thức bàn giao/bảo lưu sở hữu. Parent hash
và source binding được kiểm tra; không đổi pin lịch sử. Xem [hướng dẫn v4](../docs/guides/baseline_v4_civil_defaults_20261109.md).

## Chạy benchmark với Gold Master R14

Dùng hai gói có mục đích khác nhau:

| Gói | Dùng để làm gì? |
|---|---|
| Runtime `PDF360_V4R2_20261110 DEV_VALIDATION` | Tải bằng `scripts.dataset pull`. Gói này có workbook để seed PostgreSQL và PDF cho phát triển. |
| R14 `GOLD_DEV_VALIDATION_300_OF_300.zip` | Nhận từ người quản lý dataset. Có PDF, C01 và đáp án Gold của **240 DEV + 60 VALIDATION** để chạy và chấm benchmark. Giải nén vào `data/private/gold_r14_team`. |

Sau khi tạo môi trường ảo và `.env` theo [hướng dẫn dev](../docs/guides/dev_setup.md), tải
runtime, seed DB và cấu hình `ASSESSMENT_MODULES=modules`. File `.env.example` đã
pin knowledge của release này. C01 R14 nghiêm ngặt về pin, nên khi dùng lại cấu hình
của release khác, kiểm tra cả knowledge hash và phiên bản triển khai trước khi chạy.

```bash
python -m scripts.dataset pull
python -m scripts.dataset check
docker compose up -d --wait postgres
python -m scripts.local_db init
python -m scripts.local_db seed
python -m scripts.local_db check
ASSESSMENT_MODULES=modules uvicorn legal_checker.main:create_app --factory --host 127.0.0.1 --port 8000
```

Để API chạy, mở terminal khác với cùng môi trường ảo và thực hiện thử trên 8 ca DEV:

```bash
python -m scripts.run_benchmark --inputs data/private/gold_r14_team \
  --api http://127.0.0.1:8000 --split DEV \
  --case CA360_001 CA360_322 CA360_003 CA360_324 CA360_225 CA360_338 CA360_351 CA360_240 \
  --output data/private/benchmark_r14/dev_runs
python -m scripts.score_benchmark --gold data/private/gold_r14_team \
  --predictions data/private/benchmark_r14/dev_runs \
  --output data/private/benchmark_r14/dev_metrics.json
```

Bỏ `--case` để chạy toàn bộ split đã chọn. Ghi lại commit/image, cấu hình LLM và
snapshot trước khi chạy. Dùng thư mục output mới cho mỗi cấu hình. Runner tự kiểm
checksum, upload PDF và gửi giá trị intake. `scripts.dataset cache-sources` hữu ích
khi mở ca đã seed có dataset URI. Runner benchmark có bước upload PDF riêng.

Với TEST, đội chạy chỉ dùng gói R14 `TEST_INPUTS_60_CASES.zip` làm `--inputs` và
chọn `--split TEST`. Sau khi predictions được khóa, evaluator dùng gói riêng
`GOLD_MASTER_EVALUATOR_360_OF_360.zip` làm `--gold` để chấm. Hai gói này được giải
nén vào các thư mục riêng. [Phạm vi và cấu trúc Gold R14](../docs/guides/gold_master_20261114.md).

C02 đo một nhóm fields vô hướng có mapping, trên nhãn `KNOWN`. C05 chấm phạm vi
riêng với cặp applicability/version. C06 đo mức tìm lại witness L2 và MRR@K trên
các query có witness đã chấm, dùng quote chuẩn hóa cùng trang trong các đoạn
FINAL được chọn. C07 tính confusion matrix và F1 cho `ASSESSED`, giữ
`NO_PREDICTION` riêng. C08 chấm status của requirement đã đánh giá. C09 báo số
lượt ghép được theo nguyên văn và trang cùng kết quả validation trên các cặp đó.
C13 kiểm trạng thái bản nháp, liên kết nguồn và các định danh của run. Chấm nội
dung C10/C11, quyết định C12 và đối sánh nguồn rộng hơn còn thuộc phạm vi mở rộng
evaluator. Báo riêng các ca không hoàn tất cùng mẫu số của mỗi lớp.
