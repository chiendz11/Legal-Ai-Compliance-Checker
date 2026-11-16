# Hướng dẫn Triển khai Nhóm B (Bước 3–4: Legal Scope, Citation Validation & Retrieval)

Thử nghiệm Retrieval hiện hành: [source/structural context V2](../guides/legal_document_methods_trial_20261109.md).
C06 phân biệt đoạn tìm thấy với ngữ cảnh cha/dẫn chiếu qua scores; ngữ cảnh được chọn
không tự là evidence chứng minh một kết luận. Không trộn chunk IDs của seed với extraction mới.

Cập nhật tích hợp 09/11: Temporal Resolver nhận persisted C01: ngày khai báo chỉ dùng đúng loại mốc, có provenance riêng và không được ghi đè ngày C02 mâu thuẫn. Scope trọng tài có binding dự thảo hạn chế.
Xem [đặc tả và kết quả sửa](../guides/remaining_verification_alignment_20261109.md).

Dataset hiện hành: [TEAM_BASELINE_20261107](../guides/dataset_team_baseline_20261107.md). Dùng scope 36 atomic requirements và topic mapping; không lọc bằng 10 parent families cũ rồi bỏ mất nhóm nguồn.

> **Người phụ trách**: Người 3 · **Input**: C02, C03, Chunks, Legal DB · **Output**: C04, C05 (ApplicableRequirement), C06 (RetrievalEvidence), C09 (CitationValidation)

Đặc tả hiện hành: [INTEGRATION_V1](../contracts/integration_spec.md), [dictionary](../contracts/data_dictionary.md).

Bàn giao bắt buộc: [playbook năm người](../guides/parallel_development_playbook.md), [acceptance scenarios](../contracts/handoff_acceptance.json). Recipe SQL baseline/standalone bên dưới không thay source live workflow_runs/report_versions.

Tài liệu chung: [Tổng quan module & Quy tắc JOIN](README.md)

Revision tri thức 06/11: dùng [policy scope/temporal](../contracts/knowledge_applicability_policy.md)
để phân biệt ngày chọn pháp luật và sự kiện thực hiện. Release TEAM 07/11 đã dựng lại runtime/QA cùng pin; nhận xét giữ pin 05/11 chỉ dành revision lịch sử. Không gán hash mới lên expected cũ.

---

## 5. Nhóm B: bước 3–4: Applicable Law, Citation Validation và Retrieval

Nhóm này có **hai nhánh độc lập ở bước 3**; bước 4 chỉ tiếp tục nhánh Applicable Law.
C09 gửi cho Risk/Report, không dùng để thêm/bớt checklist C05.

### 5.1 Bước 3A.1: Scope Resolver → C04

**Nhận:** C02 profile/chủ thể và knowledge phạm vi/requirement families.
**Trả:** `list[ScopeResolution]`, tức C04.

Đọc: `knowledge.loai_hop_dong`, `pham_vi_ap_dung`, `yeu_cau_phap_ly`, các metadata
cần thiết của `phien_ban_yeu_cau`; đọc `runtime.ho_so_hop_dong`, `chu_the_hop_dong`.

Đọc runtime rows ở trên là recipe dev/baseline. Live nhận C02 của extraction đang
chạy; không đọc profile bảng đơn để thay DTO mới. Knowledge luôn từ snapshot pin.

Làm lần lượt:

1. Dựng profile DTO từ giá trị đã chọn, giữ unknown và provenance.
2. Lấy các scope predicates liên quan; viết interpreter cho dạng JSON được hỗ trợ.
3. Đánh giá ba trạng thái: MATCH / NO_MATCH / UNKNOWN. Thiếu fact không mặc định NO_MATCH.
4. Tạo checklist requirement families và lý do; giữ profile/scope condition snapshot.
5. Trả C04 với `yeu_cau_ca_id`, `ca_id`, `requirement_id`, `scope_status`, `scope_reason`.
6. Live trả C04 trong memory, Temporal dùng cùng IDs; workflow lưu snapshot. Nếu làm writer normalized riêng cho standalone, Scope chỉ sở hữu cột scope và Temporal cột temporal; không ghi đè baseline. Không cần thêm writer DB giữa mỗi hàm.

