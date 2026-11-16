"""Run the full assessment (steps 1–7) on a split and compare it with the QA references.

The references are SILVER outputs from the dataset build (``legal_gold=false``), mostly
"INSUFFICIENT", so agreement is not legal accuracy. The report therefore separates:

* agreement with the reference on every item (scope, applicability, requirement status,
  criterion finding);
* how many items each side actually decides (not UNKNOWN / INSUFFICIENT);
* on the items the reference does decide, how many we decide the same way.

Steps 1–2 read the PDF when its bytes are in the source cache (``scripts.seed_source_cache``),
otherwise they use the case's frozen C02 reference, exactly like the API. Offline by default;
``--llm`` makes paid calls through ASSESSMENT_LLM / OPENAI_* and is meant for a few cases.
Results are written under data/private/eval/ (git-ignored). Run from the repository root:

    python -m scripts.eval_assessment --split VALIDATION
    python -m scripts.eval_assessment --split VALIDATION --limit 3 --llm
"""

import argparse
import csv
import json
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from devtools.upstream_fixtures import list_cases, load_artifact, load_context
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
UNDECIDED = {"UNKNOWN", "INSUFFICIENT"}
MISSING = "<missing>"  # the reference has the item, our run does not
DIMENSIONS = ("scope", "applicability", "requirement", "criterion")


def build_source(settings, with_llm: bool):
    """The same module source the API builds (verifier, OCR, reference policy, C07 options)."""
    from legal_checker.api.dependencies import module_source
    from legal_checker.modules.assessments.cases import CaseRepository
    from legal_checker.shared.storage.http import CachedHttpSourceStorage
    from legal_checker.shared.storage.uploads import LocalUploadStorage, RoutingSourceStorage

    if settings.assessment_modules not in {"modules", "modules_di_reference"}:
        raise SystemExit("Set ASSESSMENT_MODULES=modules or modules_di_reference in .env")
    storage = RoutingSourceStorage(
        LocalUploadStorage(settings.upload_dir, max_bytes=settings.source_max_bytes),
        CachedHttpSourceStorage(
            settings.source_cache_dir,
            timeout_seconds=settings.source_download_timeout_seconds,
            max_bytes=settings.source_max_bytes,
        ),
    )
    source = module_source(settings, CaseRepository(settings.database_url), storage)
    if not with_llm:
        source.llm_client_factory = None  # offline: no paid call, whatever .env says
    return source


def case_context(database_url: str, source, knowledge, ca_id: str, stamp: str):
    """The case's own deployment pin and the current knowledge, as a new API run would use.

    The reference run may be pinned to an older deployment; reusing it would fail the
    workflow's pin check or silently evaluate under another rule version.
    """
    from legal_checker.shared.contracts.common import Context

    reference = load_context(database_url, ca_id)
    row = source.cases.get(ca_id)
    if row is None:
        raise LookupError(f"Case {ca_id} is not in runtime.ca_danh_gia")
    return Context(
        ca_id=ca_id,
        **row.case.deployment.model_dump(),
        knowledge_snapshot_sha256=knowledge.sha256,
        run_id=f"{ca_id}_EVAL_{stamp}",
        trace_id=f"EVAL_{stamp}_{reference.trace_id}"[:120],
    )


def references(database_url: str, ca_id: str) -> dict[str, dict]:
    """Reference status per item, keyed the same way as our outputs."""
    pipeline = load_artifact(database_url, ca_id, "EXPECTED", "PipelineResponse")["payload"]
    return {
        "scope": {
            r["yeu_cau_ca_id"]: r["scope_status"]
            for r in load_artifact(database_url, ca_id, "EXPECTED", "C04")
        },
        "applicability": {
            r["yeu_cau_ca_id"]: r["applicability_status"]
            for r in load_artifact(database_url, ca_id, "EXPECTED", "C05")
        },
        "requirement": {
            r["yeu_cau_ca_id"]: r["status"]
            for r in load_artifact(database_url, ca_id, "EXPECTED", "C08")
        },
        "criterion": {
            f"{r['yeu_cau_ca_id']}|{r['tieu_chi_id']}": r["finding"]
            for r in pipeline["criterion_results"]
        },
    }


def ours(draft) -> dict[str, dict]:
    payload = draft.evaluation.payload
    return {
        "scope": {r.yeu_cau_ca_id: r.scope_status for r in draft.scope},
        "applicability": {r.yeu_cau_ca_id: r.applicability_status for r in draft.requirements},
        "requirement": {r.yeu_cau_ca_id: r.status for r in payload.requirement_results},
        "criterion": {
            f"{r.yeu_cau_ca_id}|{r.tieu_chi_id}": r.finding for r in payload.criterion_results
        },
    }


