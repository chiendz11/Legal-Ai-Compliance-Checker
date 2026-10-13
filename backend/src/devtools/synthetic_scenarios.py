"""Authored counterfactual dossiers for the selected apartment requirement families.

This is a dataset reference adapter, not the production scope/temporal/LLM implementation.
Facts, source verification and document completeness refer to a declared test universe.
"""

import hashlib
import random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from legal_checker.shared.contracts.temporal import ApplicableRequirement

VERSION = "v7.5.0-synthetic-eval-r2"
DEPLOYMENT = "V750_SYNTHETIC_EVAL_R2"
URI_PREFIX = "dataset://v750-synthetic-r2/"
SCENARIOS = (
    "CLEAN_DOMESTIC",
    "CLEAN_FOREIGN_BOUNDARY",
    "FIRST_PAYMENT_EXCESS",
    "FOREIGN_PREHANDOVER_EXCESS",
    "PRE_CERTIFICATE_EXCESS",
    "DEPOSIT_BREACH",
    "MAINTENANCE_WARRANTY_BREACH",
    "MISSING_CONTACT_PARTIAL",
    "MISSING_PROPERTY",
    "ANNEX_NOT_RECEIVED",
    "CONFLICTING_PRICE",
    "MISSING_RELEVANT_DATES",
    "HISTORICAL_VALID",
    "TRANSITION_UNRESOLVED",
    "INDIVIDUAL_RESALE",
)
FAMILIES = (
    "FAM_PARTY_IDENTITY",
    "FAM_PROPERTY_INFO",
    "FAM_APT_COMMERCIAL_CONTENT",
    "FAM_APT_DEPOSIT",
    "FAM_FIRST_PAYMENT_CAP",
    "FAM_PRE_HANDOVER_CAP",
    "FAM_PRE_CERT_CAP",
    "FAM_MAINTENANCE_2_PERCENT",
    "FAM_WARRANTY_MIN_60",
)
FUTURE_FAMILIES = set(FAMILIES[3:7])
CONTENT_TOPICS = {
    "PARTIES": "parties",
    "PROPERTY": "property",
    "PRICE": "price",
    "METHOD": "method",
    "TERM": "term",
    "HANDOVER": "handover",
    "WARRANTY": "warranty",
    "RIGHTS": "rights",
    "LIABILITY": "liability",
    "PENALTY": "penalty",
    "TERMINATION": "termination",
    "DISPUTE": "dispute",
    "EFFECT": "effect",
}


@dataclass
class Scenario:
    case_id: str
    source_doc: str
    source_group: str
    split: str
    name: str
    index: int
    original_seed_date: date | None = None
    profile: dict = field(default_factory=dict)
    numeric: dict = field(default_factory=dict)
    sections: dict = field(default_factory=dict)
    markers: dict = field(default_factory=dict)
    missing: set = field(default_factory=set)
    uncertain: set = field(default_factory=set)
    conflicting: set = field(default_factory=set)
    citation_number: str | None = None
    citation_title: str | None = None
    expected_citation: str = "UNKNOWN"

    @property
    def document_id(self):
        return "SYN_" + self.source_doc

    @property
    def complete(self):
        return self.name != "ANNEX_NOT_RECEIVED"


def scenario_plan(seed, split):
    """Four DEV and one VALIDATION/TEST instance of every authored archetype.

    Existing document families stay in their original split. Different instances have
    different parties, sums, dates and clause order; shared archetypes are intentional.
    """
    profiles = {r["hop_dong_id"]: r for r in seed.tables["ho_so_hop_dong"]}
    docs = {r["hop_dong_id"]: r for r in seed.tables["hop_dong"]}
    cases = defaultdict(list)
    for row in seed.tables["ca_danh_gia"]:
        cases[split[row["ca_id"]]].append(row)
    if {key: len(value) for key, value in cases.items()} != {
        "DEV": 60,
        "VALIDATION": 15,
        "TEST": 15,
    }:
        raise ValueError("Synthetic release requires the 90-case 60/15/15 split")
    result = []
    for part, multiplier in (("DEV", 4), ("VALIDATION", 1), ("TEST", 1)):
        rows = sorted(cases[part], key=lambda r: r["ca_id"])
        random.Random("750-synthetic-r2-" + part).shuffle(rows)
        names = list(SCENARIOS) * multiplier
        for i, (row, name) in enumerate(zip(rows, names, strict=True)):
            doc = row["hop_dong_id"]
            scenario = Scenario(
                row["ca_id"],
                doc,
                docs[doc]["ho_mau_id"],
                part,
                name,
                int(row["ca_id"].split("_")[-1]),
                profiles[doc]["ngay_giao_ket"],
            )
            populate_scenario(scenario, i)
            result.append(scenario)
    return sorted(result, key=lambda s: s.case_id)


