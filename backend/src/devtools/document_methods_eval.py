"""Compare source-preserving document methods on explicitly selected local PDFs.

No DB writes, provider calls, legal labels, TEST defaults, or changes to source PDFs.
The XLSX is an inspection workbook, not a seed/replacement for QA answer tables.
"""

import argparse
import csv
import hashlib
import importlib.util
import json
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import date
from pathlib import Path

from legal_checker.modules.documents.chunker import CHUNKER_VERSION, join_pages
from legal_checker.modules.documents.citation_spans import find_citation_spans
from legal_checker.modules.documents.profile_extractor import extract_profile
from legal_checker.modules.documents.service import PdfDocumentIntelligence
from legal_checker.shared.contracts.assessment import AssessmentCase


def _load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _audit(job):
    root, row, baseline, baseline_citations = job
    path = (Path(root) / row["pdf_path"]).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise ValueError("PDF path is outside the selected root")
    content = path.read_bytes()
    sha = hashlib.sha256(content).hexdigest()
    if sha != row["pdf_sha256"]:
        raise ValueError(f"Source checksum mismatch: {path.name}")

    class Storage:
        def read(self, source):
            return content

    case = AssessmentCase(
        ca_id="TRIAL_" + row["hop_dong_id"],
        hop_dong_id=row["hop_dong_id"],
        source=dict(
            tep_id="TRIAL_SOURCE", object_uri=path.as_uri(), mime_type="application/pdf", sha256=sha
        ),
        assessment_context=dict(
            ngay_danh_gia=date(2026, 11, 9), review_mode="DRAFT_REVIEW", document_set_complete=True
        ),
        deployment=dict(
            phien_ban_id="DOCUMENT_METHODS_TRIAL_V1",
            rule_version="NO_FINDINGS",
            legal_knowledge_version="NOT_USED_BY_EXTRACTION_AUDIT",
        ),
        tenant_id="LOCAL_EVAL",
        created_by="LOCAL_EVAL",
    )
    extraction = PdfDocumentIntelligence(Storage()).run(case)
    source, _, _ = join_pages(extraction.document)
    new = extraction.chunks
    old = []
    if baseline:
        old = _load_module(baseline, "trial_old_chunker").chunk_document(
            extraction.document, hop_dong_id=case.hop_dong_id, version="baseline"
        )
    spans = find_citation_spans(source)

    def metrics(chunks):
        ends = [c.global_end for c in chunks[:-1]]
        return dict(
            chunks=len(chunks),
            max_chars=max((len(c.noi_dung) for c in chunks), default=0),
            citation_boundary_cuts=sum(any(s["start"] < e < s["end"] for s in spans) for e in ends),
        )

    quotes_valid = all(
        next(c.noi_dung for c in new if c.doan_id == m.doan_id)[m.start : m.end] == m.quote
        for citation in extraction.citations
        for m in citation.mentions
    )
    covered = "".join(c.noi_dung for c in new)
    text_preserved = "".join(covered.split()) == "".join(source.split())
    if not text_preserved or not quotes_valid:
        raise ValueError(f"Source preservation failed: {path.name}")
    old_facts = (
        extract_profile(
            old,
            hop_dong_id=case.hop_dong_id,
            version="baseline",
            complete_draft_source=not extraction.unreadable_pages,
        )
        if old
        else None
    )

    def normalized(profile):
        return {
            f.ten_truong: f.gia_tri_chuan_json for f in profile.facts if f.trang_thai == "EXTRACTED"
        }

    changes = []
    if old_facts:
        a, b = normalized(old_facts), normalized(extraction.result.contract_profile)
        changes = [
            {"field": n, "before": a.get(n), "after": b.get(n)}
            for n in sorted(a.keys() | b.keys())
            if a.get(n) != b.get(n)
        ]
    old_refs = []
    if old and baseline_citations:
        old_refs = _load_module(baseline_citations, "trial_old_citations").extract_citations(
            old, version="baseline"
        )

    def citation_key(c):
        return (c.so_hieu, c.ten_van_ban, c.nam, c.dieu, c.khoan)

    return dict(
        contract_id=case.hop_dong_id,
        source_id=row["source_id"],
        group=row["group"],
        split=row.get("split", "UNASSIGNED"),
        pdf_path=str(path),
        sha256=sha,
        extraction_version=extraction.version,
        pages=len(extraction.document.pages),
        unreadable_pages=extraction.unreadable_pages,
        before=metrics(old) if old else None,
        after=metrics(new),
        source_preserved=text_preserved,
        citation_quotes_valid=quotes_valid,
        C03_count=len(extraction.citations),
        C02_fact_count=len(extraction.result.contract_profile.facts),
        fact_changes=changes,
        lost_citation_keys=[
            list(k)
            for k in set(map(citation_key, old_refs)) - set(map(citation_key, extraction.citations))
        ],
        chunks=[
            dict(
                doan_id=c.doan_id,
                hop_dong_id=c.hop_dong_id,
                section_path=c.section_path,
                page_start=c.page_start,
                page_end=c.page_end,
                noi_dung=c.noi_dung,
                sha256_text=c.sha256,
                thu_tu=c.thu_tu,
                phien_ban_chunk=extraction.version,
                global_start=c.global_start,
                global_end=c.global_end,
                split_reason=c.split_reason,
            )
            for c in new
        ],
        citations=[
            dict(
                vien_dan_id=c.vien_dan_id,
                raw_text=c.raw_text,
                so_hieu=c.so_hieu,
                ten_van_ban=c.ten_van_ban,
                status=c.status,
                positions=[
                    dict(doan_id=m.doan_id, start=m.start, end=m.end, quote=m.quote)
                    for m in c.mentions
                ],
            )
            for c in extraction.citations
        ],
    )


