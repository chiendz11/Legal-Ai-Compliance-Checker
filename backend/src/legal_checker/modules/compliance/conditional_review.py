"""Finite conditions for supplied-draft review; no assertions about actual performance."""

POLICY = "DRAFT_LOCAL_CONDITIONS_V1"

TRIAL = (
    "Có thỏa thuận cho bên mua sử dụng thử tài sản trước khi quyết định mua hoặc không mua. "
    "Kiểm tra căn hộ trước bàn giao, bảo hành hoặc quyền từ chối nhận căn hộ không phải dùng thử."
)
CREDIT = (
    "Có thỏa thuận cấp thời hạn trả chậm/trả dần tiền mua sau khi đã nhận tài sản theo Điều 453. "
    "Tiến độ ứng tiền xây dựng nhà ở tương lai, hoặc giữ lại khoản thanh toán chờ giấy chứng nhận "
    "theo pháp luật chuyên ngành, tự nó không chứng minh có thỏa thuận mua chịu này."
)

CONDITIONS = {
    "TC_PV_DS418_01": ("Có thỏa thuận phạt vi phạm hợp đồng giữa các bên.", True),
    "TC_PV_DS418_02": ("Có thỏa thuận phạt vi phạm hợp đồng giữa các bên.", True),
    "TC_PV_DS435_02": (
        "Có thỏa thuận xác định địa điểm giao tài sản, trực tiếp hoặc bằng dẫn chiếu rõ ràng. "
        "Chỉ hứa thông báo địa điểm sau này chưa phải địa điểm đã thỏa thuận.",
        False,
    ),
    "TC_PV_DS442_02": (
        "Có thỏa thuận rõ về chi phí vận chuyển và chi phí liên quan chuyển quyền sở hữu. "
        "Điều khoản thuế/phí/lệ phí đăng ký sở hữu có thể là thỏa thuận liên quan. "
        "Không nhầm Điều 442 về chi phí với điều kiện chất lượng tài sản.",
        False,
    ),
    "TC_PV_DS452_01": (TRIAL, True),
    "TC_PV_DS452_02": (TRIAL, True),
    "TC_PV_DS453_01": (CREDIT, True),
    "TC_PV_DS453_02": (CREDIT, True),
}


def condition_spec(criterion_id):
    row = CONDITIONS.get(criterion_id)
    if row is None:
        return None
    return {"policy_id": POLICY, "question": row[0], "applies_when_present": row[1]}


def condition_result(criterion_id, assessment):
    spec = condition_spec(criterion_id)
    if spec is None or assessment not in {"PRESENT", "ABSENT"}:
        return "UNKNOWN", None
    applies = (assessment == "PRESENT") is spec["applies_when_present"]
    reason = (
        f"{POLICY}: toàn bộ hồ sơ dự thảo cho kết quả {assessment} đối với điều kiện: "
        + spec["question"]
    )
    return ("MATCH", None) if applies else ("NO_MATCH", reason)


