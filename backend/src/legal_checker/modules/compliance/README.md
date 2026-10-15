# compliance

Bước 5: nhận C05, C06 và knowledge được khóa phiên bản; tạo C07 rồi tổng hợp C08.

Hiện chỉ có skeleton. Các entrypoint giữ chữ ký để nối contracts và đều phát sinh `NotImplementedError`; chưa có logic rule, LLM, tổng hợp hoặc sinh kết quả. Module được gọi qua hàm Python, không có HTTP endpoint riêng.

Người phụ trách triển khai logic trong các file đã đặt tên, query DB qua repository của module, kiểm tra input/output theo `shared/contracts/`, rồi bổ sung tests riêng. Contracts, schema DB và dữ liệu seed tham chiếu được giữ để phát triển song song.

Input provider dùng chung một interface: `ObservationProvider.observe` trong `observations.py`,
được inject qua `DraftModules.observations`. Adapter tạo các `Observation` từ C05/C06,
profile/facts và knowledge; các gates phải dựa trên kiểm tra thật, không tin flags do
LLM tự khai báo. Observation vẫn là đầu vào đề xuất, chưa phải C07 đã xác minh.
