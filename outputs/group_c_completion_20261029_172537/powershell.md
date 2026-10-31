# Lệnh PowerShell bàn giao nhóm C

Chạy từ `C:\demo\Legal-Ai-Compliance-Checker`, dùng `.venv\Scripts\python.exe`.
Không ghi đè `.env`, output directories hoặc gói evidence này. Các lệnh nhóm C dưới
đây không tạo paid provider. Source ZIP chứa working tree, gồm cả files untracked;
patch chỉ chứa tracked changes và không đủ khôi phục toàn bộ implementation.

## PostgreSQL test riêng

```powershell
$pg = 'C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe'
$cluster = 'C:\demo\Legal-Ai-Compliance-Checker\data\private\group_c_phase2_postgres\cluster'
& $pg -D $cluster status
# Chỉ start khi instance đang dừng; không thay dịch vụ/DB dev:
& $pg -D $cluster -l 'C:\demo\Legal-Ai-Compliance-Checker\data\private\group_c_phase2_postgres\server.log' -o '-p 55433 -h 127.0.0.1' -w start
$env:TEST_DATABASE_URL = 'postgresql://legal_checker@127.0.0.1:55433/legal_checker_test_completion'
```

Tests kiểm tra prefix `legal_checker_test`, tạo/xóa DB con riêng. Sandbox Codex cần
quyền chạy ngoài sandbox để kết nối TCP loopback; PowerShell trực tiếp của máy không
có giới hạn đó. Native PG18.4 đã dùng để kiểm chứng local; CI khai báo PG17.10 và
Python3.12. Không coi local result là một GitHub Actions run đã chạy.

## Checks theo CI

```powershell
.\.venv\Scripts\python.exe -m ruff check --config backend/pyproject.toml .
.\.venv\Scripts\python.exe -m ruff format --check --config backend/pyproject.toml .
.\.venv\Scripts\python.exe -m pytest -q -c backend/pyproject.toml
```

Muốn lưu một lần kiểm tra mới mà giữ nguyên manifests/evidence hiện tại:

```powershell
$newCheck = 'outputs/group_c_recheck_' + [guid]::NewGuid().ToString('N')
New-Item -ItemType Directory -Path $newCheck | Out-Null
Copy-Item -LiteralPath outputs/group_c_completion_20261029_172537/verify_all.py -Destination $newCheck
.\.venv\Scripts\python.exe -X utf8 "$newCheck/verify_all.py" --test-database-url $env:TEST_DATABASE_URL
```

Script chạy Ruff check/format toàn repo, full pytest có JUnit và kiểm tra import
installed package/resources từ thư mục ngoài repo; báo lỗi nếu còn tests skipped.

## Đọc run demo đúng membership

```powershell
$source = Get-Content -LiteralPath outputs/group_c_completion_20261029_172537/demo_source.json -Raw | ConvertFrom-Json
$demo = Get-Content -LiteralPath outputs/group_c_completion_20261029_172537/demo_verification.json -Raw | ConvertFrom-Json
$env:DATABASE_URL = $source.database_url
$readOut = 'outputs/group_c_read_' + [guid]::NewGuid().ToString('N')
.\.venv\Scripts\python.exe -X utf8 -m legal_checker.modules.assessments.run_group_c --case $demo.case_id --read-run $demo.run_id --output-dir $readOut
```

Run cũ phải đọc đúng ngay cả khi `$demo.newer_run_id` đã tồn tại. Reader không gọi
Knowledge adapter/provider/C07/C08/C10/C11 engines. Đừng thay bằng query run mới nhất.

## Offline, retry và replay

```powershell
$offlineOut = 'outputs/group_c_offline_' + [guid]::NewGuid().ToString('N')
.\.venv\Scripts\python.exe -X utf8 -m legal_checker.modules.assessments.run_group_c --case CA360_001 --reference-run CA360_001_PDF360_LS2_REFERENCE --save --output-dir $offlineOut

$saved = 'outputs/group_c_completion_20261029_172537/demo_verified_saved'
$retryOut = 'outputs/group_c_retry_' + [guid]::NewGuid().ToString('N')
.\.venv\Scripts\python.exe -X utf8 -m legal_checker.modules.assessments.run_group_c --input "$saved/input.json" --save --output-dir $retryOut

$replayOut = 'outputs/group_c_replay_' + [guid]::NewGuid().ToString('N')
.\.venv\Scripts\python.exe -X utf8 -m legal_checker.modules.assessments.run_group_c --input "$saved/input.json" --replay-analyses "$saved/analyses.json" --profile "$saved/profile.json" --output-dir $replayOut
```

Offline reference mode fork run mới, chỉ copy C02/C05 và selected FINAL C06 đã có.
Retry cùng input/case/run trả output đã lưu; input khác cùng run conflict. Replay
giữ context/proposal bindings và chạy engines không gọi model; read-run chỉ đọc DB.
BackendReview/verifications/registry thật dùng sidecars gắn đúng digest/context,
không tự thêm review hoặc sửa flags để ép kết quả. C09 chưa có giữ NOT_RUN.

## Tái lập demo trên DB mới

```powershell
$newDemo = 'outputs/group_c_demo_' + [guid]::NewGuid().ToString('N')
New-Item -ItemType Directory -Path $newDemo | Out-Null
Copy-Item -LiteralPath outputs/group_c_completion_20261029_172537/prepare_demo.py -Destination $newDemo
Copy-Item -LiteralPath outputs/group_c_completion_20261029_172537/verify_demo.py -Destination $newDemo
.\.venv\Scripts\python.exe -X utf8 "$newDemo/prepare_demo.py" --base-url $env:TEST_DATABASE_URL
.\.venv\Scripts\python.exe -X utf8 "$newDemo/verify_demo.py"
```

Prepare chỉ nạp whitelist knowledge/upstream từ workbook local và giữ flags nguồn;
không đọc/nạp reference C07–C11 hoặc observations. Driver save/read/retry/replay,
lưu thêm run mới rồi đọc lại run cũ, đối chiếu DTO/hashes/normalized rows/lineage
và chặn mọi engines trong read mode. Không cần API key hoặc PDF download.

```powershell
# Sau khi xong, dừng riêng instance test; giữ dữ liệu lịch sử:
& $pg -D $cluster -m fast -w stop
```
