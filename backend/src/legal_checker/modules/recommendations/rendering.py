"""Bind explicit legacy draft slots from observed values, never from guessed facts."""

import re

SLOTS = {
    "nguyên văn": "quote",
    "thông tin/bằng chứng cụ thể còn thiếu": "verification_request",
}


def verification_request(source):
    if source.get("reason_code") == "NAME_ONLY_VERSION_IDENTITY_AMBIGUOUS":
        return (
            "năm ban hành hoặc số hiệu, cùng bản nguồn hoặc dẫn chiếu đủ để "
            "định danh phiên bản luật"
        )
    reason = source.get("uncertainty_reason") or source.get("ly_do")
    return "chứng từ nguồn và thông tin làm rõ vấn đề: " + reason if reason else None


def observed_quote(source):
    quotes = [e.get("trich_dan") for e in source.get("evidence", [])]
    text = "\n".join(q for q in quotes if isinstance(q, str) and q.strip())
    occurrence = source.get("source_snapshot_json", {}).get("source_occurrence", {})
    # This is an observed title, not a normalized/resolved document identity.
    return text or occurrence.get("observed_title") or ""


def bind_draft_slots(text, values):
    missing = []

    def bind(match):
        name = match[1].strip()
        field = SLOTS.get(name)
        if field:
            value = values.get(field)
            if field == "verification_request" and not value:
                value = verification_request(values)
            if isinstance(value, str) and value.strip():
                return value
            missing.append(field)
        elif not (
            name.casefold().startswith(("dự thảo", "điều ", "khoản ", "điểm "))
            or re.fullmatch(r"[\d\s.,%/-]+", name)
        ):
            missing.append(name)
        return match[0]

    result = re.sub(r"\[([^\[\]\n]+)\]", bind, text)
    return result, sorted(set(missing))
