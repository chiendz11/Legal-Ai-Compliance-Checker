"""Cross-boundary regressions: documentation, provenance and numeric vocabulary."""

import ast
import json
import re
from collections import Counter
from urllib.parse import unquote

import pytest
from legal_checker.core.config import PROJECT_ROOT
from legal_checker.shared.contracts.citation import CitationProvenance
from legal_checker.shared.contracts.document_intelligence import ProfileFields

DOCS = PROJECT_ROOT / "docs"


def _without_fences(text):
    return re.sub(r"^```[^\n]*\n.*?^```[^\n]*$", "", text, flags=re.M | re.S)


def _anchors(text):
    anchors = set(re.findall(r'<a\s+id="([^"]+)"', text))
    counts = Counter()
    for line in _without_fences(text).splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if not match:
            continue
        title = re.sub(r"[^\w\- ]", "", match[1].lower()).replace(" ", "-")
        n = counts[title]
        counts[title] += 1
        anchors.add(title + (f"-{n}" if n else ""))
    return anchors


def test_documentation_links_and_fragments_resolve():
    broken = []
    for source in DOCS.rglob("*.md"):
        text = _without_fences(source.read_text())
        for match in re.finditer(r"\[[^\]]*\]\(([^\s)]+)\)", text):
            destination = unquote(match[1].strip("<>"))
            if destination.startswith(("http:", "https:", "mailto:", "data:")):
                continue
            path, _, fragment = destination.partition("#")
            target = (source.parent / path).resolve() if path else source
            if not target.exists() or (
                fragment and target.suffix == ".md" and fragment not in _anchors(target.read_text())
            ):
                broken.append(f"{source.relative_to(DOCS)}: {destination}")
    assert not broken, "Broken documentation links:\n" + "\n".join(broken)


def test_live_c09_provenance_has_consistent_context_and_snapshot():
    context = {
        "ca_id": "CA",
        "run_id": "RUN",
        "trace_id": "TRACE",
        "phien_ban_id": "DEPLOY",
        "rule_version": "RULE",
        "legal_knowledge_version": "LEGAL",
        "knowledge_snapshot_sha256": "a" * 64,
    }
    with pytest.raises(ValueError):
        CitationProvenance.model_validate({})
    with pytest.raises(ValueError):
        CitationProvenance(context=context, hop_dong_id="HD", knowledge_snapshot_sha256="b" * 64)
    actual = CitationProvenance(
        context=context, hop_dong_id="HD", knowledge_snapshot_sha256="a" * 64
    )
    assert actual.context.run_id == "RUN"
    assert (
        json.loads((DOCS / "contracts/citation_provenance.schema.json").read_text())
        == CitationProvenance.model_json_schema()
    )


def test_dictionary_covers_profile_and_numeric_literal_keys():
    dictionary = json.loads((DOCS / "contracts/data_dictionary.json").read_text())
    assert set(dictionary["profile_fields"]) == set(ProfileFields.model_fields)
    source = PROJECT_ROOT / "backend/src/legal_checker/modules/compliance/numeric_rules.py"
    keys = set()
    for node in ast.walk(ast.parse(source.read_text())):
        if not isinstance(node, ast.Call):
            continue
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "facts"
            and node.func.attr == "get"
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            keys.add(node.args[0].value)
        if (
            isinstance(node.func, ast.Name)
            and node.func.id in {"_equals", "_boolean"}
            and len(node.args) > 1
            and isinstance(node.args[1], ast.Constant)
        ):
            keys.add(node.args[1].value)
    assert keys <= set(dictionary["numeric_fact_fields"])


def test_frontend_understands_all_verification_action_codes():
    from legal_checker.modules.recommendations.generator import VERIFICATION_ACTIONS

    policy = json.loads((DOCS / "contracts/integration_policy.json").read_text())
    source = (
        PROJECT_ROOT
        / "frontend/src/features/assessments/recommendations/RecommendationsSection.tsx"
    )
    definition = re.search(
        r"VERIFICATION_ACTIONS\s*=\s*new Set\(\[(.*?)\]\)", source.read_text(), re.S
    )
    assert definition
    assert set(re.findall(r'"([A-Z_]+)"', definition[1])) == set(policy["verification_actions"])
    assert VERIFICATION_ACTIONS == set(policy["verification_actions"])


def test_review_policy_is_versioned_in_shared_contracts():
    from legal_checker.shared.contracts.review import REVIEW_POLICY

    policy = json.loads((DOCS / "contracts/integration_policy.json").read_text())
    assert REVIEW_POLICY == policy["review_policy"]


