# Quy ước tri thức về phạm vi, phiên bản và mốc áp dụng

> Baseline hiện hành cho DB mới: [PDF360 v4 r2 — 10/11](../guides/dataset_pdf360_v4r2_runtime_20261110.md).
> Knowledge được chủ dự án duyệt, hash `4ab2d7ea296ea908e25c09fcb6d5f073f1ebe1917678b36390f803b1c725804a`; full-catalog reference xét 323 families.
> Số liệu PDF/TEAM_CORE của revision trước bên dưới là lịch sử; literal reference mới chưa phải legal gold toàn tài liệu.


Revision dữ liệu mới: [TEAM_BASELINE_20261107](../guides/dataset_team_baseline_20261107.md). Tám topic có nguồn đồng thời đã được tách theo [mapping](legal_topic_mapping.json), giữ version IDs/hiệu lực. Giới hạn revision 06/11 bên dưới là lịch sử; xem disposition trong guide mới.

Ngày chốt: 06/11/2026. Policy: `LEGAL_VERSION_POLICY_V1`.
Schema máy đọc: [legal_version_policy.schema.json](legal_version_policy.schema.json).
Tài liệu này bổ sung [integration_spec.md](integration_spec.md); không thay C01–C13.

## 1. Workbook chứa gì và mỗi bảng chịu trách nhiệm gì?

| Bảng | Ý nghĩa và cách nối |
|---|---|
| `yeu_cau_phap_ly` | Một family mô tả vấn đề cần kiểm tra, khóa `requirement_id` |
| `pham_vi_ap_dung` | Điều kiện loại hợp đồng, tư cách chủ thể, thuộc tính giao dịch. JOIN family bằng `requirement_id`; `nhom_phien_ban` xác định nhóm nguồn |
| `phien_ban_yeu_cau` | Một phiên bản của family/nhóm nguồn: hiệu lực, nguồn chính, mốc chọn chế độ và chuyển tiếp |
| `van_ban_phap_ly` | Văn bản có danh tính riêng. Không xem một tên ghép hai số hiệu là một văn bản pháp luật độc lập |
| `dieu_khoan_phap_ly` | Nguyên văn điều/khoản/phụ lục; `van_ban_id` phải trỏ đúng văn bản chứa nó |
| `nguon_yeu_cau` | Các căn cứ bổ trợ của cùng phiên bản; không ép mọi căn cứ phải thuộc văn bản chính |
| `tieu_chi_danh_gia` | Từng mệnh đề được đánh giá, JOIN bằng `requirement_version_id`. Mỗi criterion có nguồn trực tiếp, loại kiểm tra và điều kiện riêng |
| `quy_tac_quyet_dinh` | Các điều kiện để ra SATISFIED/MISSING/VIOLATED/UNKNOWN cho criterion |
| `ngoai_le_ap_dung` | Ngoại lệ cần facts/chứng cứ theo ca; chưa phân giải ngoại lệ thì không xác nhận kết luận |

Ví dụ SQL đọc cấu hình phiên bản và nguồn, chưa quyết định phiên bản đó áp dụng:

```sql
SELECT r.requirement_id, v.requirement_version_id, v.nhom_phien_ban,
       v.loai_moc_ap_dung, v.hieu_luc_tu, v.hieu_luc_den,
       v.quy_tac_chuyen_tiep, v.source_van_ban_id,
       a.dieu_khoan_id, a.van_ban_id AS article_document_id
FROM knowledge.yeu_cau_phap_ly r
JOIN knowledge.phien_ban_yeu_cau v USING (requirement_id)
JOIN knowledge.dieu_khoan_phap_ly a ON a.dieu_khoan_id = v.dieu_khoan_id
WHERE r.requirement_id = %(requirement_id)s
ORDER BY v.nhom_phien_ban, v.hieu_luc_tu;
```