def populate_scenario(s, variant):
    """Write scenario facts first; outcomes are derived later from these facts."""
    historical = s.name == "HISTORICAL_VALID"
    resale = s.name == "INDIVIDUAL_RESALE"
    signing = date(2024, 3 if historical else 9, 1 + s.index % 20)
    if s.name == "TRANSITION_UNRESOLVED":
        signing = date(2024, 7, 15)
    absent_date = s.name == "MISSING_RELEVANT_DATES"
    collection = signing + timedelta(days=3)
    if s.name == "TRANSITION_UNRESOLVED":
        collection = date(2024, 8, 10)
    s.markers = {
        "SIGNING": None if absent_date else signing,
        "COLLECTION": None if absent_date else collection,
        "PRE_HANDOVER_COLLECTION": None if absent_date else collection + timedelta(days=20),
        "PRE_CERTIFICATE_COLLECTION": None if absent_date else collection + timedelta(days=50),
    }
    price = Decimal(1_500_000_000 + s.index * 25_000_000)
    foreign = s.name in ("CLEAN_FOREIGN_BOUNDARY", "FOREIGN_PREHANDOVER_EXCESS")
    first_ratio = Decimal("0.30") if s.name == "CLEAN_FOREIGN_BOUNDARY" else Decimal("0.25")
    pre_ratio = Decimal("0.50") if foreign else Decimal("0.70")
    cert_ratio = Decimal("0.95")
    deposit_ratio = Decimal("0") if historical or resale else Decimal("0.05")
    maintenance_ratio, months = Decimal("0.02"), 60
    eligible = True
    if s.name == "FIRST_PAYMENT_EXCESS":
        first_ratio = Decimal("0.31") + Decimal(variant % 3) / 100
    if s.name == "FOREIGN_PREHANDOVER_EXCESS":
        pre_ratio = Decimal("0.51") + Decimal(variant % 4) / 100
    if s.name == "PRE_CERTIFICATE_EXCESS":
        cert_ratio = Decimal("0.96") + Decimal(variant % 4) / 100
    if s.name == "DEPOSIT_BREACH":
        deposit_ratio, eligible = Decimal("0.06"), False
    if s.name == "MAINTENANCE_WARRANTY_BREACH":
        maintenance_ratio, months = Decimal("0.03"), 36
    s.profile = {
        "loai_hop_dong_id": "MB_CAN_HO_CHUNG_CU",
        "doi_tuong": "NHA_O",
        "linh_vuc": "NHA_O",
        "he_phap_luat": "VIET_NAM",
        "muc_dich_giao_dich": "TIEU_DUNG_KHONG_THUONG_MAI",
        "ngay_giao_ket": None if absent_date else signing,
        "ngay_giao_ket_raw": "..../..../...." if absent_date else signing.isoformat(),
        "do_chinh_xac_ngay": "UNKNOWN" if absent_date else "DAY",
        "trang_thai_ngay": "UNKNOWN" if absent_date else "SYNTHETIC_ASSUMPTION",
        "loai_moc_ap_dung": "NGAY_GIAO_KET",
        "ngay_hieu_luc_hop_dong": None if absent_date else signing,
        "ngay_ban_giao_du_kien": collection + timedelta(days=40),
        "quan_he_chu_the": "CA_NHAN_VOI_CA_NHAN" if resale else "KINH_DOANH_VA_NGUOI_TIEU_DUNG",
        "ben_ban_co_von_nuoc_ngoai": foreign,
        "ben_ban_la_chu_dau_tu": not resale,
        "ben_ban_la_ca_nhan": resale,
        "ben_mua_la_ca_nhan": True,
        "gia_tri_hop_dong": price,
        "don_vi_tien": "VND",
        "tinh_trang_tai_san": "CO_SAN" if resale else "HINH_THANH_TRONG_TUONG_LAI",
        "la_nha_o_xa_hoi": False,
        "la_hop_dong_theo_mau": not resale,
        "la_nha_xay_moi": not resale,
        "che_do_giao_dich": "BAN_LAI_CA_NHAN" if resale else "KINH_DOANH_BDS",
        "muc_dich_su_dung_can_ho": "DE_O",
    }
    deposit = price * deposit_ratio
    # The first invoice excludes deposit; total first collection is first_ratio * price.
    s.numeric = {
        "contract_price": str(price),
        "sale_price": str(price),
        "first_payment": str(price * first_ratio - deposit),
        "deposit": str(deposit),
        "deposit_included_in_first_payment": False,
        "prehandover_cumulative": str(price * pre_ratio),
        "foreign_seller_art10_4": foreign,
        "foreign_invested_seller": foreign,
        "before_certificate_cumulative": str(price * cert_ratio),
        "maintenance_base_price": str(price),
        "apartment_value": str(price),
        "maintenance_amount": str(price * maintenance_ratio),
        "separate_from_sale_price": not historical,
        "included_in_sale_payment": historical,
        "warranty_months": str(months),
        "warranty_start": "COMPLETION_AND_ACCEPTANCE_INTO_USE",
        "eligible_before_collection": eligible,
        "sale_price_agreed": True,
    }
    if s.name == "MISSING_CONTACT_PARTIAL":
        s.missing.add("contact")
    if s.name == "MISSING_PROPERTY":
        s.missing.add("property")
    if s.name == "ANNEX_NOT_RECEIVED":
        s.uncertain.add("property")
        s.profile["muc_dich_giao_dich"] = None
        s.profile["muc_dich_su_dung_can_ho"] = None
    if s.name == "CONFLICTING_PRICE":
        s.conflicting.update(("price", "first", "pre", "cert", "deposit", "maintenance"))
        s.profile["gia_tri_hop_dong"] = None
    if s.name == "MISSING_RELEVANT_DATES":
        s.uncertain.add("effect")
    seller = f"Ông Trần Minh {s.index:03d}" if resale else f"Công ty Dự án Giả lập {s.index:03d}"
    buyer = f"Bà Nguyễn An {s.index:03d}"
    address = f"Số {s.index + 10}, đường Mẫu, thành phố Giả Định"
    signing_text = s.profile["ngay_giao_ket_raw"]
    price_text = f"Giá bán căn hộ là {price} VND; giá này không bao gồm kinh phí bảo trì."
    if historical:
        price_text = (
            f"Giá trị căn hộ làm căn cứ tính bảo trì là {price} VND; "
            "kinh phí bảo trì cộng vào tiền bán khi bàn giao."
        )
    s.sections = {
        "cover": (
            "HỒ SƠ KIỂM THỬ GIẢ LẬP — KHÔNG PHẢI GIAO DỊCH THỰC. "
            f"Hợp đồng số {s.index:03d}/2024. "
            "Các nhân vật, địa chỉ, chứng từ trong hồ sơ đều hư cấu."
        ),
        "scope": (
            "Giao dịch mua bán căn hộ chung cư thương mại tại Việt Nam, không phải nhà ở xã hội. "
            + (
                "Bên bán là cá nhân bán lại căn hộ đã có sẵn, không kinh doanh bất động sản, "
                "không phải chủ đầu tư; căn hộ xây dựng từ năm 2010, đã hết bảo hành. "
                "Hợp đồng được đàm phán riêng."
                if resale
                else "Bên bán là chủ đầu tư kinh doanh bất động sản; "
                "căn hộ hình thành trong tương lai, nhà chung cư mới nhiều chủ sở hữu. "
                "Bên mua là cá nhân mua để ở, không kinh doanh. Hợp đồng theo mẫu."
            )
            + (
                " Bên bán là tổ chức kinh tế có vốn đầu tư nước ngoài "
                "thuộc khoản 4 Điều 10 Luật 29/2023/QH15."
                if foreign
                else " Bên bán không có vốn đầu tư nước ngoài."
            )
        ),
        "names": f"Bên bán: {seller}. Bên mua: {buyer}.",
        "address": (
            f"Địa chỉ bên bán: {address}. Địa chỉ bên mua: số {s.index + 20}, "
            "đường Ví Dụ, thành phố Giả Định."
        ),
        "contact": (
            f"Điện thoại bên bán: 0900{s.index:06d}; bên mua: 0910{s.index:06d}. "
            f"Email: seller{s.index}@example.invalid và buyer{s.index}@example.invalid."
        ),
        "property": (
            f"Căn hộ A-{s.index:03d}, tầng {2 + s.index % 20}, tòa T{s.index % 5 + 1}, "
            "dự án Minh Họa tại thành phố Giả Định. "
            f"Diện tích thông thủy {60 + s.index % 40} m2; dùng để ở; số lượng một căn hộ."
        ),
        "price": price_text,
        "method": (
            "Thanh toán bằng chuyển khoản vào tài khoản của bên bán ghi trong hồ sơ; "
            "biên nhận xác định số hợp đồng và khoản thu."
        ),
        "term": (
            "Thanh toán theo các đợt nghiệm thu xây dựng; đợt đầu trong ba ngày từ ký; "
            "phần còn lại chỉ đến hạn khi người mua được cấp Giấy chứng nhận."
        ),
        "handover": (
            "Bàn giao căn hộ, hồ sơ kỹ thuật và biên bản nghiệm thu dự kiến ngày "
            f"{s.profile['ngay_ban_giao_du_kien']}; các bên lập biên bản khi giao nhận."
        ),
        "warranty": (
            f"Bên bán bảo hành căn hộ {months} tháng kể từ khi hoàn thành xây dựng "
            "và nghiệm thu đưa vào sử dụng; sửa chữa hư hỏng kết cấu "
            "và hệ thống thuộc phạm vi bảo hành."
        ),
        "rights": (
            "Bên bán giao đúng căn hộ và hồ sơ; bên mua thanh toán theo tiến độ. "
            "Các bên được yêu cầu thực hiện đúng cam kết và cung cấp thông tin liên quan."
        ),
        "liability": (
            "Bên vi phạm nghĩa vụ phải khắc phục và bồi thường thiệt hại thực tế có căn cứ, "
            "theo điều kiện trách nhiệm do pháp luật quy định."
        ),
        "penalty": (
            "Các bên không thỏa thuận phạt vi phạm; "
            "trách nhiệm bồi thường được xử lý riêng theo pháp luật dân sự."
        ),
        "termination": (
            "Chấm dứt theo thỏa thuận; hủy bỏ khi có vi phạm nghiêm trọng theo luật. "
            "Các bên hoàn trả những gì đã nhận và xử lý thiệt hại có căn cứ."
        ),
        "dispute": (
            "Tranh chấp được thương lượng; nếu không giải quyết được "
            "thì yêu cầu Tòa án có thẩm quyền. Không lựa chọn trọng tài."
        ),
        "effect": f"Hợp đồng được ký và có hiệu lực ngày {signing_text}.",
        "deposit": (
            f"Thỏa thuận đặt cọc ghi giá bán {price} VND; đã thu {deposit} VND vào ngày "
            f"{collection if not absent_date else '..../..../....'}. "
            "Hồ sơ điều kiện kinh doanh xác nhận căn hộ "
            f"{'đã' if eligible else 'chưa'} đủ điều kiện tại thời điểm thu cọc."
        ),
        "first": (
            f"Biên nhận đợt đầu ngày {s.markers['COLLECTION'] or '..../..../....'}: "
            f"thu {s.numeric['first_payment']} VND, chưa gồm tiền cọc {deposit} VND đã thu riêng; "
            "khoản cọc không được cộng lần thứ hai vào đợt sau."
        ),
        "pre": (
            f"Sổ thu và biên bản ngày {s.markers['PRE_HANDOVER_COLLECTION'] or '..../..../....'}: "
            "căn hộ chưa bàn giao; lũy kế tiền thu kể cả cọc là "
            f"{s.numeric['prehandover_cumulative']} VND."
        ),
        "cert": (
            f"Sổ thu ngày {s.markers['PRE_CERTIFICATE_COLLECTION'] or '..../..../....'}: "
            "người mua chưa được cấp Giấy chứng nhận; "
            f"lũy kế đã thu {s.numeric['before_certificate_cumulative']} VND. "
            "Giá trị còn lại chỉ đến hạn khi Giấy chứng nhận được cấp."
        ),
        "maintenance": (
            f"Kinh phí bảo trì phần sở hữu chung là {s.numeric['maintenance_amount']} VND "
            f"trên giá trị căn hộ {price} VND; khoản này "
            f"{'cộng vào tiền bán khi bàn giao' if historical else 'tách riêng khỏi giá bán'}."
        ),
        "inventory": (
            "Danh mục hồ sơ: hợp đồng và biên nhận/sổ thu giả lập nêu trên; "
            "không có thỏa thuận sửa đổi khác hoặc ngoại lệ được khai báo ngoài hồ sơ này."
        ),
    }
    s.sections["parties"] = s.sections["names"] + " " + s.sections["address"]
    del s.sections["names"], s.sections["address"]
    for topic in s.missing:
        s.sections.pop(topic, None)
    if "property" in s.uncertain:
        s.sections["scope"] = s.sections["scope"].replace(
            "Bên mua là cá nhân mua để ở, không kinh doanh.",
            "Bên mua là cá nhân; mục đích tiêu dùng hay kinh doanh chưa được xác định.",
        )
        s.sections["property"] = (
            "Thông tin căn hộ nằm tại Phụ lục 01 được dẫn chiếu; "
            "phụ lục chưa được cung cấp trong hồ sơ nhận để đánh giá."
        )
        s.sections["inventory"] = (
            "Hồ sơ đã nhận: hợp đồng, biên nhận/sổ thu. Phụ lục 01 mô tả căn hộ chưa được nhận; "
            "không được suy luận rằng nội dung căn hộ vắng trong toàn bộ giao dịch."
        )
    if s.conflicting:
        s.sections["price"] += (
            f" Phụ lục cùng ngày ghi giá bán {price + 100_000_000} VND; "
            "các bản không xác định văn bản ưu tiên."
        )
    if s.name == "TRANSITION_UNRESOLVED":
        s.sections["inventory"] += (
            " Hợp đồng ký trước 01/08/2024, các đợt thu sau ngày này; "
            "chưa có hồ sơ đủ để xác định cơ chế chuyển tiếp cho từng nghĩa vụ."
        )
    elif historical:
        s.sections["inventory"] += (
            " Kịch bản chốt đánh giá trước 01/07/2024; "
            "các nghĩa vụ và khoản thu được xét đều phát sinh trước 01/08/2024."
        )
    elif not resale:
        s.sections["inventory"] += (
            " Kịch bản dự án và hợp đồng mới sau 01/08/2024; "
            "không kế thừa giao dịch, thu tiền hoặc thỏa thuận trước mốc này."
        )
    if resale:
        for topic in ("deposit", "first", "pre", "cert", "maintenance", "warranty"):
            s.sections.pop(topic, None)
    # Citation cases are orthogonal to the compliance mutations.
    s.citation_number = None
    s.expected_citation = "UNKNOWN"
    mode = variant % 4
    if historical:
        mode = 0
    if absent_date:
        mode = 3
    if mode == 0:
        s.citation_number = (
            "91/2015/QH13"
            if resale
            else "66/2014/QH13"
            if signing < date(2024, 8, 1)
            else "29/2023/QH15"
        )
        s.citation_title = "Bộ luật Dân sự" if resale else "Luật Kinh doanh bất động sản"
        s.expected_citation = "VALID"
    elif mode == 1:
        s.citation_number, s.citation_title = "66/2014/QH13", "Luật Kinh doanh bất động sản"
        s.expected_citation = "VALID" if signing < date(2024, 8, 1) else "STALE"
    elif mode == 2:
        s.citation_number, s.citation_title = (
            "29/2023/QH15",
            "Luật Bảo vệ quyền lợi người tiêu dùng",
        )
        s.expected_citation = "INVALID"
    else:
        s.citation_title = "Luật Kinh doanh bất động sản (không ghi số hiệu)"
    s.sections["citation"] = (
        "Căn cứ được ghi trong hợp đồng: "
        + s.citation_title
        + (" số " + s.citation_number if s.citation_number else "")
        + "."
    )


