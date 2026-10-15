# recommendations

Bước 7: nhận C10 và knowledge; tạo C11 chờ human review.

Hiện chỉ có skeleton. Các entrypoint giữ chữ ký để nối contracts và đều phát sinh `NotImplementedError`; chưa có logic rule, LLM, tổng hợp hoặc sinh kết quả. Module được gọi qua hàm Python, không có HTTP endpoint riêng.

Người phụ trách triển khai logic trong các file đã đặt tên, query DB qua repository của module, kiểm tra input/output theo `shared/contracts/`, rồi bổ sung tests riêng. Contracts, schema DB và dữ liệu seed tham chiếu được giữ để phát triển song song.
