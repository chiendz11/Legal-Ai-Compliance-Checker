"""C03 source-first extraction of contract-authored legal citations.

- EXTRACTED: có số hiệu văn bản pháp luật (vd 91/2015/QH13) hoặc (Bộ) luật kèm năm.
- AMBIGUOUS: chỉ có tên văn bản, không số hiệu/năm (vd "theo Luật Nhà ở").
- Không kiểm tra hiệu lực (việc của bước 3B): "Nghị định 999/2099/NĐ-CP" vẫn được trích.
- Cùng một văn bản + điều/khoản nêu nhiều lần → 1 citation với nhiều vị trí.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from itertools import groupby, pairwise
from typing import TYPE_CHECKING

from legal_checker.modules.documents.citation_spans import find_citation_spans

if TYPE_CHECKING:
    from legal_checker.modules.documents.chunker import ChunkRecord
    from legal_checker.modules.documents.parser import DocumentText
from legal_checker.shared.contracts.citation import (
    CitationExtraction,
    CitationExtractionMetadata,
    CitationNormalization,
    CitationPosition,
)

EXTRACTOR_VERSION = "source-spans-v5"


@dataclass(frozen=True)
class CitationMention:
    """Một lần xuất hiện: quote + offset trong chunk, dùng cho bang_chung_vien_dan."""

    doan_id: str
    page_start: int
    page_end: int
    start: int
    end: int
    quote: str


@dataclass
class CitationRecord:
    vien_dan_id: str
    hop_dong_id: str
    raw_text: str
    status: str
    so_hieu: str | None = None
    loai_van_ban: str | None = None
    ten_van_ban: str | None = None
    nam: int | None = None
    dieu: str | None = None
    khoan: str | None = None
    diem: str | None = None
    mentions: list[CitationMention] = field(default_factory=list)
    provenance: dict[str, str] = field(default_factory=dict)

    def to_contract(self) -> CitationExtraction:
        positions, seen = [], set()
        for m in self.mentions:
            key = (m.doan_id, m.page_start, m.page_end)
            if key not in seen:
                seen.add(key)
                positions.append(
                    CitationPosition(
                        doan_id=m.doan_id, page_start=m.page_start, page_end=m.page_end
                    )
                )
        return CitationExtraction(
            vien_dan_id=self.vien_dan_id,
            hop_dong_id=self.hop_dong_id,
            raw_text=self.raw_text,
            normalized=CitationNormalization(
                so_hieu=self.so_hieu,
                ten_van_ban=self.ten_van_ban,
                loai_van_ban=self.loai_van_ban,
                nam=self.nam,
                dieu=self.dieu,
                khoan=self.khoan,
            ),
            extraction=CitationExtractionMetadata(status=self.status),
            evidence=positions,
        )


def extract_citations(
    chunks: Iterable[ChunkRecord], *, version: str, document: DocumentText | None = None
) -> list[CitationRecord]:
    """Extract on source text once, then map occurrences to exact chunk intersections.

    If no document is provided (legacy callers), only contiguous supplied slices are
    joined. Never bridge an unread/omitted region or infer missing source characters.
    """
    chunks = sorted(chunks, key=lambda c: (c.global_start, c.thu_tu))
    if len({c.hop_dong_id for c in chunks}) > 1:
        raise ValueError("Citation sources belong to several contracts")
    if any(c.global_end - c.global_start != len(c.noi_dung) for c in chunks):
        raise ValueError("Chunk source offsets do not match its text")
    if any(a.global_end > b.global_start for a, b in pairwise(chunks)):
        raise ValueError("Overlapping citation source slices")
    if document is not None:
        from legal_checker.modules.documents.chunker import join_pages

        source, starts, _ = join_pages(document)
        if any(source[c.global_start : c.global_end] != c.noi_dung for c in chunks):
            raise ValueError("Chunk differs from the supplied document source")
    # Each run contains source-contiguous chunks; missing regions are never joined.
    numbered = []
    group = 0
    previous = None
    for chunk in chunks:
        if previous is not None and (
            previous.global_end != chunk.global_start or previous.thu_tu + 1 != chunk.thu_tu
        ):
            group += 1
        numbered.append((group, chunk))
        previous = chunk
    records: dict[tuple, CitationRecord] = {}
    regions = []
    if document is None:
        for _, pairs in groupby(numbered, key=lambda item: item[0]):
            run = [chunk for _, chunk in pairs]
            regions.append((run[0].global_start, "".join(c.noi_dung for c in run), run))
    else:
        # Unreadable pages are barriers, even though join_pages preserves their number.
        a = None
        for page, start in zip(
            sorted(document.pages, key=lambda p: p.page_number), starts, strict=True
        ):
            if page.readable:
                if a is None:
                    a = start
            elif a is not None:
                regions.append((a, source[a:start], chunks))
                a = None
        if a is not None:
            regions.append((a, source[a:], chunks))
    for origin, text, run in regions:
        if not run:
            continue
        for s in find_citation_spans(text):
            quote = text[s["start"] : s["end"]]
            start, end = origin + s["start"], origin + s["end"]
            mentions = [
                (
                    c,
                    max(start, c.global_start) - c.global_start,
                    min(end, c.global_end) - c.global_start,
                )
                for c in run
                if c.global_start < end and c.global_end > start
            ]
            if sum(b - a for _, a, b in mentions) != end - start:
                # The full source can expose spans outside the supplied extraction.
                # Do not publish a raw citation whose complete source cannot be located.
                continue
            doc_key = s["so_hieu"] or (s["ten"] or f"UNRESOLVED_TYPE:{s['loai']}").lower()
            dynamic = bool(re.search(r"hiện\s+hành|từng\s+thời\s+điểm", quote, re.I))
            key = (
                doc_key,
                s["nam"] if not s["so_hieu"] else None,
                s["dieu"],
                s["khoan"],
                s["diem"],
                dynamic,
            )
            record = records.get(key)
            if record is None:
                hop_dong_id = run[0].hop_dong_id
                record = CitationRecord(
                    vien_dan_id=f"{hop_dong_id}_VD_{version}_{len(records) + 1:03d}",
                    hop_dong_id=hop_dong_id,
                    raw_text=quote,
                    status=s["status"],
                    so_hieu=s["so_hieu"],
                    loai_van_ban=s["loai"],
                    ten_van_ban=s["ten"],
                    nam=s["nam"],
                    dieu=s["dieu"],
                    khoan=s["khoan"],
                    diem=s["diem"],
                    provenance={"method": EXTRACTOR_VERSION, "rule": s["rule"]},
                )
                records[key] = record
            for source, start, end in mentions:
                record.mentions.append(
                    CitationMention(
                        source.doan_id,
                        source.page_start,
                        source.page_end,
                        start,
                        end,
                        source.noi_dung[start:end],
                    )
                )
    return list(records.values())