Không chọn requirement chỉ vì hợp đồng viện dẫn nó. Một luật không được viện dẫn
vẫn có thể tạo requirement áp dụng theo profile.

### 5.2 Bước 3A.2: Temporal Resolver → C05

**Nhận:** C02 + C04 + phiên bản requirement/metadata thời gian/chuyển tiếp.
**Trả:** `list[ApplicableRequirement]`, tức C05.

Đọc: `knowledge.phien_ban_yeu_cau`, `van_ban_phap_ly`, `quan_he_van_ban`,
`ngoai_le_ap_dung`, nguồn/điều khoản cần xác minh và `runtime.moc_thoi_gian_hop_dong`.
Live trả C05 vào workflow; ghi normalized chỉ thuộc use case baseline/standalone đã chọn, không bắt buộc trước Retrieval live.

Làm lần lượt:

1. Chọn mốc đúng nghĩa vụ/ngữ cảnh: ngày giao kết, hiệu lực hoặc mốc liên quan có evidence.
   Không dùng ngày chạy dev để thay mọi relevant date.
2. Chọn version trong khoảng hiệu lực `[từ, đến)` theo policy đã kiểm tra.
3. Xét thay thế/sửa đổi/chuyển tiếp và ngoại lệ; các điều kiện chưa đủ giữ chưa resolve.
4. Giữ nguyên `requirement_id`, `scope_status` và checklist của Scope Resolver.
5. Ghi version ID, mốc/loại mốc, resolution method, source snapshot và lý do.
6. Validate C05: CONFIRMED cần MATCH + RESOLVED + version ID + relevant date.

BRD phụ lục nêu cả NO_VERSION/CONFLICT. DTO C05 hiện chỉ nhận
`version_status = RESOLVED | UNKNOWN`; xem mục 8.3 trước khi mở rộng enum.

Query để xem C05 nguồn và phiên bản:

```sql
SELECT a.*, v.noi_dung AS noi_dung_requirement,
       v.hieu_luc_tu, v.hieu_luc_den, v.source_van_ban_id, v.dieu_khoan_id
FROM runtime.yeu_cau_ap_dung a
LEFT JOIN knowledge.phien_ban_yeu_cau v USING (requirement_version_id)
WHERE a.ca_id = 'CA360_001'
ORDER BY a.yeu_cau_ca_id;
```

C05 được dùng cho **cả Retrieval và Compliance/Aggregation**: giữ requirement/version
và trạng thái áp dụng của ca, không chỉ là thông tin chuyển riêng từ Temporal sang Retrieval.

### 5.3 Bước 3B: Citation Validator → C09

**Nhận:** C03 + C02/context, metadata pháp lý và relevant date.
**Trả:** `list[CitationValidation]`, tức C09.

Đọc: `runtime.vien_dan_phap_ly_hop_dong`, `bang_chung_vien_dan`, chunks/mốc/profile;
`knowledge.van_ban_phap_ly`, `quan_he_van_ban`, `nguon_phap_ly`, các nguồn liên quan.
Projection baseline/standalone: `runtime.phat_hien_vien_dan`; live trả C09 vào draft,
không bắt buộc ghi bảng này trước khi gọi Risk.

Làm lần lượt theo các files trong `modules/citation_validation/`:

1. `normalizer.py`: chuẩn hóa citation có evidence, giữ nguyên raw; nhiều ứng viên
   định danh chưa phân biệt được thì giữ UNKNOWN.
2. `identity_validator.py`: dùng [policy định danh V2](../contracts/citation_identity_policy.json):
   số hiệu, tên+năm khớp duy nhất hoặc anchor số hiệu trong cùng hợp đồng; không
   tự chọn bản mới nhất hoặc bản đang hiệu lực để đoán ý viện dẫn.
3. `temporal_validator.py`: xét hiệu lực/thay thế tại relevant date; current status lưu riêng.
4. `domain_validator.py`: xét phù hợp giao dịch/chủ thể/vấn đề pháp lý.
5. `classifier.py`: trả VALID / STALE / INVALID / UNKNOWN với reason code, lý do và nguồn.
6. `service.py`/writer: validate case/citation IDs, lưu finding + snapshot + run/version.

