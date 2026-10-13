"""Protect module ownership and pure evaluation while repositories stay feature-local."""

import ast

from legal_checker.core.config import BACKEND_ROOT


def imported_names(path):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.lineno, node.module


def test_modules_do_not_depend_on_http_routes_or_development_fixtures():
    root = BACKEND_ROOT / "src/legal_checker/modules"
    paths = list(root.rglob("*.py"))
    assert paths, "Architecture check must scan the actual backend modules"
    prohibited = ("fastapi", "legal_checker.api", "legal_checker.main", "devtools")
    violations = [
        f"{path.relative_to(root)}:{line}: {name}"
        for path in paths
        for line, name in imported_names(path)
        if any(name == prefix or name.startswith(prefix + ".") for prefix in prohibited)
    ]
    assert not violations, "Module depends on HTTP/composition/fixtures: " + "; ".join(violations)


def test_evaluation_engines_do_not_open_database_or_provider_connections():
    root = BACKEND_ROOT / "src/legal_checker/modules"
    prohibited = ("psycopg", "httpx", "legal_checker.core.postgres", "legal_checker.shared.llm")
    engines = (
        "compliance/criterion_reasoner.py",
        "compliance/numeric_rules.py",
        "compliance/requirement_aggregator.py",
        "compliance/grounding_validator.py",
        "risks/common.py",
        "risks/compliance_mapper.py",
        "risks/citation_mapper.py",
        "risks/aggregator.py",
        "recommendations/generator.py",
        "recommendations/validator.py",
    )
    violations = [
        f"{path.relative_to(root)}:{line}: {name}"
        for path in (root / name for name in engines)
        for line, name in imported_names(path)
        if any(name == prefix or name.startswith(prefix + ".") for prefix in prohibited)
    ]
    assert not violations, "Pure evaluation depends on concrete connections: " + "; ".join(
        violations
    )
