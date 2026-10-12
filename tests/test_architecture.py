"""Protect the business module boundary as adapters and HTTP endpoints are added."""

import ast
from pathlib import Path


def test_business_modules_do_not_import_transport_or_concrete_adapters():
    root = Path(__file__).resolve().parents[1] / "app" / "business_modules"
    prohibited = ("fastapi", "httpx", "sqlite3", "app.adapters", "app.bootstrap", "app.api")
    violations = []
    for path in root.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            imports = []
            if isinstance(node, ast.Import):
                imports = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports = [node.module]
            for name in imports:
                if any(name == prefix or name.startswith(prefix + ".") for prefix in prohibited):
                    violations.append(f"{path.relative_to(root)}:{node.lineno}: {name}")
    assert not violations, "Business modules depend on concrete infrastructure: " + "; ".join(
        violations
    )