Ví dụ test nghiệp vụ bắt buộc: citation hợp lệ ngày ký nhưng bị thay thế sau đó vẫn
VALID cho đánh giá lịch sử; có thể hiển thị current status đã hết hiệu lực riêng.
Citation sai domain có reason/risk phù hợp, nhưng không đổi compliance label.

```sql
SELECT f.finding_id, f.ca_id, f.vien_dan_id, f.van_ban_id, f.trang_thai,
       f.ma_ly_do, f.moc_ap_dung, f.finding_verified, f.lan_chay_id
FROM runtime.phat_hien_vien_dan f
WHERE f.ca_id = 'CA360_001'
  AND f.lan_chay_id = 'REF_TEAM_20261107_CA360_001'
ORDER BY f.finding_id;
```

### 5.4 Bước 4: Retrieval → C06

**Nhận:** C05 + chunks đúng hợp đồng + criteria của các requirement versions đã chọn.
**Trả:** `list[RetrievalEvidence]`, tức C06 có liên kết **per-criterion**.

Đọc: `runtime.yeu_cau_ap_dung`, `doan_hop_dong`; knowledge `tieu_chi_danh_gia`,
`phien_ban_yeu_cau`, policies liên quan; index/embedding của đúng phiên bản.
Projection baseline/standalone: `runtime.ket_qua_truy_xuat`; live trả C06 vào draft. Nếu triển khai embeddings, ghi
`runtime.embedding_doan_hop_dong` và metadata model/index.

Làm lần lượt:

1. Dùng `RetrievalDatasetRepository.load_input_rows(ca_id)` để lấy case, C05 source rows,
   chunks và criteria. Map C05/chunks sang DTO; kiểm tra quyền trước khi đọc.
2. Với requirement chưa resolve, giữ trạng thái chưa đủ dữ liệu; không chọn version ngẫu nhiên.
3. Dựng query theo từng criterion từ nội dung requirement/criterion/evidence cần tìm.
4. Xây index toàn tài liệu; search ứng viên và lọc đúng contract/index version.
5. Rerank/select theo criterion; phát hành C06 có `yeu_cau_ca_id`, `tieu_chi_id`, `doan_id`.
6. Ghi score/rank, stage, selected flag và model/retrieval/index/run versions.
7. Evidence rỗng vẫn là kết quả retrieval hợp lệ của criterion đó; bước 5 quyết định
   UNKNOWN hay MISSING dựa thêm coverage/absence gates, không phải retrieval tự kết luận.

Ví dụ dùng repository hiện có:

```python
import os
from dotenv import load_dotenv
from legal_checker.modules.retrieval.repository import RetrievalDatasetRepository

load_dotenv(".env")
repository = RetrievalDatasetRepository(os.environ["DATABASE_URL"])
inputs = repository.load_input_rows("CA360_001")
candidates = repository.load_seeded_evidence("CA360_001", "REF_TEAM_20261107_CA360_001")
print(len(inputs["requirements"]), len(inputs["chunks"]), len(candidates))
```

`candidates` là rows mẫu, cần map/validate C06; với bộ 360 đã có criterion ID.
Khi chạy Retrieval thật, module của bạn phải tự tìm/chọn evidence per-criterion.
File `retriever.py`, `indexer.py`, `reranker.py`, `service.py` đã có điểm đặt implementation.

Embedding seed cần giữ đúng nhãn model/index. Không gọi vector baseline từ vựng là
semantic embedding của LLM; khi đổi embedding model phải xây index tương ứng.

### 5.5 Test và bàn giao nhóm B

- Profile thiếu fact → Scope UNKNOWN; luật không được viện dẫn vẫn có thể áp dụng.
- Ngày đúng tại biên hiệu lực; thiếu ngày; chuyển tiếp chưa rõ → trạng thái/lý do đúng.
- Đổi C09 VALID thành STALE không thay C04/C05/C08.
- Citation ambiguity, sai số hiệu/domain, nguồn chưa xác minh → không đoán VALID.
- C06 đúng case/contract/criterion/run; Recall@K đo trên evidence đã annotation.
- Search toàn hợp đồng, không chỉ các đoạn có tên luật; retrieval miss không thành VIOLATED.