Không JOIN tất cả scope × versions × criteria rồi lấy dòng đầu. Resolver phải xử lý
đúng nhóm nguồn và khoảng hiệu lực `[hieu_luc_tu, hieu_luc_den)`. Runtime phải dùng
snapshot pin theo hash; query bảng đang sửa chỉ dành cho biên soạn và kiểm tra dữ liệu.

## 2. Tách ngày chọn pháp luật khỏi ngày chứng minh thực hiện

Policy này chỉ chuẩn hóa **đánh giá hợp đồng tại thời điểm xác lập**
(`CONTRACT_AT_CONCLUSION`). Nó không chứng nhận toàn bộ việc thực hiện giao dịch
tại ngày hiện tại, và không tự xử lý một phụ lục sửa đổi được lập về sau.

| Giá trị `loai_moc_ap_dung` | Ngày lấy từ C02 | Ví dụ sử dụng |
|---|---|---|
| `SIGNING` | Marker SIGNING của hợp đồng đang xét | Hình thức/nội dung/quyền nghĩa vụ tại khi xác lập; sự kiện thực hiện được xét riêng |
| `TEMPLATE_USE` | Ngày bắt đầu dùng/công khai mẫu được chứng minh | Danh mục/đăng ký mẫu và điều kiện giao dịch chung; không tự lấy ngày ký thay thế |
| `DEPOSIT_AGREEMENT` | Ngày xác lập thỏa thuận đặt cọc đang xét | Quy định đặt cọc; không tự suy từ lịch thu tiền hoặc ngày hợp đồng mua bán |
| `COLLECTION` | Ngày thu tiền thực tế có chứng từ | Được schema hỗ trợ cho policy cần đúng sự kiện thu tiền; revision này không tự tạo ngày đó |

Trong revision 06/11 có 337 phiên bản dùng SIGNING, năm dùng TEMPLATE_USE và một
dùng DEPOSIT_AGREEMENT. Đây là lựa chọn của phạm vi **contract review** đã khai báo,
không phải tuyên bố mọi nghĩa vụ pháp lý đều phát sinh vào ngày ký.

Ví dụ: có thể chọn chế độ pháp luật cho điều khoản bảo hành từ ngày ký; muốn chứng
minh đã hết 60 tháng phải có ngày nghiệm thu/mốc bắt đầu đúng loại và chứng cứ khác.
Tương tự, điều khoản thanh toán và chứng từ đã thu tiền là hai đầu vào khác nhau.
`performance_events` ghi các loại sự kiện liên quan, **không phải** yêu cầu mọi ca
đều có đủ tất cả sự kiện đó. Người 4 bind sự kiện và facts theo từng criterion.

## 3. Chuyển tiếp là một phần của chọn phiên bản

`quy_tac_chuyen_tiep` vẫn là cột TEXT của schema SQL hiện tại. Bản revision lưu
JSON theo schema ở đầu tài liệu trong cột đó, nên không cần thêm bảng hoặc đổi
cột. JSON có `policy_id`, `review_scope`, `selection_marker`, `performance_events`,
`transition`, nguồn và `criteria_ready`. Prose cũ được lưu trong changelog ngoài Git.
Resolver cũ chỉ đọc prose không đủ; cần dùng code đi kèm revision này.

Các quyết định đối chiếu nguồn:

