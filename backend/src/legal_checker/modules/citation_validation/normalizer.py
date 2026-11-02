"""Citation normalization for matching only; the raw citation text is never rewritten."""

import re
import unicodedata

_SPACES = re.compile(r"\s+")
_LEADING_TYPE = re.compile(r"^(bo luat|luat|nghi dinh|thong tu|quyet dinh)\s+", re.IGNORECASE)


def fold(text: str) -> str:
    """Lower-case, strip Vietnamese diacritics (đ→d) and collapse whitespace/line breaks."""
    decomposed = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    plain = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return _SPACES.sub(" ", plain).strip().lower()


def number_key(number: str | None) -> str | None:
    """'99/2015/NĐ-CP', '99/2015/ND-CP' and '99 / 2015 / nđ-cp' share one key."""
    if not number:
        return None
    return _SPACES.sub("", fold(number)).upper() or None


def number_year(number: str | None) -> int | None:
    match = re.search(r"/((?:19|20)\d{2})/", number or "")
    return int(match.group(1)) if match else None


def title_core(title: str | None) -> str | None:
    """'Luật Nhà ở' → 'nha o'; used to detect a number cited with another law's name."""
    if not title:
        return None
    return _LEADING_TYPE.sub("", fold(title)) or None
