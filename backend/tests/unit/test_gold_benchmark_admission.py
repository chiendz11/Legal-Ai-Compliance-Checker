"""Regression checks for benchmark inflation, separate from legal correctness."""

import json

from legal_checker.modules.benchmarks.evaluator import GoldBenchmarkEvaluator


def evaluator(tmp_path, finding="UNKNOWN"):
    cases = tmp_path / "cases"
    cases.mkdir()
    (cases / "CASE.json").write_text(
        json.dumps(
            {
                "gold_version": "TEST",
                "criteria": [
                    {
                        "criterion_id": "JUDGED",
                        "finding": finding,
                        "annotation_quality": "GOLD",
                        "disposition": "ASSESSED",
                        "evidence": [],
                        "reason": "Authored test target",
                    },
                    {
                        "criterion_id": "OUTSIDE",
                        "finding": "UNKNOWN",
                        "annotation_quality": "GOLD",
                        "disposition": "OUTSIDE_REVIEW_SCOPE",
                    },
                    {
                        "criterion_id": "PENDING",
                        "finding": "UNKNOWN",
                        "annotation_quality": "PENDING_ADJUDICATION",
                    },
                ],
                "requirements": [
                    {
                        "requirement_id": "FAMILY",
                        "requirement_version_id": "V1",
                        "applicability_status": "CONFIRMED",
                    }
                ],
            }
        )
    )
    return GoldBenchmarkEvaluator(tmp_path)


def test_missing_prediction_is_not_a_correct_legal_unknown(tmp_path):
    result = evaluator(tmp_path).evaluate_case("CASE", [])
    assert result.total_evaluated == 1
    assert result.correct_count == 0
    assert result.confusion_matrix["UNKNOWN"]["NO_PREDICTION"] == 1


def test_scope_exclusions_and_pending_targets_are_not_scored(tmp_path):
    result = evaluator(tmp_path).evaluate_case(
        "CASE", [{"tieu_chi_id": "JUDGED", "finding": "UNKNOWN"}]
    )
    assert result.total_evaluated == result.correct_count == 1


def test_c05_joins_family_and_checks_selected_version(tmp_path):
    benchmark = evaluator(tmp_path)
    predicted = [
        {
            "yeu_cau_ca_id": "CASE_FAMILY",
            "requirement_id": "FAMILY",
            "requirement_version_id": "WRONG",
            "applicability_status": "CONFIRMED",
        }
    ]
    result = benchmark.evaluate_case("CASE", [], predicted)
    assert result.c05_evaluations[0]["match"] is False
    predicted[0]["requirement_version_id"] = "V1"
    result = benchmark.evaluate_case("CASE", [], predicted)
    assert result.c05_evaluations[0]["match"] is True