```bash
pytest -q -c backend/pyproject.toml backend/tests/contract/test_db_handoffs.py -k legal
pytest -q -c backend/pyproject.toml backend/tests/contract/test_db_handoffs.py -k retrieval
```

Đây là tests DB handoff/provenance; bổ sung query/mapping riêng của implementation và eval.
Bàn giao C04/C05 cho Retrieval/Compliance, C09 cho Risk/Report, C06 cho Compliance.

### 5.6 Recipe đọc/join cho nhóm B: C02 → C04 → C05 → C06, nhánh C03 → C09

#### B1 — Scope: đọc profile trước, JOIN family với điều kiện phạm vi

**Input upstream:** C02 của nhóm A. Khi dev riêng, đọc Q11–Q14 hoặc C02 QA; không đọc
`yeu_cau_ap_dung.scope_status` để trả chính trạng thái Scope của implementation mình.

```sql
-- Q20_SCOPE_CATALOG: family → N scope clauses; chưa chọn version/criterion.
SELECT r.requirement_id, r.ten_nhom_yeu_cau, r.nhom_nghia_vu, r.che_do_ket_hop,
       s.pham_vi_id, s.nhom_phien_ban, s.loai_hop_dong_id,
       s.doi_tuong, s.loai_chu_the, s.linh_vuc,
       s.dieu_kien_scope, s.dieu_kien_json, s.trang_thai,
       l.ten_loai, l.loai_cha_id
FROM knowledge.yeu_cau_phap_ly r
LEFT JOIN knowledge.pham_vi_ap_dung s ON s.requirement_id=r.requirement_id
LEFT JOIN knowledge.loai_hop_dong l ON l.loai_hop_dong_id=s.loai_hop_dong_id
ORDER BY r.requirement_id, s.pham_vi_id;
```

Vì UNKNOWN loại hợp đồng vẫn cần được xử lý, ví dụ đọc catalog trước rồi interpreter
đánh giá trên C02. Nếu tối ưu query theo loại/subtype, phải xét scope tổng quát, loại cha
và nhóm chưa đủ facts; không lọc mất chúng chỉ vì giá trị profile NULL. Nhiều scope clauses
của một family cần đọc `che_do_ket_hop`/policy để quyết định AND/OR, không coi mỗi row là
một requirement độc lập. Baseline TEAM có scope tham chiếu 36 atomic requirements/ca trong ASSESSMENT_SCOPE.json; live xét catalog pin (323 families). Không tự hiểu reference đã annotate toàn bộ luật.

**Output:** C04 giữ `requirement_id`, group, trạng thái và lý do/predicate/profile snapshot.
Sinh `yeu_cau_ca_id` ổn định cho family thuộc case. Ghi phần scope của `yeu_cau_ap_dung`.
Temporal tiếp tục trên chính IDs/checklist này. Không JOIN citations để tạo checklist.

#### B2 — Temporal: từ C04 lấy tất cả candidate versions và đúng mốc

Q13_MARKERS là output DI cung cấp các mốc. Với một C04, JOIN bằng **requirement_id**
để xem candidates; `requirement_version_id` là kết quả của resolver, chưa có từ đầu.

```sql
-- Q21_VERSION_CANDIDATES: a là C04 đã lưu của run/checklist đang chọn.
SELECT a.yeu_cau_ca_id, a.requirement_id, a.nhom_phien_ban AS scope_group,
       a.scope_status, v.requirement_version_id, v.nhom_phien_ban AS version_group,
       v.hieu_luc_tu, v.hieu_luc_den, v.loai_moc_ap_dung,
       v.quy_tac_chuyen_tiep, v.dieu_kien_ap_dung, v.trang_thai_runtime,
       v.can_xac_minh_scope, v.can_xac_minh_chuyen_tiep,
       vb.van_ban_id, vb.so_hieu, vb.trang_thai_xac_minh
FROM runtime.yeu_cau_ap_dung a
LEFT JOIN knowledge.phien_ban_yeu_cau v ON v.requirement_id=a.requirement_id
LEFT JOIN knowledge.van_ban_phap_ly vb ON vb.van_ban_id=v.source_van_ban_id
WHERE a.ca_id=%(case_id)s
ORDER BY a.yeu_cau_ca_id, v.hieu_luc_tu, v.requirement_version_id;
```

