"""Source-checked interpretation of optional Civil Code defaults, not legal approval.

Keep this revision additive: old reports keep their original snapshot. These two
criteria identify a delivery arrangement and a permitted ownership/risk arrangement.
They do not turn lawful agreed terms into prohibited clauses. Other mandatory-law
checks remain separate criteria and must not be suppressed by this revision.
"""

import hashlib
import json
from copy import deepcopy

from psycopg.types.json import Jsonb

from legal_checker.core.postgres import connect_postgres
from legal_checker.modules.legal_knowledge.repository import canonical

REVISION = "V750_CIVIL_DEFAULTS_20261109"
SOURCE_URL = "https://vbpl.vn/van-ban/chi-tiet/bo-luat-dan-su-so-91-2015-qh13--95942"
TARGETS = {
    "TC_PV_DS436_01": {
        "article": "ART_VB_DS_2015_436",
        "SATISFIED": (
            "Đã xác định phương thức giao tài sản theo thỏa thuận trong nguồn; khi đã kiểm "
            "đủ hồ sơ và không có thỏa thuận thì áp dụng giao một lần, trực tiếp theo Điều "
            "436 khoản 1. Điều khoản bàn giao/đo đạc/lập biên bản là nguồn về giao căn hộ; "
            "Fax/thư chỉ là cách thông báo. Không yêu cầu nhiều đợt giao hoặc biên bản đã ký "
            "khi chỉ rà nội dung dự thảo. Không kết luận đã thực hiện việc giao."
        ),
        "VIOLATED": (
            "Chỉ đánh giá vi phạm THỰC HIỆN phương thức giao khi có thỏa thuận hoặc quy tắc "
            "mặc định xác định được, chứng cứ thực hiện độc lập và sự không thực hiện đúng "
            "nghĩa vụ đó. Một lựa chọn phương thức được các bên thỏa thuận hợp pháp, hoặc "
            "việc hợp đồng không chép lại mặc định, không tự là vi phạm Điều 436 khoản 1. "
            "Vi phạm quy định bắt buộc khác phải đánh giá bằng đúng tiêu chí/căn cứ khác."
        ),
        "evidence": (
            "Điều khoản giao nhận căn hộ, người nhận, kiểm tra và biên bản; "
            "toàn bộ hồ sơ nếu áp dụng mặc định. Chứng cứ thực hiện chỉ cần khi "
            "kết luận về thực hiện."
        ),
    },
    "TC_PV_DS453_02": {
        "article": "ART_VB_DS_2015_453",
        "SATISFIED": (
            "Sau khi xác nhận giao dịch trả chậm/trả dần thuộc Điều 453, đã xác định thỏa "
            "thuận bảo lưu sở hữu và quyền sử dụng/phân bổ rủi ro, có xét thỏa thuận khác. "
            "Khoản 1 cho phép bảo lưu đến khi trả đủ, trừ thỏa thuận khác; khoản 2 cho bên "
            "mua sử dụng và chịu rủi ro trong thời gian sử dụng, trừ thỏa thuận khác. Quy tắc "
            "mặc định không bắt buộc được chép lại. Đọc cả điều khoản giao nhận/sử dụng và "
            "bảo lưu. Không đòi thêm điều khoản phạt/hủy/chấm dứt cho tiêu chí này."
        ),
        "VIOLATED": (
            "Chỉ kết luận vi phạm THỰC HIỆN sự phân bổ quyền/rủi ro khi xác định đúng thỏa "
            "thuận hợp pháp hoặc mặc định và có chứng cứ độc lập về hành vi trái nghĩa vụ. "
            "Không kết luận vi phạm từ riêng câu bên bán bảo lưu sở hữu đến khi trả đủ, "
            "từ thỏa thuận khác được Điều 453 cho phép, từ thiếu nhãn trả chậm/trả dần hoặc "
            "thiếu câu chép lại mặc định. Điều khoản trái quy định bắt buộc khác cần đúng "
            "tiêu chí/căn cứ đó, không gộp phạt 8%, hủy/chấm dứt vào tiêu chí này."
        ),
        "evidence": (
            "Điều kiện mua trả chậm/trả dần, điều khoản bảo lưu, quyền sử dụng/rủi ro "
            "sau giao nhận và thỏa thuận khác; nguồn về thực hiện nếu đánh giá thực hiện."
        ),
    },
}


def revised_content(base):
    """Return a new source-checked snapshot; never mutate the supplied baseline."""
    result = deepcopy(base)
    tables = result["tables"]
    criteria = {r["tieu_chi_id"]: r for r in tables["tieu_chi_danh_gia"]}
    articles = {r["dieu_khoan_id"]: r for r in tables["dieu_khoan_phap_ly"]}
    documents = {r["van_ban_id"]: r for r in tables["van_ban_phap_ly"]}
    for key, policy in TARGETS.items():
        criterion = criteria[key]
        article = articles[policy["article"]]
        if (
            criterion["source_dieu_khoan_id"] != policy["article"]
            or documents[article["van_ban_id"]]["so_hieu"] != "91/2015/QH13"
        ):
            raise ValueError("Civil-default revision requires the exact registered legal basis")
        criterion.update(
            bang_chung_can_thiet=policy["evidence"],
            human_verified=False,
            trang_thai="SOURCE_CHECKED",
            trang_thai_nguon="SOURCE_CHECKED",
        )
        for finding in ("SATISFIED", "VIOLATED"):
            rows = [
                r
                for r in tables["quy_tac_quyet_dinh"]
                if r["tieu_chi_id"] == key and r["finding"] == finding
            ]
            if len(rows) != 1:
                raise ValueError("Civil-default revision requires one decision per finding")
            row = rows[0]
            value = row["dieu_kien_json"]
            value = json.loads(value) if isinstance(value, str) else deepcopy(value)
            value.update(
                predicate=policy[finding],
                conclusion_scope_required=True,
                performance_requires_receipt_evidence=True,
                allowed_evaluation_targets=["PERFORMANCE"]
                if finding == "VIOLATED"
                else ["CONTRACT_CONTENT", "PERFORMANCE"],
            )
            row.update(
                dieu_kien_json=value,
                ly_do_chuan=policy[finding],
                rule_version=REVISION,
                human_verified=False,
                trang_thai="SOURCE_CHECKED",
            )
    result["parent_snapshot_sha256"] = hashlib.sha256(canonical(base).encode()).hexdigest()
    result["catalog_revision"] = REVISION
    result["revision_source_url"] = SOURCE_URL
    return result


def apply_revision(database_url, parent_sha256):
    """Insert immutable revised content; leave all existing pins and reports alone."""
    with connect_postgres(database_url) as conn:
        row = conn.execute(
            "SELECT content FROM knowledge.knowledge_snapshots WHERE sha256=%s", (parent_sha256,)
        ).fetchone()
        if (
            row is None
            or hashlib.sha256(canonical(row["content"]).encode()).hexdigest() != parent_sha256
        ):
            raise ValueError("Missing or invalid parent snapshot")
        content = revised_content(row["content"])
        sha = hashlib.sha256(canonical(content).encode()).hexdigest()
        conn.execute(
            "INSERT INTO knowledge.knowledge_snapshots "
            "(sha256,schema_version,content,review_status) "
            "VALUES (%s,%s,%s,%s) ON CONFLICT (sha256) DO NOTHING",
            (sha, content["schema_version"], Jsonb(content), "SOURCE_CHECKED"),
        )
    return {
        "revision": REVISION,
        "knowledge_snapshot_sha256": sha,
        "parent_snapshot_sha256": parent_sha256,
        "review_status": "SOURCE_CHECKED",
    }
