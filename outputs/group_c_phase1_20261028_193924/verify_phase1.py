"""Re-run phase 1 checks and save exact commands/results, without DB or paid API."""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESTINATION = Path(__file__).resolve().parent
TEST_NAMES = [
    "test_criterion_reasoner.py",
    "test_c07_findings.py",
    "test_c07_hardening.py",
    "test_c07_extended_types.py",
    "test_grounding_validator.py",
    "test_numeric_rules.py",
    "test_numeric_rules_extended.py",
    "test_numeric_rule_scope.py",
    "test_reviewed_observations.py",
    "test_llm_observations.py",
    "test_manual_observations.py",
    "test_requirement_aggregator.py",
    "test_risks.py",
    "test_recommendations.py",
    "test_group_c_core.py",
]
CHANGED_CODE = [
    "backend/src/legal_checker/modules/compliance/criterion_reasoner.py",
    "backend/src/legal_checker/modules/compliance/decision_rules.py",
    "backend/src/legal_checker/modules/compliance/requirement_aggregator.py",
    "backend/src/legal_checker/modules/risks/aggregator.py",
    "backend/src/legal_checker/modules/risks/citation_mapper.py",
    "backend/src/legal_checker/modules/risks/compliance_mapper.py",
    "backend/src/legal_checker/modules/risks/policy.py",
    "backend/src/legal_checker/modules/risks/service.py",
    "backend/src/legal_checker/modules/recommendations/generator.py",
    "backend/src/legal_checker/modules/recommendations/validator.py",
    "backend/src/legal_checker/modules/recommendations/service.py",
    "backend/tests/unit/test_c07_hardening.py",
    "backend/tests/unit/test_requirement_aggregator.py",
    "backend/tests/unit/test_risks.py",
    "backend/tests/unit/test_recommendations.py",
    "backend/tests/unit/test_group_c_core.py",
    str(Path(__file__).relative_to(ROOT)),
    str(DESTINATION.joinpath("inventory_knowledge.py").relative_to(ROOT)),
]


def main():
    checks = [
        (
            "pytest_phase1",
            [
                "-m",
                "pytest",
                "-q",
                "-c",
                "backend/pyproject.toml",
                *["backend/tests/unit/" + name for name in TEST_NAMES],
                "backend/tests/contract/test_architecture.py",
                "--junitxml=" + str(DESTINATION / "pytest.xml"),
            ],
        ),
        (
            "ruff_check_phase1",
            ["-m", "ruff", "check", "--config", "backend/pyproject.toml", *CHANGED_CODE],
        ),
        (
            "ruff_format_phase1",
            [
                "-m",
                "ruff",
                "format",
                "--check",
                "--config",
                "backend/pyproject.toml",
                *CHANGED_CODE,
            ],
        ),
    ]
    environment = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    results = []
    for name, arguments in checks:
        command = [sys.executable, *arguments]
        result = subprocess.run(
            command, cwd=ROOT, env=environment, capture_output=True, text=True, encoding="utf-8"
        )
        output = result.stdout + result.stderr
        DESTINATION.joinpath(name + ".log").write_text(output, encoding="utf-8")
        results.append({"name": name, "command": command, "exit_code": result.returncode})
        print(name, "exit_code=" + str(result.returncode))
        print(output)
    report = {
        "completed_at_asia_saigon": datetime.now(timezone(timedelta(hours=7))).isoformat(),
        "interpreter": sys.executable,
        "python_version": sys.version,
        "scope": "PHASE_1_CORE_BUSINESS_TESTS_ONLY",
        "postgresql_tests_run": False,
        "workflow_runner_or_save_read_demo_run": False,
        "checks": results,
    }
    DESTINATION.joinpath("checks.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return int(any(result["exit_code"] for result in results))


if __name__ == "__main__":
    raise SystemExit(main())
