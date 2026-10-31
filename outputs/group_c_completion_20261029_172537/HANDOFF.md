# Bàn giao hoàn thành nhóm C

**Giai đoạn 1–3 đã đạt nghiệm thu kỹ thuật trong phạm vi nhóm C.**
Kiểm chứng cuối 29/10/2026 18:00, Asia/Saigon. Không có paid API calls hoặc DB dev
writes. Source knowledge và outputs vẫn giữ draft/unverified/PENDING.

## Kết quả kiểm chứng

- **1259 passed, 0 failed/errors, 0 skipped**, full pytest theo cấu hình repo.
- Ruff check toàn repo: **All checks passed**. Ruff format --check: **278 files already formatted**.
- Installed package và migration resources import được từ thư mục ngoài repo.
- Python **3.14.0**, PostgreSQL **18.4** native, test instance loopback **55433**;
  CI config khai báo Python3.12/PG17.10. Đây là local execution của required commands,
  không phải tuyên bố đã chạy remote GitHub Actions.
- Một warning deprecation Starlette/httpx còn từ dependency, không ảnh hưởng kết quả.

Exact commands, interpreter, exit codes và timestamp: `checks.json`.
Logs: `ruff_check.log`, `ruff_format.log`, `pytest.log`, `installed_package.log`.
JUnit: `pytest.xml`. Không dùng kết quả 1009 scoped của giai đoạn 2 làm bằng chứng cuối.

## Luồng dữ liệu và ownership

C05 + selected FINAL C06 + chunks/facts/chứng từ và pinned knowledge tạo proposal;
backend verification/review độc lập tạo Observation cho C07. C08 tổng hợp checklist
đầy đủ theo AGG_CAN_HO_V1. C07 và C09 độc lập hội tụ tại C10, sau đó C11 render theo
mapping/templates đã pin. Store lưu normalized rows, full DTO, pins và lineage trong
một transaction; reader chỉ chọn đúng case/run, không chạy lại engines.

Hướng dẫn API Python, mapping DB và trách nhiệm nhóm D:
[docs/group_c_handoff.md](../../docs/group_c_handoff.md).
Đặc biệt C10 SQL PK `ket_qua_id` là DTO `ket_qua_rui_ro_id`; compliance source là
C07 result ID, citation source là C09 finding ID; C11 bind đúng risk instance.
Không lấy catalog ID hoặc run mới nhất để ghép report.

## Các phần đã hoàn thiện

| Phần | Implementation chính | Bằng chứng |
|---|---|---|
| C07 | compliance reasoner/provider/review/grounding/numeric helpers | Bốn findings, full resolved checklist, exact quotes/codepoint offsets, độc lập proposal/review, registry, Decimal/scope/target gates |
| C08 | requirement_aggregator.py | AGG_CAN_HO_V1 precedence, missing/unresolved, N/A không che gap, counts/coverage/snapshots |
| C10 | risks mappers/policy/aggregator/service | C07/C09 source XOR, ownership/context/hash, guards, severity, stable dedup và matched-rule provenance |
| C11 | recommendations generator/validator/service | Instance binding, ALL selection, required elements/facts/limits, verification-only actions, PENDING metadata |
| Workflow/runner | compliance service, steps_5_7, draft workflow, run_group_c.py | DI, no fake upstream, diagnostics, offline/replay/save/read/export, flags và atomic artifacts |
| PostgreSQL | assessments repository/integrity | Exact history, checksum/pins/lineage/normalized checks, retry/conflict/concurrency/rollback/tampering, no-recompute reader |
| Contracts/checks/docs | JSON bundle, migration/storage fixes, READMEs/guides | Full checks và regressions đã chạy thực tế |

Kiểm kê knowledge được đối chiếu lại với source workbook SHA và engine hiện tại:
**441 criteria, 7 types, 12 numeric schemas** trong `knowledge_inventory.json`.
Nhận diện schema không đồng nghĩa facts/source/luật đã được xác minh cho một ca thật.

## Demo mới có nguồn rõ ràng

DB: `legal_checker_test_group_c_completion_8b39db4ae691`.
Case: `CA360_001`; source upstream run: `CA360_001_PDF360_LS2_REFERENCE`.
Whitelisted knowledge/C02/C05/C06 được lấy từ workbook local; không đọc/nạp
C07/C08/C10/C11 EXPECTED hoặc observations tham chiếu. Bốn bảng output ban đầu rỗng.

- Run chính: `CA360_001_C07_DEV_2a016b0fce614af78ae65af5f89dc5a9`.
- Run mới hơn: `CA360_001_C07_DEV_3398fe97ea984c42a19c15d91331d8ef`.
- Knowledge SHA: `c47aa957127751775c850ea63b9ae1d0a57d6a05bfc7f65452738f243eaefdc4`.
- Input SHA: `e2cbe07744063f58ac40d7df8a17b823e083557ff40500dbda51c78ef5246009`.
- Output SHA: `253c117c444a8fee7851fe6f44732634b111f3d686e7cf7a43251c9f59308f95`.

