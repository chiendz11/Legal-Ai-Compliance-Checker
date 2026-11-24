import { Link } from "react-router-dom";

import { Section } from "../../shared/components/ui";

const STEPS = [
  {
    title: "1. Tải hợp đồng lên",
    text: "Chọn tệp PDF (bản có chữ hoặc bản scan) hoặc DOCX của hợp đồng mua bán căn hộ chung cư. Hệ thống lưu tệp gốc và dấu vân tay của tệp để chứng minh báo cáo được làm trên đúng tệp đó.",
  },
  {
    title: "2. Hệ thống phân tích",
    text: "Đọc hợp đồng, xác định quy định pháp luật nào áp dụng tại ngày ký, kiểm tra từng điều khoản rồi tổng hợp rủi ro và khuyến nghị. Thường mất từ vài chục giây đến vài phút.",
  },
  {
    title: "3. Đọc báo cáo",
    text: "Báo cáo mở ra ở mục Tổng quan: kết luận, lý do và việc nên làm tiếp. Các mục sau đi dần vào chi tiết và bằng chứng.",
  },
];

const SECTIONS = [
  [
    "1. Tổng quan",
    "Đọc mục này trước: kết luận chung, những điểm cần chú ý (quy định không đạt, rủi ro kèm việc cần làm), vì sao một số quy định chưa kết luận được và việc nên làm tiếp.",
  ],
  [
    "2. Kết quả kiểm tra",
    "Toàn bộ quy định cần xét, nhóm theo chủ đề (giá và thanh toán, bàn giao, bảo hành…). Mở từng quy định để xem lý do, các điểm kiểm tra, đoạn hợp đồng làm bằng chứng, điều luật và việc cần làm.",
  ],
  [
    "3. Hợp đồng",
    "Những gì hệ thống đọc được từ hợp đồng (loại hợp đồng, các bên, ngày ký, giá…) và các văn bản luật mà hợp đồng trích dẫn, có đối chiếu còn hiệu lực hay không.",
  ],
  [
    "4. Rà soát và phát hành",
    "Dành cho chuyên viên: xác nhận, sửa hoặc yêu cầu bổ sung từng kết luận, rồi phát hành báo cáo chính thức.",
  ],
  [
    "Chi tiết kỹ thuật",
    "Link nhỏ cuối mục lục, dành cho kỹ sư: bảng xác định phạm vi và thông tin truy vết.",
  ],
  [
    "Xem trong hợp đồng",
    "Ở bất kỳ đâu có nút này, bấm vào sẽ mở bản PDF gốc bên cạnh và tô vàng đúng đoạn được nhắc tới.",
  ],
];

const TERMS = [
  ["Tuân thủ", "Hợp đồng đáp ứng quy định, có đoạn hợp đồng làm bằng chứng."],
  ["Tuân thủ một phần", "Đáp ứng một số điểm kiểm tra, còn thiếu hoặc sai ở điểm khác."],
  ["Không tuân thủ", "Hợp đồng vi phạm hoặc thiếu nội dung bắt buộc của quy định."],
  ["Chưa đủ căn cứ", "Hệ thống chưa đủ thông tin để kết luận. Không có nghĩa là hợp đồng vi phạm. Lý do cụ thể được ghi ở từng quy định và trong mục Tổng quan."],
  ["Quy định áp dụng", "Một yêu cầu pháp luật (ví dụ: đặt cọc không quá 5% giá bán) mà hợp đồng loại này phải đáp ứng tại ngày ký."],
  ["Điểm kiểm tra", "Một ý cụ thể cần kiểm tra trong một quy định. Mỗi quy định có một hoặc nhiều điểm kiểm tra."],
  ["Chưa xác định", "Điểm kiểm tra chưa có kết luận, thường vì chưa chạy AI hoặc chưa tìm thấy đoạn hợp đồng liên quan."],
  ["Bản nháp / Đã phát hành", "Bản nháp là kết quả máy, chưa được chuyên viên duyệt. Chỉ bản Đã phát hành mới dùng như kết luận chính thức."],
];

/** Plain-language guide: what the system does, how to read a report, and the terms it uses. */
export function HelpPage() {
  return (
    <Section
      title="Hướng dẫn sử dụng"
      description="Hệ thống kiểm tra hợp đồng mua bán căn hộ chung cư với quy định pháp luật hiện hành và chỉ ra điểm cần chú ý. Kết quả là bản nháp hỗ trợ chuyên viên, không thay thế ý kiến pháp lý."
    >
      <h3 className="subhead">Cách hoạt động</h3>
      <ol className="help-steps">
        {STEPS.map((s) => (
          <li key={s.title} className="card-flat">
            <strong>{s.title}</strong>
            <p>{s.text}</p>
          </li>
        ))}
      </ol>
      <p>
        <Link className="button primary" to="/upload">
          Tải hợp đồng đầu tiên
        </Link>
      </p>

      <h3 className="subhead" id="che-do">
        Hai chế độ hiển thị
      </h3>
      <dl className="help-list">
        <div>
          <dt>Đơn giản</dt>
          <dd>
            Dành cho người dùng phổ thông. Báo cáo gói trong một trang: kết luận, các điểm cần xem
            lại (quy định yêu cầu gì, hợp đồng đang ghi gì, nên làm gì) và vài lưu ý.
          </dd>
        </div>
        <div>
          <dt>Nâng cao</dt>
          <dd>
            Dành cho chuyên viên: toàn bộ quy định theo chủ đề, điểm kiểm tra, căn cứ pháp lý, thông
            tin đọc từ hợp đồng và phần rà soát, phát hành. Các mục bên dưới mô tả chế độ này.
          </dd>
        </div>
        <div>
          <dt>Đổi chế độ</dt>
          <dd>
            Dùng công tắc “Chế độ hiển thị” ở cuối thanh bên hoặc ở đầu trang báo cáo. Hai chế độ
            đọc cùng một kết quả; chế độ Đơn giản chỉ hiển thị ít hơn.
          </dd>
        </div>
      </dl>

      <h3 className="subhead" id="doc-bao-cao">
        Cách đọc báo cáo (chế độ Nâng cao)
      </h3>
      <dl className="help-list">
        {SECTIONS.map(([title, text]) => (
          <div key={title}>
            <dt>{title}</dt>
            <dd>{text}</dd>
          </div>
        ))}
      </dl>

      <h3 className="subhead" id="thuat-ngu">
        Thuật ngữ
      </h3>
      <dl className="help-list">
        {TERMS.map(([title, text]) => (
          <div key={title}>
            <dt>{title}</dt>
            <dd>{text}</dd>
          </div>
        ))}
      </dl>

      <h3 className="subhead">Giới hạn hiện tại</h3>
      <ul className="help-limits">
        <li>Chỉ đánh giá hợp đồng mua bán căn hộ chung cư; tài liệu loại khác sẽ được báo là không xử lý.</li>
        <li>Tệp DOCX được đọc theo nội dung văn bản; DOCX không có số trang nên không xem song song với báo cáo được (vẫn tải được tệp gốc).</li>
        <li>Bản scan được đọc bằng OCR tiếng Việt; bản quá mờ có thể đọc sai dấu.</li>
        <li>
          Muốn đánh giá nội dung từng điều khoản cần bật AI trên máy chủ. Không có AI, các điểm kiểm
          tra sẽ là “chưa xác định”.
        </li>
      </ul>
    </Section>
  );
}