- Mốc hiệu lực Luật Nhà ở và Luật KDBĐS 2023 được đối chiếu với
  [Luật 43/2024/QH15](https://datafiles.chinhphu.vn/cpp/files/vbpq/2024/9/43-2024-qh15.pdf).
  Không suy mốc 01/01/2025 chỉ từ trang thông tin bản luật ban đầu.
- Điều 83 khoản 9 [Luật 29/2023/QH15](https://datafiles.chinhphu.vn/cpp/files/vbpq/2024/01/luat29.pdf)
  có cơ chế tiếp tục thực hiện hợp đồng cũ và yêu cầu đối với nội dung sửa đổi sau
  ngày luật mới có hiệu lực. Bản contract review giữ ngày xác lập của văn bản đang
  xét; muốn xét sửa đổi mới phải cấp nguồn và mốc riêng.
- Khoản 5 Điều 83 quy định riêng nhà hình thành trong tương lai đủ điều kiện kinh
  doanh trước mốc luật mới; đồng thời vẫn phải công khai theo Điều 6 trước ký.
  Với hợp đồng ký từ 01/08/2024 và profile xác nhận HTTTL, resolver đòi fact boolean
  `transition.future_sale_eligible_before_20240801` có review và evidence. `false`
  cho phép xét chế độ mới; `true` chọn chế độ ngay trước mốc theo quy định chuyển
  tiếp **chỉ cho các điều kiện/thủ tục bán đã khai báo SALE_PROCEDURE_ONLY**;
  thiếu/conflict là UNKNOWN. Không tự suy mọi điều khoản của một hợp đồng mới đều
  theo luật cũ: các nhánh đó giữ CASE_REVIEW. Riêng nhóm Điều 6 vẫn xét công khai theo chế độ
  mới. Nếu catalog không có phiên bản lịch sử cần thiết, vẫn là gap, không sáng tác
  một phiên bản thay thế.
- Điều 80 [Luật 19/2023/QH15](https://vbpl.vn/van-ban/chi-tiet/luat-bao-ve-quyen-loi-nguoi-tieu-dung-so-19-2023-qh15--161263)
  phân biệt giao dịch/mẫu đã tồn tại và tình trạng thực hiện, sửa đổi. Việc đánh
  giá nghĩa vụ đang tiếp tục sau mốc luật mới cần đánh giá chuyển tiếp riêng; code
  chưa tự phân giải toàn bộ nhánh này từ một ngày ký.
- Điều 198 [Luật Nhà ở 27/2023/QH15](https://vbpl.vn/van-ban/chi-tiet/luat-nha-o-so-27-2023-qh15--169032)
  có các nhánh dự án, NOXH, quản lý nhà chung cư. Với NOXH ký từ mốc mới, guard cần
  fact `transition.housing_social_process_before_20240801`; quy trình đã có từ
  trước vẫn cần review nhánh tương ứng. Ghi mã HOUSING_198 không có nghĩa
  đã implement/xác nhận đủ mọi nhánh. Không áp kết quả contract review cho việc
  quản lý/thực hiện hiện tại nếu chưa bổ sung hồ sơ và logic tương ứng.

`can_xac_minh_chuyen_tiep=true` trong revision nói rằng **ca có thể cần kiểm tra
chuyển tiếp**; nó không hủy trạng thái user-reviewed của knowledge. Các nghiệp vụ
chuyển tiếp chưa có implementation đầy đủ được ghi rõ trong báo cáo revision.

## 4. Hai dữ kiện scope đã chốt

| Field chuẩn C02 | Ý nghĩa | Điều gì không được suy ra? |
|---|---|---|
| `la_giao_dich_dien_tu` | Có căn cứ giao dịch sử dụng thông điệp dữ liệu/phương tiện điện tử thuộc phạm vi luật liên quan | Upload một PDF hoặc có email liên hệ không tự chứng minh hợp đồng điện tử |
| `co_thoa_thuan_trong_tai` | Có thỏa thuận trọng tài hoặc hồ sơ yêu cầu giải quyết theo thỏa thuận đó cần kiểm tra | Không phải nút backend “muốn đánh giá trọng tài”; thiếu regex match không đủ để gán false |

Năm scope records đổi tên `can_danh_gia_trong_tai` thành
`co_thoa_thuan_trong_tai`; chín records điện tử giữ tên cũ. C02 bổ sung hai thuộc
tính nullable. Knowledge không tự điền giá trị cho 360 hợp đồng.

Producer 2 phải đưa facts vào `profile.<field>` cùng evidence. Nếu phát triển chế
độ đọc DB, JOIN `runtime.trich_xuat_truong` và `runtime.bang_chung_truong` của đúng
hợp đồng/extraction version, rồi dựng typed fields; không mong hai cột mới đã có
sẵn trong `runtime.ho_so_hop_dong`. Repository Documents hiện lưu facts, nhưng
extractor và các reader của từng nhóm vẫn phải thực hiện mapping theo contract.

Ví dụ lấy facts cùng vị trí nguồn của một extraction để dựng C02:

```sql
SELECT f.trich_xuat_id, f.ten_truong, f.gia_tri_chuan_json,
       f.trang_thai, f.human_verified, b.bang_chung_id,
       b.doan_id, b.trich_dan_nguyen_van, b.ky_tu_bat_dau, b.ky_tu_ket_thuc
FROM runtime.trich_xuat_truong f
JOIN runtime.bang_chung_truong b USING (trich_xuat_id)
JOIN runtime.doan_hop_dong d
  ON d.doan_id = b.doan_id AND d.hop_dong_id = f.hop_dong_id
WHERE f.hop_dong_id = %(contract_id)s
  AND d.phien_ban_chunk = %(extraction_version)s
  AND f.ten_truong IN (
    'profile.la_giao_dich_dien_tu',
    'profile.co_thoa_thuan_trong_tai',
    'transition.future_sale_eligible_before_20240801',
    'transition.housing_social_process_before_20240801'
  )
ORDER BY f.ten_truong, f.trich_xuat_id, b.bang_chung_id;
```

Query này không tự xác minh facts. Mapper phải kiểm tra quote/offset với text
chunk, nhóm các evidence của cùng fact và giữ mâu thuẫn; không lấy dòng đầu để
ghi đè giá trị khác. Không có dòng/evidence là chưa biết, không phải false.

## 5. Nguồn chính, nguồn bổ trợ và nguồn đồng thời

Revision sửa `PV_HYC016` về văn bản chính `VBPL008` và điều chính
`ART_VBPL008_19`; giữ Phụ lục danh mục của
[Quyết định 02/2012/QĐ-TTg](https://vanban.chinhphu.vn/?pageid=27160&docid=154056)
làm nguồn bổ trợ trong `nguon_yeu_cau`. Hai criterion vốn lấy Điều 19 nay thống
nhất với văn bản chính. Mã văn bản ghép cũ được giữ cho lịch sử, không xóa nguồn.

Nhiều luật có thể cùng điều chỉnh một vấn đề; chồng hiệu lực giữa hai nhóm không tự là catalog sai.
Release 07/11 dùng atomic family theo nhóm nguồn, giữ các version IDs và ngày gốc.
C05 vẫn một family/version, không còn phải chọn một nguồn trong tám topic đã chuẩn hóa.
Topic mapping phục vụ nhóm/đếm; không cộng mỗi source-group thành một incident độc lập.

PV_HYC051 đã có 19 criteria cho Mẫu số 01 và criteria_ready=true trong baseline mới.
Tiêu chí mới là SOURCE_CHECKED; đủ metadata không tự phê duyệt proposal, facts hoặc
kết luận mới. Nghiệm thu nội dung/ngoại lệ vẫn theo verifier và proof obligations.

## 6. Phân biệt revision tri thức với release dataset

Bản `KNOWLEDGE_ALIGNED_20261106` sửa tri thức, giữ toàn bộ sheets runtime/QA cũ và
hash lịch sử của chúng. Đây **chưa phải baseline dev/eval mới đã tái nghiệm thu**.
Không thay hash cũ trên đáp án rồi gọi đó là kết quả của policy mới.

Release TEAM_BASELINE_20261107 đã dựng lại runtime/QA và pin manifest; đây là baseline kỹ thuật SILVER/SYNTHETIC_SPEC, không tự là gold độc lập. Dùng guide 07/11 để seed DB mới. Các bước annotation độc lập, module quality và nghiệm thu phát hành vẫn riêng; không lấy việc có gói mới làm bằng chứng đã hoàn thành chúng. Revision lịch sử 06/11 không tự đổi DB/PDF/app đang triển khai.
