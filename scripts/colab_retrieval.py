"""Run step-4 retrieval on a GPU runtime from an exported bundle (no PostgreSQL needed).

Inside the unzipped export (see scripts/export_colab_retrieval.py):

    pip install -q "sentence-transformers>=3,<6"
    python colab_retrieval.py --mode rerank --fp16

Writes `results/` with our C06 rows, Recall@K metrics and the embedding cache; copy
`results/embedding_cache` to `data/private/embedding_cache` locally to reuse the vectors.
"""

import argparse
import gzip
import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=next(HERE.glob("bundle_*.jsonl.gz"), None))
    parser.add_argument(
        "--mode", default="rerank", choices=["bm25", "bm25_rerank", "hybrid", "rerank"]
    )
    parser.add_argument("--embedding-model")
    parser.add_argument("--rerank-model")
    parser.add_argument("--fp16", action="store_true", help="Half precision (T4/A100/RTX)")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--no-path", action="store_true", help="Do not index article titles")
    parser.add_argument("--no-fact", action="store_true", help="Do not promote C02 field evidence")
    parser.add_argument("--out", type=Path, default=HERE / "results")
    args = parser.parse_args()
    if args.fp16:
        os.environ["LEGAL_CHECKER_ML_FP16"] = "1"

    from legal_checker.modules.retrieval.fact_evidence import FactEvidence
    from legal_checker.modules.retrieval.service import (
        LexicalRetrievalService,
        semantic_retrieval_service,
    )
    from legal_checker.shared.contracts.common import Context
    from legal_checker.shared.contracts.document_intelligence import Chunk
    from legal_checker.shared.contracts.retrieval import RetrievalEvidence
    from legal_checker.shared.contracts.temporal import ApplicableRequirement

    args.out.mkdir(parents=True, exist_ok=True)
    current_paths: dict[str, str] = {}

    def section_paths(hop_dong_id: str) -> dict[str, str]:
        return current_paths

    current_facts: list = []

    def fact_evidence(hop_dong_id: str) -> list:
        return current_facts

    path_option = {} if args.no_path else {"section_paths": section_paths}
    if not args.no_fact:
        path_option["fact_evidence"] = fact_evidence
    if args.mode == "bm25":
        service = LexicalRetrievalService(**path_option)
    else:
        service = semantic_retrieval_service(
            **path_option,
            embedding_model=args.embedding_model,
            rerank_model=args.rerank_model,
            cache_dir=args.out / "embedding_cache",
            rerank=args.mode in ("rerank", "bm25_rerank"),
            dense=args.mode in ("hybrid", "rerank"),
        )
    print(f"Mode {args.mode}: {service.retrieval_version}", flush=True)

    ks = (1, 3, 5, 10)
    hits_at: Counter = Counter()
    targets = processed = 0
    goldset_path = HERE / "goldset_DEV.json"
    goldset = (
        json.loads(goldset_path.read_text(encoding="utf-8")) if goldset_path.exists() else None
    )
    gold_by_case: dict[str, list[int]] = defaultdict(list)
    for number, target in enumerate((goldset or {}).get("pool", [])):
        gold_by_case[target["ca_id"]].append(number)
    gold: Counter = Counter()
    started = time.time()
    with (
        gzip.open(args.bundle, "rt", encoding="utf-8") as source,
        gzip.open(args.out / f"c06_{args.mode}.jsonl.gz", "wt", encoding="utf-8") as sink,
    ):
        for number, line in enumerate(source, start=1):
            if args.limit and number > args.limit:
                break
            case = json.loads(line)
            current_paths.clear()
            current_paths.update(case.get("section_paths") or {})
            current_facts[:] = [
                FactEvidence(f["ten_truong"], tuple(f["doan_ids"]))
                for f in case.get("fact_evidence") or []
            ]
            knowledge = SimpleNamespace(
                criteria_for=lambda version, criteria=case["criteria"]: criteria.get(version, [])
            )
            ours = service.retrieve(
                Context.model_validate(case["context"]),
                [ApplicableRequirement.model_validate(r) for r in case["requirements"]],
                [Chunk.model_validate(c) for c in case["chunks"]],
                knowledge,
            )
            sink.write(
                json.dumps(
                    {"ca_id": case["ca_id"], "c06": [r.model_dump(mode="json") for r in ours]},
                    ensure_ascii=False,
                )
                + "\n"
            )
            for number in gold_by_case.get(case["ca_id"], []):
                target = goldset["pool"][number]
                grade = {
                    c["doan_id"]: goldset["labels"][str(number)][i]
                    for i, c in enumerate(target["candidates"])
                }
                rows = sorted(
                    (
                        r
                        for r in ours
                        if r.tieu_chi_id == target["tieu_chi_id"]
                        and r.yeu_cau_ca_id == target["yeu_cau_ca_id"]
                    ),
                    key=lambda r: r.thu_hang,
                )
                order = [r.doan_id for r in rows]
                chosen = [r.doan_id for r in rows if r.duoc_chon]
                if 2 in grade.values():
                    gold["direct_targets"] += 1
                    for k in ks:
                        gold[f"strict@{k}"] += any(grade.get(d, 0) == 2 for d in order[:k])
                    gold["direct_selected"] += any(grade.get(d, 0) == 2 for d in chosen)
                gold["selected"] += len(chosen)
                gold["selected_relevant"] += sum(grade.get(d, 0) >= 1 for d in chosen)
            ranking = defaultdict(list)
            for row in sorted(ours, key=lambda r: r.thu_hang):
                ranking[(row.yeu_cau_ca_id, row.tieu_chi_id)].append(row.doan_id)
            selected = defaultdict(list)
            for row in map(RetrievalEvidence.model_validate, case["reference"]):
                if row.duoc_chon:
                    selected[(row.yeu_cau_ca_id, row.tieu_chi_id)].append(row.doan_id)
            for key, chosen in selected.items():
                targets += 1
                for k in ks:
                    hits_at[k] += any(d in ranking[key][:k] for d in chosen)
            processed = number
            elapsed = time.time() - started
            print(f"  case {number} {case['ca_id']}: {elapsed:.0f}s elapsed", flush=True)

    metrics = {
        "mode": args.mode,
        "retrieval_version": service.retrieval_version,
        "cases": processed,
        "criteria_with_reference_selection": targets,
        **{f"recall@{k}": round(hits_at[k] / max(targets, 1), 4) for k in ks},
        "seconds": round(time.time() - started, 1),
    }
    if gold["direct_targets"]:
        # Independent relevance labels (2 = answers the criterion); see eval_retrieval_goldset.
        metrics["goldset"] = {
            "targets_with_direct_chunk": gold["direct_targets"],
            **{f"strict@{k}": round(gold[f"strict@{k}"] / gold["direct_targets"], 4) for k in ks},
            "selection_has_direct": f"{gold['direct_selected']}/{gold['direct_targets']}",
            "selected_rows": gold["selected"],
            "selected_relevant_share": round(
                gold["selected_relevant"] / max(gold["selected"], 1), 4
            ),
        }
    (args.out / f"metrics_{args.mode}.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