def interpretation_notes(criterion_id):
    return {
        "TC_PV_DS453_01": (
            "Điều 453 là chế độ có điều kiện. Kiểm thỏa thuận cấp thời hạn trả chậm/trả dần "
            "sau nhận tài sản, không đồng nhất nhiều đợt ứng tiền hoặc giữ lại tiền chờ giấy "
            "chứng nhận với mua chịu. Khi điều kiện không phát sinh thì loại có căn cứ. Khi "
            "điều kiện phát sinh, khoản 2 yêu cầu hợp đồng bằng văn bản; chính PDF hợp đồng "
            "đang rà là văn bản để đánh giá nội dung dự thảo. Không bắt văn bản phải có đúng "
            "cụm từ 'mua trả chậm' hoặc đòi hợp đồng/phụ lục riêng nếu thỏa thuận đã thể hiện. "
            "Chưa ký trong DRAFT_REVIEW không tự là vi phạm nội dung; không xác nhận đã ký."
        ),
        "TC_PV_DS453_02": (
            "Điều 453 khoản 1 CHO PHÉP bên bán bảo lưu quyền sở hữu đến khi bên mua trả đủ "
            "tiền, trừ thỏa thuận khác. Khoản 2 cho bên mua sử dụng và chịu rủi ro trong thời "
            "gian sử dụng, trừ thỏa thuận khác. Phải đọc cả điều khoản bàn giao/sử dụng và "
            "điều khoản bảo lưu, không chỉ một câu. Sự có mặt của bảo lưu sở hữu không phải "
            "vi phạm; sự thiếu một câu chép lại luật hoặc thiếu nhãn 'trả chậm/trả dần' cũng "
            "không chứng minh vi phạm. Xét đúng điều kiện phát sinh và nội dung thỏa thuận "
            "khác; luật mặc định được áp dụng khi không có thỏa thuận khác, không bắt hợp "
            "đồng nhắc lại quy tắc mặc định. VIOLATED phải chỉ ra mệnh đề trái quy định bắt "
            "buộc bằng nguồn cụ thể; không suy ra từ việc một thỏa thuận được pháp luật cho "
            "phép có mặt. Không đánh giá sự kiện thực hiện hoặc tự áp trần phạt thương mại."
        ),
        "TC_PV_DS435_02": (
            "Đây là nhánh mặc định KHI KHÔNG CÓ thỏa thuận địa điểm giao; không được lấy chính "
            "việc thiếu thỏa thuận làm lý do UNKNOWN hoặc vi phạm. Khi local_applicability là "
            "MATCH và condition_review_assessment=ABSENT, backend đã kiểm điều kiện này qua "
            "toàn bộ nguồn. Đối chiếu Điều 277 khoản 2 trong related_legal_articles: nghĩa vụ "
            "có đối tượng bất động sản được thực hiện tại nơi có bất động sản. Không bắt dự "
            "thảo chép lại quy tắc mặc định nếu luật đã bổ sung; không xác nhận đã bàn giao. "
            "Nếu còn thiếu loại tài sản hoặc có xung đột thì vẫn nêu rõ dữ kiện thiếu."
        ),
        "TC_PV_DS436_01": (
            "Trích dẫn về phương thức phải thể hiện cách thực hiện giao/nhận, chủ thể nhận "
            "hoặc thủ tục kiểm tra/lập biên bản; không lấy riêng ngày hoặc địa điểm bàn giao "
            "làm bằng chứng về phương thức. "
            "Giao tài sản nhiều đợt là một phương án thỏa thuận, không phải yêu cầu bắt buộc "
            "mọi hợp đồng phải có nhiều đợt. Áp dụng Điều 436 được cấp: nếu không thỏa thuận "
            "phương thức thì giao một lần và trực tiếp cho bên mua. Kiểm điều khoản bàn giao "
            "căn hộ/biên bản bàn giao trong C06; phân biệt với nhiều đợt THANH TOÁN. Chỉ đánh "
            "giá nội dung dự thảo, không đòi biên bản thực hiện đã ký. Thiếu thỏa thuận mà "
            "luật cho phép dùng mặc định không tự là MISSING/UNKNOWN. Không giả định cơ chế "
            "mặc định nếu nguồn có thỏa thuận khác chưa được làm rõ."
        ),
        "TC_PV_HYC015_02": (
            "Không đồng nhất ngày C01 với thời điểm áp dụng điều kiện giao dịch chung. "
            "Đối chiếu cả các quy tắc/nội quy đính kèm, điều khoản đưa chúng vào hợp đồng "
            "và điều khoản hiệu lực của chính văn bản đó, theo định nghĩa pháp luật được cấp. "
            "Không đòi tài liệu phải mang đúng nhãn 'điều kiện giao dịch chung', nhưng không tự "
            "coi mọi phụ lục hoặc hợp đồng dịch vụ riêng là điều kiện bán hàng. Nếu văn bản "
            "được xác định đúng và ghi rõ sự kiện bắt đầu áp dụng, DRAFT_REVIEW kiểm cách xác "
            "định mốc này; không đòi ngày/sự kiện ký ban hành đã thực sự xảy ra. Việc công khai "
            "hoặc niêm yết thực tế là tiêu chí khác, không tự xác nhận từ bản dự thảo."
        ),
        "TC_PV_HYC011_01": (
            "Điều cấm đòi đúng tình huống bên bán không hoàn thành nghĩa vụ mà bên mua vẫn bị buộc "
            "thực hiện. Trả tiền đến hạn không phụ thuộc THÔNG BÁO thanh toán, hoặc nghĩa vụ bình "
            "thường của bên mua, tự nó không phải tình huống bên bán vi phạm."
        ),
        "TC_PV_HYC012_01": (
            "Phân biệt chủ thể và hợp đồng: kiểm tra bên BÁN chuyển quyền/nghĩa vụ của hợp đồng "
            "mua bán này cho người thứ ba không được bên mua đồng ý. Bên MUA chuyển nhượng, "
            "giao quỹ bảo trì cho Ban quản trị hoặc chuyển hợp đồng DỊCH VỤ quản lý "
            "là quan hệ khác."
        ),
        "TC_PV_DS444_02": (
            "DRAFT_REVIEW kiểm tra phân bổ trách nhiệm trong điều khoản: bảo vệ quyền bên mua, "
            "ngoại lệ khi bên mua biết quyền của người thứ ba. Không xác nhận quyền sở hữu thực tế "
            "hoặc trạng thái nhận thức đã xảy ra; không bắt dự thảo chứng minh sự kiện tương lai."
        ),
        "TC_PV_DS446_02": (
            "Kiểm cả thân hợp đồng và phụ lục về thời hạn/mốc bảo hành. Với nhà ở thuộc luật "
            "chuyên ngành được cung cấp trong related_legal_articles, đối chiếu mốc nghiệm thu "
            "đưa vào sử dụng của luật đó; không mặc định buộc dự thảo dùng ngày nhận vật của "
            "quy tắc chung. Sự có mặt của cách tính mốc không chứng minh đã nghiệm thu thực tế."
        ),
    }.get(criterion_id)