Query trả candidates, **không tự giải quyết version**. Service phải:

1. Giữ group/phạm vi từ C04; đọc loại mốc và policy của candidate.
2. Chọn ngày có provenance tương ứng từ C02; nếu ngày NULL thì giữ UNKNOWN.
3. Kiểm tra interval, amendment/replacement, transition và ngoại lệ.
4. Nếu nhiều candidates còn hợp lệ/chưa rõ ưu tiên, giữ UNKNOWN + lý do; không `LIMIT 1`.
5. Trả C05 với version đã chọn hoặc candidate giữ rõ là chưa resolve.

Nếu C04 đang ở memory, gọi `knowledge.versions` theo IDs của C04; query Q21 chỉ là cách
đọc các rows đã lưu trong DB. `yeu_cau_ap_dung` không có run column; khi thay checklist,
tạo case/checklist version phù hợp hoặc dùng snapshot đã pin, không ghi đè baseline.

Nguồn/version và ngoại lệ đọc thành tập riêng để không nhân dòng:

```sql
-- Q22_VERSION_BASIS: 1 version → N nguồn/điều khoản. Thêm param version_id.
SELECT v.requirement_version_id, v.requirement_id, v.noi_dung,
       n.lien_ket_id, n.vai_tro, n.vi_tri_cu_the,
       d.dieu_khoan_id, d.vi_tri, d.noi_dung_nguon, d.trang_thai_xac_minh,
       vb.van_ban_id, vb.so_hieu, vb.url_nguon
FROM knowledge.phien_ban_yeu_cau v
LEFT JOIN knowledge.nguon_yeu_cau n ON n.requirement_version_id=v.requirement_version_id
LEFT JOIN knowledge.dieu_khoan_phap_ly d ON d.dieu_khoan_id=n.dieu_khoan_id
LEFT JOIN knowledge.van_ban_phap_ly vb ON vb.van_ban_id=d.van_ban_id
WHERE v.requirement_version_id=%(version_id)s
ORDER BY n.lien_ket_id;
```

`v.dieu_khoan_id`/`source_van_ban_id` còn là basis trực tiếp của version; đọc cả basis này
và quan hệ `nguon_yeu_cau` theo policy. Ngoại lệ lấy ở Q34 dưới đây. Candidate hay row có
nguồn không tự là source_verified/human-approved.

#### B3 — Citation: C03 → candidate legal identity → C09

**Input upstream:** C03/Q15, C02/mốc/Q13. C09 seed chỉ dùng để kiểm tra writer/mapping
hoặc đối chiếu sau classifier. Một citation có thể chưa có số hiệu hoặc tên đầy đủ.

```sql
-- Q23_IDENTITY_CANDIDATES: chuẩn hóa số hiệu trong code rồi bind normalized_number.
SELECT vb.van_ban_id, vb.so_hieu, vb.so_hieu_chuan, vb.ten_van_ban,
       vb.linh_vuc, vb.hieu_luc_tu, vb.hieu_luc_den, vb.van_ban_thay_the_id,
       vb.identity_verified, vb.temporal_verified, vb.domain_verified,
       vb.trang_thai_xac_minh,
       s.nguon_id, s.url, s.duong_dan, s.sha256, s.trang_thai AS source_status
FROM knowledge.van_ban_phap_ly vb
LEFT JOIN knowledge.nguon_phap_ly s ON s.van_ban_id=vb.van_ban_id
WHERE vb.so_hieu_chuan=%(normalized_number)s OR vb.so_hieu=%(normalized_number)s
ORDER BY vb.van_ban_id, s.nguon_id;
```

Số hiệu khớp là **candidate định danh**, chưa là VALID. Nhóm theo `van_ban_id` (mỗi văn bản
có thể nhiều nguồn), đối chiếu tên/loại/ngày, rồi đọc quan hệ thay thế/sửa đổi:

