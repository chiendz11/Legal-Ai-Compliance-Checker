"""Production Benchmark and Evaluation Engine for Scoped and E2E Gold datasets.

Evaluates pipeline predictions against source-grounded Gold annotations across:
- C07 Criterion reasoning (Accuracy, Precision, Recall, F1, Confusion Matrix)
- C06 Evidence grounding (Span/Quote overlap verification)
- C05 Requirement scope & version resolution
- Layer coverage and release gate verification
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[5]
_CONFIGURED_DATA = Path(os.environ.get("GOLD_DATASET_PATH", "data/private/gold"))
BENCHMARK_DATA_DIR = (
    _CONFIGURED_DATA if _CONFIGURED_DATA.is_absolute() else _REPO_ROOT / _CONFIGURED_DATA
)


@dataclass
class CriterionEvaluation:
    criterion_id: str
    requirement_id: str
    gold_finding: str
    pred_finding: str
    match: bool
    evidence_match: bool
    gold_reason: str
    pred_explanation: str
    gold_quotes: list[str] = field(default_factory=list)
    pred_quotes: list[str] = field(default_factory=list)


@dataclass
class ClassMetrics:
    support: int = 0
    tp: int = 0
    fp: int = 0
    fn: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0


@dataclass
class BenchmarkEvaluationResult:
    case_id: str
    gold_version: str
    total_evaluated: int
    correct_count: int
    accuracy: float
    macro_f1: float
    per_class_metrics: dict[str, dict[str, Any]]
    confusion_matrix: dict[str, dict[str, int]]
    criterion_evaluations: list[dict[str, Any]]
    c05_evaluations: list[dict[str, Any]]
    summary: str


class GoldBenchmarkEvaluator:
    """Production benchmark evaluator for Legal-AI-Compliance-Checker."""

    def __init__(self, data_dir: Path | str | None = None):
        self.data_dir = Path(data_dir) if data_dir else BENCHMARK_DATA_DIR
        self._coverage_cache: dict[str, Any] | None = None
        self._cases_cache: dict[str, dict[str, Any]] = {}

    def get_gold_coverage(self) -> dict[str, Any]:
        """Returns the summary of gold coverage across all registered cases."""
        if self._coverage_cache is None:
            cov_path = self.data_dir / "GOLD_COVERAGE.json"
            if cov_path.exists():
                self._coverage_cache = json.loads(cov_path.read_text(encoding="utf-8"))
            else:
                self._coverage_cache = {
                    "release_status": "UNKNOWN",
                    "full_e2e_gold_ready": False,
                    "registered_cases": 0,
                }
        return self._coverage_cache

    def get_release_gate_status(self) -> dict[str, Any]:
        """Returns the full release gate status including missing layers/cases."""
        gate_path = self.data_dir / "FULL_RELEASE_GATE.json"
        if gate_path.exists():
            return json.loads(gate_path.read_text(encoding="utf-8"))
        return {
            "release_status": "INCOMPLETE",
            "full_e2e_gold_ready": False,
            "errors": [],
        }

    def load_gold_case(self, case_id: str) -> dict[str, Any] | None:
        """Loads the gold annotation for a specific case."""
        if case_id in self._cases_cache:
            return self._cases_cache[case_id]

        case_path = self.data_dir / "cases" / f"{case_id}.json"
        if not case_path.exists():
            return None

        data = json.loads(case_path.read_text(encoding="utf-8"))
        self._cases_cache[case_id] = data
        return data

    def list_gold_cases(self) -> list[str]:
        """Lists all case IDs with gold answers available."""
        cases_dir = self.data_dir / "cases"
        if not cases_dir.exists():
            return []
        return sorted([p.stem for p in cases_dir.glob("*.json")])

    def evaluate_case(
        self,
        case_id: str,
        predicted_criteria: list[dict[str, Any] | Any],
        predicted_requirements: list[dict[str, Any] | Any] | None = None,
    ) -> BenchmarkEvaluationResult:
        """Evaluates predicted criterion and requirement findings against gold answers."""
        gold_case = self.load_gold_case(case_id)
        if not gold_case:
            raise ValueError(f"No Gold answer dataset found for case {case_id}")

        gold_criteria = {
            c["criterion_id"]: c
            for c in gold_case.get("criteria", [])
            if c.get("annotation_quality") == "GOLD"
            and c.get("disposition", "ASSESSED") == "ASSESSED"
        }
        gold_version = gold_case.get("gold_version", "UNKNOWN")

        # Normalize predicted criteria
        pred_map: dict[str, Any] = {}
        for p in predicted_criteria:
            cid = getattr(p, "tieu_chi_id", None) or (
                p.get("tieu_chi_id") if isinstance(p, dict) else None
            )
            if cid:
                pred_map[cid] = p

        # Labels set
        classes = ["SATISFIED", "VIOLATED", "UNKNOWN", "MISSING"]
        prediction_labels = [*classes, "NO_PREDICTION"]
        matrix: dict[str, dict[str, int]] = {g: {p: 0 for p in prediction_labels} for g in classes}
        class_stats: dict[str, ClassMetrics] = {c: ClassMetrics() for c in classes}

        criterion_evals: list[CriterionEvaluation] = []
        correct_count = 0
        total_judged = 0

        for crit_id, gold_c in gold_criteria.items():
            gold_finding = gold_c.get("finding", "UNKNOWN")
            if gold_finding not in matrix:
                matrix[gold_finding] = {p: 0 for p in prediction_labels}
            if gold_finding not in class_stats:
                class_stats[gold_finding] = ClassMetrics()

            pred_item = pred_map.get(crit_id)
            if pred_item is None:
                pred_finding = "NO_PREDICTION"
                pred_exp = "Không có kết quả dự đoán từ pipeline"
                pred_quotes = []
            else:
                pred_finding = (
                    getattr(pred_item, "finding", None)
                    or (pred_item.get("finding") if isinstance(pred_item, dict) else None)
                    or "UNKNOWN"
                )
                pred_exp = getattr(pred_item, "giai_thich", "") or (
                    pred_item.get("giai_thich", "") if isinstance(pred_item, dict) else ""
                )
                pred_evidence = getattr(pred_item, "evidence", []) or (
                    pred_item.get("evidence", []) if isinstance(pred_item, dict) else []
                )
                pred_quotes = [
                    getattr(e, "trich_dan", "")
                    if hasattr(e, "trich_dan")
                    else e.get("trich_dan", "")
                    for e in pred_evidence
                ]

            gold_quotes = [e.get("quote", "") for e in gold_c.get("evidence", [])]
            match = pred_item is not None and gold_finding == pred_finding
            if match:
                correct_count += 1
            total_judged += 1

            # Check evidence overlap
            evidence_match = False
            if gold_quotes and pred_quotes:
                # Substring or token overlap
                for gq in gold_quotes:
                    gq_clean = " ".join(gq.split()).lower()
                    for pq in pred_quotes:
                        pq_clean = " ".join(pq.split()).lower()
                        if gq_clean and pq_clean and (gq_clean in pq_clean or pq_clean in gq_clean):
                            evidence_match = True
                            break
                    if evidence_match:
                        break
            elif pred_item is not None and not gold_quotes and not pred_quotes:
                evidence_match = True

            # Update Confusion Matrix & Class Stats
            safe_pred = pred_finding if pred_finding in matrix[gold_finding] else "NO_PREDICTION"
            matrix[gold_finding][safe_pred] += 1

            class_stats[gold_finding].support += 1
            if match:
                class_stats[gold_finding].tp += 1
            else:
                class_stats[gold_finding].fn += 1
                if safe_pred in class_stats:
                    class_stats[safe_pred].fp += 1

            criterion_evals.append(
                CriterionEvaluation(
                    criterion_id=crit_id,
                    requirement_id=gold_c.get("requirement_id", ""),
                    gold_finding=gold_finding,
                    pred_finding=pred_finding,
                    match=match,
                    evidence_match=evidence_match,
                    gold_reason=gold_c.get("reason", ""),
                    pred_explanation=pred_exp,
                    gold_quotes=gold_quotes,
                    pred_quotes=pred_quotes,
                )
            )

        # Calculate Precision, Recall, F1 for each class
        f1_scores = []
        per_class_dict: dict[str, dict[str, Any]] = {}
        for c, stats in class_stats.items():
            prec = stats.tp / (stats.tp + stats.fp) if (stats.tp + stats.fp) > 0 else 0.0
            rec = stats.tp / (stats.tp + stats.fn) if (stats.tp + stats.fn) > 0 else 0.0
            f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
            stats.precision = round(prec, 4)
            stats.recall = round(rec, 4)
            stats.f1 = round(f1, 4)
            if stats.support > 0:
                f1_scores.append(f1)
            per_class_dict[c] = {
                "support": stats.support,
                "tp": stats.tp,
                "fp": stats.fp,
                "fn": stats.fn,
                "precision": stats.precision,
                "recall": stats.recall,
                "f1": stats.f1,
            }

        accuracy = round(correct_count / total_judged, 4) if total_judged > 0 else 0.0
        macro_f1 = round(sum(f1_scores) / len(f1_scores), 4) if f1_scores else 0.0

        # Evaluate C05 Requirements if provided
        c05_evals = []
        if predicted_requirements:
            gold_reqs = {r["requirement_id"]: r for r in gold_case.get("requirements", [])}
            pred_req_map = {}
            for r in predicted_requirements:
                rid = getattr(r, "requirement_id", None) or (
                    r.get("requirement_id") if isinstance(r, dict) else None
                )
                if rid:
                    pred_req_map[rid] = r

            for rid, gr in gold_reqs.items():
                pr = pred_req_map.get(rid)
                gold_status = gr.get("applicability_status", "CONFIRMED")
                pred_status = (
                    getattr(pr, "applicability_status", None)
                    or (pr.get("applicability_status") if isinstance(pr, dict) else None)
                    or "UNKNOWN"
                )
                pred_version = getattr(pr, "requirement_version_id", None) or (
                    pr.get("requirement_version_id") if isinstance(pr, dict) else None
                )
                c05_evals.append(
                    {
                        "requirement_id": rid,
                        "gold_version_id": gr.get("requirement_version_id"),
                        "gold_applicability": gold_status,
                        "pred_status": pred_status,
                        "pred_version_id": pred_version,
                        "match": (
                            pr is not None
                            and gold_status == pred_status
                            and gr.get("requirement_version_id") == pred_version
                        ),
                    }
                )

        summary = (
            f"Case {case_id}: Đã đối soát {total_judged} tiêu chí Gold. "
            f"Đúng {correct_count}/{total_judged} "
            f"(Accuracy: {accuracy * 100:.1f}%, Macro-F1: {macro_f1:.4f})."
        )

        return BenchmarkEvaluationResult(
            case_id=case_id,
            gold_version=gold_version,
            total_evaluated=total_judged,
            correct_count=correct_count,
            accuracy=accuracy,
            macro_f1=macro_f1,
            per_class_metrics=per_class_dict,
            confusion_matrix=matrix,
            criterion_evaluations=[e.__dict__ for e in criterion_evals],
            c05_evaluations=c05_evals,
            summary=summary,
        )