def reference_scope(s, family):
    p = s.profile
    if p["che_do_giao_dich"] == "BAN_LAI_CA_NHAN":
        return (
            "NO_MATCH",
            "Selected developer/consumer-template rule does not govern private resale",
        )
    if family in ("FAM_PARTY_IDENTITY", "FAM_PROPERTY_INFO"):
        purpose = p["muc_dich_giao_dich"]
        if purpose is None or p["la_hop_dong_theo_mau"] is None:
            return "UNKNOWN", "Consumer purpose/template scope facts have not been supplied"
        if purpose != "TIEU_DUNG_KHONG_THUONG_MAI" or not p["la_hop_dong_theo_mau"]:
            return "NO_MATCH", "Selected consumer-template family does not match"
    if family in FUTURE_FAMILIES:
        match = (
            p["che_do_giao_dich"] == "KINH_DOANH_BDS"
            and p["tinh_trang_tai_san"] == "HINH_THANH_TRONG_TUONG_LAI"
            and p["la_nha_o_xa_hoi"] is False
            and p["ben_ban_la_chu_dau_tu"] is True
        )
    else:
        match = p["loai_hop_dong_id"] == "MB_CAN_HO_CHUNG_CU"
    return ("MATCH" if match else "NO_MATCH"), "Declared synthetic subtype and subject facts"