| Output run chính | Số lượng / trạng thái |
|---|---|
| C05 / selected FINAL C06 | 10 / 5 |
| C07 | 9 UNKNOWN |
| C08 | 10 INSUFFICIENT |
| C09 | 0, branch NOT_RUN |
| C10 / C11 | 9 VERIFICATION / 9 recommendations |
| Full output lineage | 37 rows đúng case/run |

UNKNOWN có lý do cụ thể: thiếu C06 cho một số criteria, facts/source/scope/exceptions,
backend review và C05 resolution chưa đủ. Không ép known finding từ dữ liệu chưa
review. Bốn findings và các C09 states được kiểm chứng riêng bằng business tests;
43 persistence cases có cả known synthetic observations, hai nhánh và tampering.

`demo_verification.json` chứng minh save/read DTO, hashes, normalized projections,
lineage và artifact bytes khớp; retry trả output gốc; replay dùng analyses thật đã
xuất và không gọi model. Sau khi lưu run mới hơn, read run cũ vẫn khớp đầy đủ.
Hai lần read đều chặn 10 engine/provider/Knowledge/source loader entrypoints:
**0 calls**, không recompute và không chọn latest run.

Folders `demo_verified_saved/read/retry/replay/newer/historical_read` giữ DTO đầy đủ,
diagnostics và sidecars. `knowledge_snapshot.json`, `case_pins.json`, `saved_runs.json`
và `normalized_rows.json` giữ nội dung DB đọc bằng transaction read-only.
Workbook SHA trong `demo_source.json` khác knowledge content SHA một cách có chủ ý.

## Sửa chữa giai đoạn 3

- Đồng bộ hai trường `diagnostics` thiếu trong bundle JSON, không đổi schema record
  C05–C11 đã khớp runtime. Machine contract suite: 23 passed.
- SQL checksum chỉ chuẩn hóa CRLF→LF tại resource boundary, giữ nguyên checksum
  lịch sử và baseline. SQL content/whitespace/BOM/lone-CR tampering vẫn bị từ chối.
- PG18 catalog NOT NULL khác PG17: loại bản ghi metadata trùng `contype='n'`, tiếp
  tục fingerprint `attnotnull`; test drop NOT NULL vẫn từ chối legacy adoption.
- Cache Windows xử lý cả Win32 sharing errors và CRT errno13/winerror=None với
  retry hữu hạn; persistent failures vẫn explicit. Publisher chỉ chấp nhận winner
  byte-identical đã verified. Race thực được tái hiện trước sửa và kiểm chứng 10 vòng.
- ZIP kiểm tra raw `orig_filename` và normalized filename; fixture giữ raw backslash,
  NUL và alias để test thực sự chứa tên nguy hiểm trên Python3.14.
- CLI help dùng ASCII để chạy được cả console cp1258. Ruff chỉ sửa imports/format
  và các dòng dài cần thiết; không ignore hoặc xóa/làm yếu tests.

`initial_pytest.*` và `cache_race_diagnostic.json` là bằng chứng điều tra thất bại
ban đầu; `checks.json`/`pytest.xml`/`cache_race_after.json` là trạng thái sau sửa.
Không sửa migration SQL lịch sử hoặc `legacy_baselines.json` để làm tests xanh.

## Gói bàn giao và cách chạy

- `source_bundle.zip` + `source_manifest.json`: snapshot backend/docs/scripts từ
  working tree hiện tại, gồm untracked implementations/tests; không gồm venv, DB
  cluster hoặc private workbook. Dùng trên clone repo nền; không phải frontend package.
- `tracked_changes.patch`: tracked diff từ foundation commit `7065df7`; không thay
  source ZIP khi cần khôi phục untracked files.
- `package_metadata.json`: HEAD/base commit, versions, exact results, demo IDs,
  canonical/raw SQL hashes và source ZIP hash.
- `artifact_manifest.json`: SHA-256 từng artifact; ZIP ngoài cùng có `.zip.sha256`.
- [powershell.md](powershell.md): start test DB, full checks, offline/save/read/replay
  và tái lập demo trên một DB mới, không ghi đè artifacts.

Instance test đã dừng sạch sau nghiệm thu; dữ liệu vẫn giữ trong
`data/private/group_c_phase2_postgres/cluster`. Khởi động lại theo PowerShell guide
trước khi đọc DB demo hoặc chạy DB tests. Không dùng DB dev để chạy destructive tests.

## Phụ thuộc ngoài nhóm C

OCR/Scope/Temporal/Retrieval/Citation upstream thật, UI, C12 human legal review và
C13 publish/export vẫn do nhóm khác phụ trách. Saved group-C DTOs không đủ tự dựng
toàn bộ C01–C04 của report. C13 builder chưa tự nhúng mọi diagnostics/exclusions;
nhóm D cần giữ/hiển thị chúng khi ghép report. Không thêm HTTP endpoint riêng cho
từng bước hoặc fake upstream để lấp giới hạn đó.

Không còn blocker kỹ thuật nhóm C được phát hiện trong phạm vi kiểm chứng này.
Khi ghép upstream thật, tiếp tục giữ ownership/pins, draft/unverified/PENDING và
uncertainty; chỉ human review có thẩm quyền mới đổi trạng thái phê duyệt cuối.