def test_unknown_findings_require_decisive_review_before_publication():
    from types import SimpleNamespace

    from legal_checker.modules.reviews.service import TargetState, publication_blockers

    target = TargetState("ket_qua_tuan_thu", "INSUFFICIENT_1", {"status": "INSUFFICIENT"})
    states = {(target.kind, target.target_id): target}
    assert publication_blockers(states)[0]["reason"] == "UNREVIEWED_FINDING"
    target.reviews.append(SimpleNamespace(action="COMMENT"))
    assert publication_blockers(states)
    target.reviews.append(SimpleNamespace(action="CONFIRM"))
    assert not publication_blockers(states)  # Accept limitations; does not change machine status.
    assert target.machine["status"] == "INSUFFICIENT"


def test_verification_dictionary_covers_semantic_controls_and_types():
    from legal_checker.modules.compliance.criterion_reasoner import SUPPORTED_TYPES
    from legal_checker.modules.compliance.verification import CriterionVerification
    from legal_checker.shared.contracts.document_intelligence import DocumentReadCoverage

    dictionary = json.loads((DOCS / "contracts/data_dictionary.json").read_text())
    assert set(dictionary["criterion_type_recipes"]) == SUPPORTED_TYPES
    source = PROJECT_ROOT / "backend/src/legal_checker/modules/compliance/criterion_reasoner.py"
    keys = {
        node.args[0].value
        for node in ast.walk(ast.parse(source.read_text()))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and isinstance(node.func.value, ast.Attribute)
        and node.func.value.attr == "facts"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    }
    assert keys <= set(dictionary["verification_control_fields"])
    assert (
        json.loads((DOCS / "contracts/criterion_verification.schema.json").read_text())
        == CriterionVerification.model_json_schema()
    )
    assert (
        json.loads((DOCS / "contracts/document_read_coverage.schema.json").read_text())
        == DocumentReadCoverage.model_json_schema()
    )


def test_handoff_acceptance_references_real_tests_and_all_five_owners():
    matrix = json.loads((DOCS / "contracts/handoff_acceptance.json").read_text())
    assert matrix["kind"] == "NORMATIVE_DELIVERY_REQUIREMENTS_NOT_RUN_RESULTS"
    owners = set(matrix["owners"])
    assert owners == {f"P{i}" for i in range(1, 6)}
    scenarios = matrix["scenarios"]
    assert len({row["id"] for row in scenarios}) == len(scenarios)
    for row in scenarios:
        assert row["owners"] and set(row["owners"]) <= owners
        assert row["expected"] and row["qualification"] == "REQUIREMENT_NOT_EXECUTION_RESULT"
        if row["level"] == "qualification":
            assert row["required_artifact"]
        else:
            assert row["test_nodes"]
        for node in row["test_nodes"]:
            file_name, test_name = node.split("::")
            source = PROJECT_ROOT / file_name
            functions = {
                n.name
                for n in ast.walk(ast.parse(source.read_text()))
                if isinstance(n, ast.FunctionDef)
            }
            assert test_name in functions, node


@pytest.mark.parametrize("pages", [[0], [2], [1, 1]])
def test_read_coverage_rejects_invalid_page_identity(pages):
    from legal_checker.shared.contracts.document_intelligence import DocumentReadCoverage

    with pytest.raises(ValueError):
        DocumentReadCoverage(
            hop_dong_id="HD",
            source_sha256="a" * 64,
            extraction_version="V1",
            page_count=1,
            unreadable_pages=pages,
        )


def test_read_coverage_does_not_claim_semantic_absence_or_related_document_completeness():
    from legal_checker.shared.contracts.document_intelligence import DocumentReadCoverage

    coverage = DocumentReadCoverage(
        hop_dong_id="HD",
        source_sha256="a" * 64,
        extraction_version="V1",
        page_count=2,
        unreadable_pages=[2],
    )
    assert not coverage.all_pages_have_text
    assert "all_related_documents_received" not in type(coverage).model_fields
    with pytest.raises(ValueError):
        DocumentReadCoverage(**coverage.model_dump(), absence_verified=True)


def test_source_url_only_is_valid_in_explicit_reference_mode(tmp_path):
    from legal_checker.shared.contracts.assessment import SourceDocument
    from legal_checker.workflows.integrated import IntegratedModulesSource

    source = SourceDocument(
        tep_id="PDF",
        url_nguon="https://example.org/source.pdf",
        mime_type="application/pdf",
        sha256="a" * 64,
    )
    implementation = IntegratedModulesSource(
        "unused", None, storage=object(), source_cache_dir=tmp_path, allow_reference_documents=True
    )
    assert not implementation.has_local_bytes(source)