def reference_requirements(s, knowledge):
    """Resolve only the declared nine families, using half-open knowledge date intervals.

    No arbitrary CANDIDATE -> CONFIRMED conversion and no universal signing-date rule.
    Collection obligations use collection events; content uses signing. Transitions stay unknown.
    """
    result = []
    for family in FAMILIES:
        scope, why = reference_scope(s, family)
        marker = {
            "FAM_APT_DEPOSIT": "COLLECTION",
            "FAM_FIRST_PAYMENT_CAP": "COLLECTION",
            "FAM_PRE_HANDOVER_CAP": "PRE_HANDOVER_COLLECTION",
            "FAM_PRE_CERT_CAP": "PRE_CERTIFICATE_COLLECTION",
        }.get(family, "SIGNING")
        relevant = s.markers[marker]
        candidates = [v for v in knowledge.versions.values() if v["requirement_id"] == family]
        active = [
            v
            for v in candidates
            if relevant is not None
            and date.fromisoformat(v["hieu_luc_tu"]) <= relevant
            and (not v["hieu_luc_den"] or relevant < date.fromisoformat(v["hieu_luc_den"]))
        ]
        # For identity's overlapping old versions, choose the declared consumer contract source.
        if len(active) > 1 and family == "FAM_PARTY_IDENTITY":
            active = [v for v in active if v["requirement_version_id"] == "PV_HYC018"]
        transitional = s.name == "TRANSITION_UNRESOLVED" and family not in FAMILIES[:2]
        if scope == "NO_MATCH":
            status, version_status = "NOT_APPLICABLE", "UNKNOWN"
            chosen = None
        elif scope == "UNKNOWN":
            status = "UNKNOWN"
            version_status = "RESOLVED" if len(active) == 1 else "UNKNOWN"
            chosen = active[0] if len(active) == 1 else None
        elif (
            relevant and not active and family in ("FAM_APT_COMMERCIAL_CONTENT", "FAM_APT_DEPOSIT")
        ):
            # These are explicitly 2024-only supplemental rules, not an assertion that old law
            # had no commercial contract/deposit requirements.
            status, version_status, chosen = "NOT_APPLICABLE", "UNKNOWN", None
            why = (
                "Selected 2024-only supplemental rule not in force; historical checklist is partial"
            )
        elif len(active) == 1 and not transitional:
            status, version_status, chosen = "CONFIRMED", "RESOLVED", active[0]
        else:
            status, version_status = "UNKNOWN", "UNKNOWN"
            chosen = (
                active[0] if len(active) == 1 else max(candidates, key=lambda v: v["hieu_luc_tu"])
            )
            why = (
                "Transition context unresolved"
                if transitional
                else "Relevant event date missing or version ambiguous"
            )
        result.append(
            ApplicableRequirement(
                yeu_cau_ca_id=s.case_id + "_" + family,
                ca_id=s.case_id,
                requirement_id=family,
                requirement_version_id=chosen["requirement_version_id"] if chosen else None,
                nhom_phien_ban=chosen["nhom_phien_ban"] if chosen else None,
                scope_status=scope,
                version_status=version_status,
                applicability_status=status,
                moc_id=s.case_id + "_" + marker,
                loai_moc=marker,
                moc_ap_dung=relevant,
                resolution_method="SYNTHETIC_SELECTED_FAMILY_REFERENCE_R2",
                profile_snapshot_json={
                    "synthetic": True,
                    "facts_are_scenario_assumptions": True,
                    "profile": {
                        k: str(v) if isinstance(v, (date, Decimal)) else v
                        for k, v in s.profile.items()
                    },
                },
                dieu_kien_snapshot_json={
                    "reference_scope_reason": why,
                    "transition_context_resolved": not transitional,
                    "selected_family_only": True,
                },
                nguon_snapshot_json={
                    "original_case_id": s.case_id,
                    "original_doc_id": s.source_doc,
                    "knowledge_sha256": knowledge.sha256,
                    "real_world_verified": False,
                },
                phien_ban_id=DEPLOYMENT,
                reason={"summary": why, "mode": "SYNTHETIC_EVALUATION"},
            )
        )
    return result


