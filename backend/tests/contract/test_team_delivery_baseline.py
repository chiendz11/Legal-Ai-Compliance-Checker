"""Catch cross-document drift in the shared dataset, Python ports, HTTP and SQL recipes."""

import inspect
import json
import re
from importlib import import_module

from legal_checker.api.dependencies import Services
from legal_checker.core.config import PROJECT_ROOT
from legal_checker.core.postgres import connect_postgres
from legal_checker.main import create_app

DOCS = PROJECT_ROOT / "docs"


def read(path):
    return json.loads(path.read_text())


def test_team_baseline_metadata_agrees_with_dataset_manifest():
    manifest = read(PROJECT_ROOT / "configs/dataset_dev_validation.json")
    policy = read(DOCS / "contracts/integration_policy.json")
    dictionary = read(DOCS / "contracts/data_dictionary.json")
    catalog = read(DOCS / "contracts/catalog.json")
    acceptance = read(DOCS / "contracts/handoff_acceptance.json")
    baseline = policy["dataset_baseline"]
    for document in (baseline, dictionary["dataset_baseline"], acceptance):
        assert document["dataset_version"] == manifest["dataset_version"]
        assert document["knowledge_snapshot_sha256"] == manifest["knowledge_snapshot_sha256"]
    assert catalog["team_delivery_baseline"] == acceptance["baseline_id"]
    assert policy["team_delivery_baseline"] == acceptance["baseline_id"]
    assert baseline["review_status"] == manifest["knowledge_review_status"]
    assert baseline["reference_profile"] == manifest["assessment_profile"]
    assert (
        baseline["atomic_requirement_count"]
        == dictionary["dataset_baseline"]["reference_atomic_requirements"]
    )
    assert baseline["migration_strategy"] == manifest["migration_strategy"]


def resolve_callable(name):
    parts = name.split(".")
    for count in range(len(parts) - 1, 0, -1):
        try:
            value = import_module(".".join(parts[:count]))
        except ModuleNotFoundError as error:
            if not name.startswith(error.name):
                raise
            continue
        for part in parts[count:]:
            value = getattr(value, part)
        return value
    raise AssertionError(f"Unresolvable documented port: {name}")


def test_documented_ports_match_the_actual_workflow_call_signatures():
    catalog = read(DOCS / "contracts/catalog.json")
    entries = [*catalog["handoffs"], *catalog["auxiliary_ports"]]
    for entry in entries:
        if "runtime_port" not in entry:
            continue
        function = resolve_callable(entry["runtime_port"])
        parameters = inspect.signature(function).parameters
        assert [name for name in parameters if name != "self"] == entry["call_parameters"], entry
        assert entry["composition_owner"] == "P5"
    verifier = resolve_callable(
        "legal_checker.modules.compliance.verification.CriterionVerificationProvider.verify"
    )
    assert inspect.signature(verifier).parameters["coverage"].kind == inspect.Parameter.KEYWORD_ONLY
    risk = next(entry for entry in catalog["handoffs"] if entry["module"] == "risks")
    assert "C08" not in risk["input"]


def test_frontend_design_models_match_runtime_models_including_diagnostics():
    design = read(DOCS / "architecture/openapi.design.json")
    runtime = create_app(services=Services(knowledge=None, assessments=None)).openapi()
    current = runtime["components"]["schemas"]
    for name, schema in design["components"]["schemas"].items():
        source = name.removeprefix("Input_").removeprefix("Output_")
        if source in current:
            assert schema == current[source], name
    assert "diagnostics" in design["components"]["schemas"]["PipelineResult"]["properties"]
    assert (
        "not implemented"
        not in design["components"]["securitySchemes"]["BearerAuth"]["description"].lower()
    )
    client = (PROJECT_ROOT / "frontend/src/shared/api/client.ts").read_text()
    aliases = set(re.findall(r'Schemas\["([^"]+)"\]', client))
    assert aliases <= design["components"]["schemas"].keys()
    assert aliases == design["x-client-schema-aliases"].keys()


def documentation_selects():
    sources = [
        DOCS / "modules/README.md",
        *(DOCS / "modules").glob("group_*.md"),
        DOCS / "contracts/knowledge_applicability_policy.md",
        DOCS / "architecture/data_flow_and_storage.md",
        DOCS / "database/local_setup.md",
    ]
    for source in sources:
        for number, block in enumerate(
            re.findall(r"```sql\s*\n(.*?)```", source.read_text(), re.S)
        ):
            uncommented = re.sub(r"--[^\n]*", "", block)
            for statement in uncommented.split(";"):
                statement = statement.strip()
                if statement.upper().startswith(("SELECT ", "WITH ")):
                    yield source.relative_to(DOCS).as_posix(), number, statement


def test_documented_select_queries_compile_against_actual_migrations(database_url):
    """EXPLAIN catches ambiguous JOINs and stale columns without running customer queries."""
    statements = list(documentation_selects())
    assert len(statements) >= 30
    errors = []
    with connect_postgres(database_url) as connection:
        for path, number, statement in statements:
            params = {name: "TEST" for name in re.findall(r"%\((\w+)\)s", statement)}
            try:
                with connection.transaction():
                    connection.execute("EXPLAIN " + statement, params or None).fetchall()
            except Exception as error:
                errors.append(f"{path}, SQL block {number}: {error}")
    assert not errors, "Invalid documented SQL:\n" + "\n".join(errors)
