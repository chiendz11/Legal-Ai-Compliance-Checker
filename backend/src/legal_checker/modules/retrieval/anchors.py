"""Explicit legal-document topic cues, never a conclusion or an absence proof."""

import re

from legal_checker.modules.retrieval.fact_evidence import fold


def anchored_chunks(query, chunks, limit=3):
    query = fold(query)
    rules = []
    if re.search(r"dia diem giao|phuong thuc giao|giao tai san", query):
        rules.append(r"^dieu\s*\d+[.:]?\s*(?:giao nhan|ban giao).*can ho")
    if "dieu kien giao dich chung" in query:
        rules.extend(
            (
                r"thoi diem ap dung dieu kien giao dich chung|phien ban dieu kien giao dich chung",
                r"ban noi quy nay co hieu luc|ban noi quy.*mot phan khong the tach roi",
                r"^dieu\s*\d+[.:]?\s*ngay hieu luc|cac phu luc.*hieu luc thi hanh",
            )
        )
    if re.search(r"(?:thoi gian|thoi han|tien do).*thanh toan", query):
        rules.append(r"thoi han (?:phai )?thanh toan|tien do thanh toan|lich bieu thanh toan")
    if re.search(r"tra cham|tra dan|lap thanh van ban", query):
        rules.extend(
            (r"hop dong mua ban can ho", r"thanh toan (?:lam )?nhieu dot|lich bieu thanh toan")
        )
    if re.search(r"bao luu.*so huu|phan bo rui ro", query):
        rules.append(r"quyen so huu.{0,220}(?:thanh toan|tra du|tra het)")
        rules.append(
            r"(?:ke tu|trong thoi gian).{0,180}(?:su dung|ban giao).{0,180}(?:trach nhiem|rui ro)"
        )
    if re.search(r"ho so.*(?:giao|nhan)|(?:giao|nhan).*ho so", query):
        rules.append(r"ho so can ho|kem theo hop dong nay.*ban ve|giay to.*ban giao")
    if re.search(r"sua chua mien phi|giam gia.*doi|doi vat|hoan tien", query):
        rules.append(r"\bdieu\s*\d+[.:]?\s*bao hanh|ben mua co quyen yeu cau.*sua chua")
    if re.search(r"quyen va nghia vu cua ben mua", query):
        rules.append(
            r"^dieu\s*\d+[.:]?\s*quyen(?: va)? nghia vu(?: cua)? ben mua|"
            r"^\d+\.\s*nghia vu cua ben mua"
        )
    found = []
    for pattern in rules:
        matches = [c.doan_id for c in chunks if re.search(pattern, fold(c.noi_dung))]
        for key in matches[:2]:
            if key not in found:
                found.append(key)
    return found[:limit]
