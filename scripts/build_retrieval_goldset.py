"""Build a candidate pool for an independent retrieval relevance set (DEV only).

For a stratified sample of (case, criterion) targets, the pool is the union of the top-5
of several retrieval variants plus the reference selections, so no variant is favoured.
Annotators label every pooled chunk 2 (answers the criterion), 1 (partial/context), 0.
Run from repository root:  python -m scripts.build_retrieval_goldset --per-criterion 2
"""

import argparse
import json
import os
import random
import re
from collections import defaultdict
from pathlib import Path

from devtools.upstream_fixtures import list_cases, load_artifact, load_context, load_document
from dotenv import load_dotenv
from legal_checker.core.postgres import connect_postgres
from legal_checker.modules.legal_knowledge.repository import Knowledge
from legal_checker.modules.retrieval.repository import RetrievalDatasetRepository
from legal_checker.modules.retrieval.service import LexicalRetrievalService
from legal_checker.shared.contracts.temporal import ApplicableRequirement

ROOT = Path(__file__).resolve().parents[1]
BOILERPLATE = re.compile(
    r"(?i)\b(hợp đồng|phải|có|thông tin|quy định|được|không|các|của|về|trong|theo|với|cho"
    r"|bên|tối thiểu|nếu có|xác định)\b"
)


def short_query(text: str) -> str:
    return re.sub(r"\s+", " ", BOILERPLATE.sub(" ", re.sub(r"[()/,.;:]", " ", text))).strip()


def variants(repository: RetrievalDatasetRepository) -> dict:
    paths, facts = repository.section_paths, repository.fact_evidence
    return {
        "bm25": LexicalRetrievalService(),
        "bm25_path": LexicalRetrievalService(section_paths=paths),
        "bm25_path_fact": LexicalRetrievalService(section_paths=paths, fact_evidence=facts),
    }


def main() -> None:
    load_dotenv(ROOT / ".env", override=False)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--per-criterion", type=int, default=2)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "data/private/eval/goldset_pool_DEV.json"
    )
    args = parser.parse_args()
    db = args.database_url
    knowledge, repository = Knowledge(db), RetrievalDatasetRepository(db)
    with connect_postgres(db) as connection:
        template = {
            r["hop_dong_id"]: r["ho_mau_id"]
            for r in connection.execute("SELECT hop_dong_id, ho_mau_id FROM runtime.hop_dong")
        }
    # Every (case, criterion) the reference C05 makes searchable, grouped by criterion.
    targets = defaultdict(list)
    for ca_id in list_cases(db, "DEV"):
        for row in load_artifact(db, ca_id, "EXPECTED", "C05"):
            if row["applicability_status"] != "NOT_APPLICABLE" and row["requirement_version_id"]:
                for criterion in knowledge.criteria_for(row["requirement_version_id"]):
                    targets[criterion["tieu_chi_id"]].append((ca_id, row["yeu_cau_ca_id"]))
    rng = random.Random(args.seed)
    sample = []
    for tieu_chi_id in sorted(targets):
        # Prefer different contract templates for the same criterion.
        seen, picks = set(), []
        for ca_id, yeu_cau_ca_id in rng.sample(targets[tieu_chi_id], len(targets[tieu_chi_id])):
            hop_dong_id = ca_id.replace("CA360", "HD360")
            if template.get(hop_dong_id) not in seen:
                seen.add(template.get(hop_dong_id))
                picks.append((ca_id, yeu_cau_ca_id))
            if len(picks) == args.per_criterion:
                break
        sample += [(tieu_chi_id, *pick) for pick in picks]

    services = variants(repository)
    by_case = defaultdict(list)
    for tieu_chi_id, ca_id, yeu_cau_ca_id in sample:
        by_case[ca_id].append((tieu_chi_id, yeu_cau_ca_id))
    pool = []
    for ca_id, wanted in sorted(by_case.items()):
        document = load_document(db, ca_id)
        text = {c.doan_id: c.noi_dung for c in document.chunks}
        paths = repository.section_paths(document.chunks[0].hop_dong_id)
        context = load_context(db, ca_id, f"{ca_id}_B_GOLD")
        requirements = [
            ApplicableRequirement.model_validate(r)
            for r in load_artifact(db, ca_id, "EXPECTED", "C05")
        ]
        rankings = {}
        for name, service in services.items():
            rows = service.retrieve(context, requirements, document.chunks, knowledge)
            ranked = defaultdict(list)
            for row in sorted(rows, key=lambda r: r.thu_hang):
                ranked[(row.yeu_cau_ca_id, row.tieu_chi_id)].append(row.doan_id)
            rankings[name] = ranked
        short = LexicalRetrievalService(section_paths=repository.section_paths)
        reference = defaultdict(list)
        for row in load_artifact(db, ca_id, "EXPECTED", "C06"):
            if row["duoc_chon"]:
                reference[(row["yeu_cau_ca_id"], row["tieu_chi_id"])].append(row["doan_id"])
        for tieu_chi_id, yeu_cau_ca_id in wanted:
            criterion = knowledge.criteria[tieu_chi_id]
            key = (yeu_cau_ca_id, tieu_chi_id)
            short_rows = short.ranked(
                document.chunks[0].hop_dong_id,
                short_query(criterion["noi_dung"]),
                *_short_index(short, document.chunks),
            )
            candidates = []
            for doan_id in [
                *[d for name in rankings for d in rankings[name][key][:5]],
                *[d for d, _ in short_rows[:5]],
                *reference[key],
            ]:
                if doan_id not in candidates:
                    candidates.append(doan_id)
            pool.append(
                {
                    "ca_id": ca_id,
                    "yeu_cau_ca_id": yeu_cau_ca_id,
                    "tieu_chi_id": tieu_chi_id,
                    "criterion": criterion["noi_dung"],
                    "evidence_hint": criterion.get("bang_chung_can_thiet"),
                    "candidates": [
                        {"doan_id": d, "path": paths.get(d), "text": text[d]} for d in candidates
                    ],
                }
            )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(pool, ensure_ascii=False, indent=1), encoding="utf-8")
    print(
        f"{len(pool)} targets, {sum(len(p['candidates']) for p in pool)} pooled chunks"
        f" -> {args.output}"
    )


def _short_index(service, chunks):
    """Index chunks (with titles) in `service` and return (index_version, chunk_by_id)."""
    from legal_checker.modules.retrieval.service import chunk_index_version, path_context

    paths = service.section_paths(chunks[0].hop_dong_id)
    titled = [
        c.model_copy(update={"noi_dung": f"{t}\n{c.noi_dung}"})
        if (t := path_context(paths.get(c.doan_id)))
        else c
        for c in chunks
    ]
    version = chunk_index_version(titled, "SHORT")
    for index in service.indexes.values():
        index.index(chunks[0].hop_dong_id, titled, version)
    return version, {c.doan_id: c for c in titled}


if __name__ == "__main__":
    main()