def criterion_topic(c):
    cid, family = c["tieu_chi_id"], c["requirement_version_id"]
    if family == "PV_APT_COMMERCIAL_CONTENT_2024":
        return CONTENT_TOPICS[cid.rsplit("_", 1)[-1]]
    if family in ("PV_GYC005", "PV_HYC018", "PV_HYC039"):
        return "contact" if cid.endswith("03") else "parties"
    if family in ("PV_GYC006", "PV_HYC019"):
        return "property"
    if family == "PV_APT_DEPOSIT_2024":
        return "deposit"
    for token, topic in (
        ("062", "first"),
        ("034", "first"),
        ("064", "pre"),
        ("036", "pre"),
        ("065", "cert"),
        ("037", "cert"),
        ("104", "maintenance"),
        ("049", "maintenance"),
        ("154", "warranty"),
        ("053", "warranty"),
    ):
        if family.endswith(token):
            return topic
    raise ValueError("No authored clause for criterion " + cid)


def authored_finding(s, requirement, criterion):
    """Independent expected labels from scenario facts, not copied from engine output."""
    topic = criterion_topic(criterion)
    if not requirement.confirmed or topic in s.uncertain or topic in s.conflicting:
        return "UNKNOWN"
    if topic in s.missing:
        return "MISSING" if criterion["noi_dung_bat_buoc_trong_hd"] and s.complete else "UNKNOWN"
    n, price = s.numeric, Decimal(s.numeric["contract_price"])
    if topic == "first":
        return (
            "VIOLATED"
            if Decimal(n["first_payment"]) + Decimal(n["deposit"]) > price * Decimal("0.30")
            else "SATISFIED"
        )
    if topic == "pre":
        limit = Decimal("0.50") if n["foreign_seller_art10_4"] else Decimal("0.70")
        return "VIOLATED" if Decimal(n["prehandover_cumulative"]) > price * limit else "SATISFIED"
    if topic == "cert":
        return (
            "VIOLATED"
            if Decimal(n["before_certificate_cumulative"]) > price * Decimal("0.95")
            else "SATISFIED"
        )
    if topic == "maintenance":
        return (
            "VIOLATED"
            if Decimal(n["maintenance_amount"]) != price * Decimal("0.02")
            else "SATISFIED"
        )
    if topic == "warranty":
        if criterion["tieu_chi_id"] == "TC_PV_HYC053_02":
            return "SATISFIED"
        return "VIOLATED" if int(n["warranty_months"]) < 60 else "SATISFIED"
    if topic == "deposit":
        cid = criterion["tieu_chi_id"]
        passed = (
            n["sale_price_agreed"]
            if cid.endswith("PRICE")
            else n["eligible_before_collection"]
            if cid.endswith("ELIGIBLE")
            else Decimal(n["deposit"]) <= price * Decimal("0.05")
        )
        return "SATISFIED" if passed else "VIOLATED"
    return "SATISFIED"


def authored_aggregate(requirement, criteria, findings):
    if requirement.applicability_status == "NOT_APPLICABLE":
        return None
    labels = [findings[c["tieu_chi_id"]] for c in criteria if c["bat_buoc"]]
    if not requirement.confirmed or not labels:
        return "INSUFFICIENT"
    if "VIOLATED" in labels or all(label == "MISSING" for label in labels):
        return "NON_COMPLIANT"
    if "UNKNOWN" in labels:
        return "INSUFFICIENT"
    return "PARTIAL" if "MISSING" in labels else "COMPLIANT"


def source_sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