def _xlsx(path, results, summary):
    from openpyxl import Workbook
    from openpyxl.cell import WriteOnlyCell
    from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

    book = Workbook(write_only=True)

    def sheet(name, rows):
        s = book.create_sheet(name)
        for row in rows:
            cells = []
            for value in row:
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False)
                if isinstance(value, str):
                    # XML cannot store some source control characters. Escape only
                    # the viewing cell; exact source and offsets remain in JSON/PDF.
                    value = ILLEGAL_CHARACTERS_RE.sub(
                        lambda m: "\\u" + format(ord(m[0]), "04x"), value
                    )
                cell = WriteOnlyCell(s, value=value)
                if isinstance(value, str):
                    cell.data_type = "s"  # PDF text is data, including formula-like text.
                cells.append(cell)
            s.append(cells)

    sheet(
        "README",
        [
            ["Purpose", "Document-method comparison, NOT a seed workbook or legal gold"],
            ["PDF source", "Original files unchanged; source SHA-256 verified against manifest"],
            ["Policy", CHUNKER_VERSION],
            ["C07-C13", "Not generated; no compliance answer labels"],
            ["TEST", "Not loaded by default; split CSV is required"],
            [
                "Offsets",
                "Character offsets in parser-normalized text; chunk-local for citation positions",
            ],
            ["Size budget", "1800 target characters, bounded fallback; not model-token-aware"],
            [
                "XLSX display",
                "XML-illegal control characters escaped as \\uXXXX; JSON keeps exact text",
            ],
        ],
    )
    sheet("SUMMARY", [["metric", "value"], *summary.items()])
    fields = [
        "contract_id",
        "source_id",
        "split",
        "group",
        "pdf_path",
        "pages",
        "sha256",
        "extraction_version",
        "before",
        "after",
        "C03_count",
        "C02_fact_count",
        "fact_changes",
        "lost_citation_keys",
        "source_preserved",
        "citation_quotes_valid",
        "unreadable_pages",
    ]
    sheet("PDF_METRICS", [fields] + [[r[f] for f in fields] for r in results])
    headers = [
        "doan_id",
        "hop_dong_id",
        "section_path",
        "page_start",
        "page_end",
        "noi_dung",
        "sha256_text",
        "thu_tu",
        "phien_ban_chunk",
        "global_start",
        "global_end",
        "split_reason",
    ]
    sheet(
        "doan_hop_dong_trial",
        [headers] + [[c[f] for f in headers] for r in results for c in r["chunks"]],
    )
    sheet(
        "citation_positions_trial",
        [
            [
                "contract_id",
                "vien_dan_id",
                "raw_text",
                "number",
                "name",
                "status",
                "doan_id",
                "start",
                "end",
                "quote",
            ]
        ]
        + [
            [
                r["contract_id"],
                c["vien_dan_id"],
                c["raw_text"],
                c["so_hieu"],
                c["ten_van_ban"],
                c["status"],
                m["doan_id"],
                m["start"],
                m["end"],
                m["quote"],
            ]
            for r in results
            for c in r["citations"]
            for m in c["positions"]
        ],
    )
    book.save(path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf-root", type=Path, required=True)
    parser.add_argument(
        "--splits",
        type=Path,
        required=True,
        help="CSV with hop_dong_id and split; no labels needed",
    )
    parser.add_argument("--split", choices=["DEV", "VALIDATION"], action="append")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--baseline-chunker", type=Path)
    parser.add_argument("--baseline-citations", type=Path)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args(argv)
    if args.workers < 1:
        parser.error("workers must be positive")
    with args.splits.open(encoding="utf-8-sig", newline="") as handle:
        splits = {r["hop_dong_id"]: r["split"] for r in csv.DictReader(handle)}
    allowed = set(args.split or ["DEV"])
    with (args.pdf_root / "manifest.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = [
            {**r, "split": splits[r["hop_dong_id"]]}
            for r in csv.DictReader(handle)
            if splits.get(r["hop_dong_id"]) in allowed
        ]
    rows = rows[: args.limit] if args.limit else rows
    if not rows:
        parser.error("No selected DEV/VALIDATION documents")
    args.out.mkdir(parents=True, exist_ok=True)
    results, failures = [], []
    jobs = [
        (
            str(args.pdf_root),
            r,
            str(args.baseline_chunker.resolve()) if args.baseline_chunker else None,
            str(args.baseline_citations.resolve()) if args.baseline_citations else None,
        )
        for r in rows
    ]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        pending = {pool.submit(_audit, job): job[1]["hop_dong_id"] for job in jobs}
        for index, future in enumerate(as_completed(pending), 1):
            try:
                result = future.result()
                (args.out / (result["contract_id"] + ".json")).write_text(
                    json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
                )
                results.append(result)
            except Exception as exc:
                failures.append(dict(contract_id=pending[future], error=str(exc)))
            if index % 10 == 0 or index == len(jobs):
                print(f"Checked {index}/{len(jobs)}; failures={len(failures)}", flush=True)
    results.sort(key=lambda r: r["contract_id"])
    summary = dict(
        policy=CHUNKER_VERSION,
        selected=len(rows),
        passed=len(results),
        failures=failures,
        splits=dict(Counter(r["split"] for r in results)),
        provider_calls=0,
        database_writes=0,
        legal_gold=False,
        source_pdfs_modified=False,
        baseline_chunks=sum((r["before"] or {}).get("chunks", 0) for r in results),
        new_chunks=sum(r["after"]["chunks"] for r in results),
        baseline_citation_boundary_cuts=sum(
            (r["before"] or {}).get("citation_boundary_cuts", 0) for r in results
        ),
        new_citation_boundary_cuts=sum(r["after"]["citation_boundary_cuts"] for r in results),
        documents_with_fact_changes=sum(bool(r["fact_changes"]) for r in results),
        documents_with_changed_citation_keys=sum(bool(r["lost_citation_keys"]) for r in results),
    )
    (args.out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    _xlsx(args.out / "DOCUMENT_METHODS_TRIAL.xlsx", results, summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
