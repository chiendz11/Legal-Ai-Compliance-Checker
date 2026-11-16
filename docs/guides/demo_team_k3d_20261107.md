# Chuyển TEAM baseline và chạy demo qua k3d

## 1. Chọn đúng môi trường

DEV local và k3d là hai PostgreSQL instances riêng. Cùng tên DB hoặc sửa .env host
không tự cập nhật Secret/database trong cụm. Giữ DB cũ, seed DB mới
legal_checker_dev_team_20261107 bằng workbook DEV/VALIDATION TEAM đã pin.

Các vai trò không đổi: người 1 phát hành/seed, người 2 extraction, người 3 C04/C05/
C06/C09, người 4 verifier/C07–C11, người 5 composition/API/FE. Đọc cùng
[playbook](parallel_development_playbook.md) và [baseline guide](dataset_team_baseline_20261107.md).

## 2. Chuẩn bị code, image và dữ liệu

Từ repo infrastructure, dùng private kubeconfig/context legal-checker-local. Nếu
cluster đang tắt, start cluster hiện có; không xóa PVC hoặc recreate database.

```bash
k3d cluster start legal-checker-local --wait
.venv/bin/python -m legal_infra build-image --allow-dirty
.venv/bin/python -m legal_infra import-image
.venv/bin/python -m legal_infra seed \
  --database-name legal_checker_dev_team_20261107 \
  --workbook ../Legal-Ai-Compliance-Checker/data/private/v750_team_baseline_20261107/bang_du_lieu_v7_5_0_TEAM_20261107_DEV_VALIDATION.xlsx
.venv/bin/python -m legal_infra.phase2 build-frontend --allow-dirty
```

Seed infrastructure gọi CLI app: init/Alembic, streaming seed và snapshot pin theo
manifest. Không gọi read_workbook nạp toàn bộ QA lớn vào RAM hoặc capture snapshot
DEV_UNVERIFIED thay SOURCE_CHECKED. Receipt phải có workbook SHA, knowledge SHA,
review status, image/source và database name. DB cũ không bị reset.

## 3. Chuyển cấu hình runtime có kiểm soát

Trước đổi DB, kiểm run/queue cũ không còn việc đang xử lý. Cập nhật DATABASE_URL trong
nguồn LocalStack Secrets Manager legal-checker/local/database, giữ password/identity
khác. Ép ESO refresh rồi kiểm target Secret bằng metadata an toàn, không log secret.
Chỉ sửa .env trên host không có tác dụng với pods. contracts/local-platform.json
database.name là DB bootstrap mặc định, không buộc app phải dùng DB cũ khi đã chọn
DATABASE_URL riêng cho release.

GitOps ConfigMap phải pin KNOWLEDGE_SNAPSHOT_SHA256, DEPLOYMENT_RULE_VERSION và
DEPLOYMENT_LEGAL_KNOWLEDGE_VERSION của TEAM. API/worker/Beat dùng cùng backend image;
frontend dùng image build từ code hiện tại. LLM key lấy từ legal-llm-secret đang có,
không commit key, không dùng payload Secret làm file cấu hình trong repo.

Dùng phase2 apply-local với image aliases trong receipts để thử source chưa publish.
Lệnh suspend auto-sync của đúng hai Legal apps, lưu policy để khôi phục; không gọi
đó là Argo đã sync một commit mới. Sau publish đúng GitOps revision mới resume.

## 4. Kiểm tra demo từ PDF thật

1. Mở frontend qua app.legal-checker.localhost:18880; upload PDF thuộc biến thể FULL,
   tạo case và run mới. Không lấy C02/C07 QA làm output của các modules đang kiểm.
2. Chờ Celery worker xử lý; F5 chỉ đọc lại tiến độ. C01/context/report phải cùng
   TEAM knowledge hash, contract/run và module_source MODULES.
3. Đọc đủ profile, scope/version, compliance, citation, risk, recommendation và
   audit/review. Kiểm source/quote, active extraction và lineage, không chỉ HTTP 200.
4. /api/v1/knowledge và audit report phải giữ SOURCE_CHECKED, không hiển thị thành
   HUMAN_VERIFIED hoặc gộp thành pending một cách sai nghĩa. Schema v7.4.9 là schema
   DB, không phải dataset/knowledge cũ.
5. Ghi riêng thiếu fact/nguồn, verifier chưa inject, lỗi provider/budget và sai handoff.
   COMPLETED không bảo đảm mọi criterion đã được LLM xử lý; không ép labels để demo.

Model/provider được kiểm bằng cấu hình thực trong cụm. Đọc được danh sách model chưa
chứng minh đã gọi reasoning thành công; chỉ báo LLM thật khi có X02 audit/attempts.
Không tự CONFIRM mọi finding hoặc publish như đã human review.

Kết quả chạy, IDs, screenshots và audit được lưu trong data/private/demo_team_20261107
và .local của infrastructure; tài liệu kết quả được bổ sung sau khi có run thật.