def summarize(matrix: Counter) -> dict:
    total = sum(matrix.values())
    agree = sum(n for (ref, mine), n in matrix.items() if ref == mine)
    ref_decided = {k: n for k, n in matrix.items() if k[0] not in UNDECIDED}
    same_on_decided = sum(n for (ref, mine), n in ref_decided.items() if ref == mine)
    return {
        "items": total,
        "agreement": round(agree / total, 4) if total else None,
        "reference_decided": sum(ref_decided.values()),
        "ours_decided": sum(
            n for (_, mine), n in matrix.items() if mine not in UNDECIDED | {MISSING}
        ),
        "ours_missing": sum(n for (_, mine), n in matrix.items() if mine == MISSING),
        "same_where_reference_decided": same_on_decided,
        "confusion": {f"{ref} -> {mine}": n for (ref, mine), n in sorted(matrix.items())},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--split", default="VALIDATION", choices=["DEV", "VALIDATION", "TEST"])
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--case", action="append", help="Only these case IDs (repeatable)")
    parser.add_argument("--llm", action="store_true", help="Paid C07 calls (ASSESSMENT_LLM)")
    parser.add_argument("--output", type=Path, default=ROOT / "data/private/eval")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env", override=False)
    from legal_checker.core.config import Settings
    from legal_checker.modules.legal_knowledge.repository import Knowledge
    from legal_checker.workflows.assessment_workflow import DraftAssessmentWorkflow

    settings = Settings.from_env()
    if args.llm and settings.assessment_llm == "offline":
        parser.error("--llm needs ASSESSMENT_LLM=openai (or groq) and its key in .env")
    knowledge = Knowledge(settings.database_url)
    source = build_source(settings, args.llm)
    cases = args.case or list_cases(settings.database_url, args.split)[: args.limit]
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    matrices: dict[str, Counter] = defaultdict(Counter)
    rows, failures, labels = [], [], Counter()
    started = time.monotonic()
    for index, ca_id in enumerate(cases, start=1):
        try:
            context = case_context(settings.database_url, source, knowledge, ca_id, stamp)
            case, modules, evaluator = source.prepare(context)
            label = source.label(case)
            draft = DraftAssessmentWorkflow(modules, knowledge, evaluator=evaluator).evaluate(
                case, context
            )
        except Exception as error:  # one failed case must not hide the others
            failures.append({"ca_id": ca_id, "error": f"{type(error).__name__}: {error}"[:500]})
            print(f"[{index}/{len(cases)}] {ca_id} FAILED {type(error).__name__}")
            continue
        labels[label] += 1
        reference, mine = references(settings.database_url, ca_id), ours(draft)
        for dimension in DIMENSIONS:
            for key, ref in reference[dimension].items():
                value = mine[dimension].get(key, MISSING)
                matrices[dimension][(ref, value)] += 1
                if ref != value:
                    rows.append(
                        {
                            "ca_id": ca_id,
                            "dimension": dimension,
                            "item": key,
                            "reference": ref,
                            "ours": value,
                            "steps_1_2": label,
                        }
                    )
        decided = sum(1 for v in mine["requirement"].values() if v not in UNDECIDED)
        print(
            f"[{index}/{len(cases)}] {ca_id} {label}: "
            f"{decided}/{len(mine['requirement'])} requirements decided"
        )

    summary = {
        "split": args.split,
        "cases": len(cases),
        "failed": failures,
        "steps_1_2": dict(labels),
        "llm": args.llm,
        "knowledge_sha256": knowledge.sha256,
        "seconds": round(time.monotonic() - started, 1),
        "note": "References are silver (legal_gold=false): agreement is not legal accuracy.",
        "dimensions": {d: summarize(matrices[d]) for d in DIMENSIONS},
    }
    args.output.mkdir(parents=True, exist_ok=True)
    base = args.output / f"assessment_{args.split.lower()}_{stamp}"
    base.with_suffix(".json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with base.with_suffix(".csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle, ["ca_id", "dimension", "item", "reference", "ours", "steps_1_2"]
        )
        writer.writeheader()
        writer.writerows(rows)

    print()
    print(f"{'dimension':<14}{'items':>7}{'agree':>8}{'ref dec.':>10}{'ours dec.':>11}{'same':>7}")
    for dimension, s in summary["dimensions"].items():
        agreement = "-" if s["agreement"] is None else f"{s['agreement']:.1%}"
        print(
            f"{dimension:<14}{s['items']:>7}{agreement:>8}{s['reference_decided']:>10}"
            f"{s['ours_decided']:>11}{s['same_where_reference_decided']:>7}"
        )
    print(f"\n{len(failures)} failed; written {base}.json and .csv")


if __name__ == "__main__":
    main()
