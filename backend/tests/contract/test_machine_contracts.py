"""Keep coding specifications valid, reference-resolvable and honest about runtime support."""

import json
from importlib import import_module

import pytest
from devtools.database_schema import TABLES
from devtools.qa_schema import QA_TABLES
from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from legal_checker.api.dependencies import Services
from legal_checker.core.config import PROJECT_ROOT
from legal_checker.main import create_app
from legal_checker.shared.contracts.audit import LlmAudit
from legal_checker.shared.contracts.handoffs import HandoffSet
from legal_checker.shared.contracts.temporal import ApplicableRequirement
from openapi_spec_validator import validate

DOCS = PROJECT_ROOT / "docs"


@pytest.fixture(scope="module")
def documents():
    return {
        str(path.relative_to(DOCS)): json.loads(path.read_text(encoding="utf-8"))
        for path in [
            *sorted((DOCS / "contracts").glob("*.json")),
            DOCS / "openapi.design.json",
            DOCS / "module_contracts.schema.json",
            DOCS / "llm_audit.schema.json",
        ]
    }


def test_module_schemas_match_runtime_models(documents):
    for entry in documents["contracts/catalog.json"]["contracts"]:
        module_name, model_name = entry["python_import"].rsplit(".", 1)
        assert module_name.startswith("legal_checker.shared.contracts.")
        model = getattr(import_module(module_name), model_name)
        document = documents[f"contracts/{entry['schema']}"]
        structural = {
            k: v for k, v in document.items() if k != "$schema" and not k.startswith("x-")
        }
        assert structural == model.model_json_schema(), (
            f"Update {entry['schema']} and the runtime model together"
        )
    assert documents["module_contracts.schema.json"] == HandoffSet.model_json_schema()
    assert documents["llm_audit.schema.json"] == LlmAudit.model_json_schema()


@pytest.mark.parametrize("name", ["runtime", "openapi.design.json"])
def test_openapi_is_valid_and_has_no_unresolved_references(documents, name):
    document = (
        create_app(services=Services(knowledge=None, assessments=None)).openapi()
        if name == "runtime"
        else documents[name]
    )
    validate(document)


@pytest.mark.parametrize("code", [*(f"C{i:02}" for i in range(1, 14)), "X01", "X02"])
def test_each_contract_is_a_standalone_2020_12_schema(documents, code):
    schema = documents[f"contracts/{code}.schema.json"]
    Draft202012Validator.check_schema(schema)

    def walk(value):
        if isinstance(value, dict):
            if "$ref" in value:
                reference = value["$ref"]
                assert reference.startswith("#/")
                target = schema
                for part in reference[2:].split("/"):
                    target = target[part.replace("~1", "/").replace("~0", "~")]
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(schema)


def test_catalog_handoffs_and_database_ownership_are_resolvable(documents):
    catalog = documents["contracts/catalog.json"]
    assert {entry["id"] for entry in catalog["contracts"]} == {
        *(f"C{i:02}" for i in range(1, 14)),
        "X01",
        "X02",
    }
    database = documents["contracts/database_catalog.json"]
    tables = {table["name"]: table for table in database["tables"]}
    assert len(tables) == 56
    for table in (*TABLES, *QA_TABLES):
        entry = tables[f"{table.schema}.{table.name}"]
        assert entry["columns"] == [
            {"name": name, "sql_type": kind} for name, kind in table.columns
        ]
        assert entry["primary_key"] == [table.primary_key]
    for entry in catalog["contracts"]:
        assert entry["tables"] and entry["semantic_rules"]
        for name in entry["tables"]:
            assert name in tables
    for fk in database["foreign_keys"]:
        assert fk["column"] in {c["name"] for c in tables[fk["table"]]["columns"]}
        destination = fk["references"]
        assert destination["column"] in {c["name"] for c in tables[destination["table"]]["columns"]}
    for handoff in catalog["handoffs"]:
        if "input_schema" not in handoff:
            continue
        name, pointer = handoff["input_schema"].split("#")
        target = json.loads((DOCS / "contracts" / name).read_text())
        for part in pointer.lstrip("/").split("/"):
            target = target[part]