```sql
-- Q24_LEGAL_RELATIONS: thêm param document_id của candidate đã chọn.
SELECT * FROM knowledge.quan_he_van_ban
WHERE van_ban_nguon_id=%(document_id)s OR van_ban_dich_id=%(document_id)s
ORDER BY moc_hieu_luc, quan_he_id;
```

Nếu số hiệu chưa rõ, áp dụng policy V2 để phân biệt identity đã phân giải với
candidates; tên không năm/số/anchor giữ UNKNOWN. Không tự sửa
OCR để ép Q23 có kết quả. Không dùng Q24 như bằng chứng sửa đổi toàn bộ văn bản khi quan
hệ chỉ ảnh hưởng một phạm vi. C09 giữ relevant/current status riêng, nguồn evidence và run.

#### B4 — Retrieval: requirement instance → version → criteria; chunks đọc riêng

**Input upstream:** C05 của Temporal + chunks của DI. Đọc Q25 để dựng danh sách targets:

```sql
-- Q25_RETRIEVAL_TARGETS: giữ cả unresolved requirements khi LEFT JOIN chưa có criteria.
SELECT a.yeu_cau_ca_id, a.requirement_id, a.requirement_version_id,
       a.scope_status, a.version_status, a.applicability_status, a.moc_ap_dung,
       v.noi_dung AS requirement_text,
       c.tieu_chi_id, c.thu_tu, c.noi_dung AS criterion_text,
       c.bang_chung_can_thiet, c.loai_kiem_tra, c.pham_vi_kiem_tra,
       c.noi_dung_bat_buoc_trong_hd
FROM runtime.yeu_cau_ap_dung a
LEFT JOIN knowledge.phien_ban_yeu_cau v
  ON v.requirement_version_id=a.requirement_version_id AND v.requirement_id=a.requirement_id
LEFT JOIN knowledge.tieu_chi_danh_gia c ON c.requirement_version_id=v.requirement_version_id
WHERE a.ca_id=%(case_id)s
ORDER BY a.yeu_cau_ca_id, c.thu_tu, c.tieu_chi_id;
```

```sql
-- Q26_CHUNKS: toàn bộ chunks đúng contract; không cần có citation hoặc evidence sẵn.
SELECT d.doan_id, d.hop_dong_id, d.section_path, d.page_start, d.page_end,
       d.noi_dung, d.chunk_quality, d.sha256_text, d.phien_ban_chunk, d.thu_tu
FROM runtime.ca_danh_gia ca
JOIN runtime.doan_hop_dong d ON d.hop_dong_id=ca.hop_dong_id
WHERE ca.ca_id=%(case_id)s ORDER BY d.thu_tu, d.doan_id;
```

Map Q25 → C05/target criteria, Q26 → `Chunk[]`, dựng `RetrievalInput(context, hop_dong_id,
requirements, chunks)`. Criteria/catalog inject qua Knowledge. **Không JOIN mọi target
với mọi chunk trong SQL để gửi hàng nghìn dòng trùng text**; index chunks một lần rồi
search/rerank theo từng criterion. NOT_APPLICABLE bỏ search có lý do; UNKNOWN vẫn giữ
trạng thái trong C05, candidate version chưa được coi là resolved chỉ vì có criteria.

C06 không chứa quote/offset; nó chỉ định chunk, scores/rank/stage/model/run. Quote được
reasoner chọn và kiểm chứng khi tạo C07. Nếu không tìm thấy selected evidence, C06 có thể
rỗng cho target nhưng cần checkpoint/coverage của lần retrieval để phân biệt chưa chạy
với chạy rồi không tìm thấy; một bảng evidence rỗng tự nó không phân biệt được hai việc.

**Nơi bàn giao:** live truyền C04/C05/C06/C09 bằng DTO, giữ trong workflow_runs.draft_json khi hoàn thành; Documents được persist trước vì Retrieval đọc metadata. Các bảng yeu_cau_ap_dung/phat_hien_vien_dan/ket_qua_truy_xuat ở trên là projection baseline/standalone, không phải bắt buộc thêm writer cho mỗi live stage. Nhóm C nhận C05/C06 và C09; nhóm D đọc cùng draft/run.