def test_ui_design_distinguishes_live_routes_from_future_contracts(documents):
    runtime = create_app(services=Services(knowledge=None, assessments=None)).openapi()["paths"]
    design = documents["openapi.design.json"]
    assert design["x-contract-status"] == "PROPOSED"
    assert "/api/v1/pipeline/steps-5-7" not in design["paths"]
    assert "/api/v1/reasoning" not in design["paths"]
    ids = []
    for path, methods in design["paths"].items():
        for method, operation in methods.items():
            ids.append(operation["operationId"])
            implemented = operation["x-implementation-status"] == "IMPLEMENTED"
            assert implemented == (path in runtime and method in runtime[path])
            if not implemented:
                assert operation["x-contract-status"] == "PROPOSED"
                assert operation["security"] == [{"BearerAuth": []}]
    assert len(ids) == len(set(ids))
    app = create_app(services=Services(knowledge=None, assessments=None))
    assert app.openapi()["paths"] == runtime  # Publishing docs must not register proposed handlers.


def test_http_request_examples_validate_against_documented_schema(documents):
    document = documents["openapi.design.json"]
    for methods in document["paths"].values():
        for operation in methods.values():
            for media in operation.get("requestBody", {}).get("content", {}).values():
                if "example" in media:
                    validator = Draft202012Validator(
                        {**media["schema"], "components": document["components"]},
                        format_checker=FormatChecker(),
                    )
                    validator.validate(media["example"])


def test_frontend_cannot_supply_server_owned_actor_or_deployment_outputs(documents):
    document = documents["openapi.design.json"]

    def body_schema(path):
        body = document["paths"][path]["post"]["requestBody"]["content"]["application/json"]
        return {**body["schema"], "components": document["components"]}

    case = {"hop_dong_id": "HD_EXAMPLE", "ngay_danh_gia": "2026-10-15"}
    validator = Draft202012Validator(body_schema("/api/v1/cases"), format_checker=FormatChecker())
    validator.validate(case)
    for key in ["actor_id", "tenant_id", "knowledge_snapshot_sha256", "report_json"]:
        with pytest.raises(ValidationError):
            validator.validate({**case, key: "client-cannot-set-this"})
    review_schema = body_schema("/api/v1/cases/{ca_id}/runs/{run_id}/reviews")
    review = {
        "target": {"doi_tuong_loai": "ket_qua_tieu_chi", "doi_tuong_id": "KQ_EXAMPLE"},
        "action": "COMMENT",
        "after": {},
        "reason": "Check appendix",
        "expected_target_sha256": "a" * 64,
    }
    validator = Draft202012Validator(review_schema)
    validator.validate(review)
    for key in ["actor_id", "before", "reviewed_at", "phien_ban_id"]:
        with pytest.raises(ValidationError):
            validator.validate({**review, key: "client-cannot-set-this"})


def test_json_schema_does_not_replace_cross_field_python_validation():
    candidate = {
        "yeu_cau_ca_id": "YCCA_EXAMPLE",
        "ca_id": "CA_EXAMPLE",
        "requirement_id": "REQ_EXAMPLE",
        "scope_status": "MATCH",
        "version_status": "RESOLVED",
        "applicability_status": "CONFIRMED",
        "phien_ban_id": "DEPLOY_EXAMPLE",
        "requirement_version_id": None,
        "moc_ap_dung": None,
    }
    # Structural schema accepts nulls; Pydantic's semantic validator requires a date/version here.
    Draft202012Validator(ApplicableRequirement.model_json_schema()).validate(candidate)
    with pytest.raises(ValueError, match="Confirmed requirement needs"):
        ApplicableRequirement.model_validate(candidate)
