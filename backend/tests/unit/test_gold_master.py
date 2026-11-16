"""Admission boundaries for a single multi-layer Gold answer registry."""

import sqlite3

import pytest
from devtools.gold_answers import GoldError, canonical_sha
from devtools.gold_master import SCHEMA, check_identity, check_literal, insert_answer


def database():
    db = sqlite3.connect(":memory:")
    db.executescript(SCHEMA)
    db.execute(
        "INSERT INTO cases VALUES(?,?,?,?,?,?,?,?,?)",
        (
            "C1",
            "H1",
            "G1",
            "DEV",
            "a" * 64,
            1,
            "b" * 64,
            "c" * 64,
            "PENDING_ADJUDICATION",
        ),
    )
    return db


def source_case():
    return {
        "case_id": "C1",
        "source": {
            "source_sha256": "a" * 64,
            "blocks": [{"id": "B1", "page": 1, "text": "Tên: A"}],
        },
    }


def fact():
    return {
        "field": "name",
        "status": "KNOWN",
        "value": "A",
        "evidence": [
            {
                "source_sha256": "a" * 64,
                "ref": "B1",
                "page": 1,
                "start": 0,
                "end": 6,
                "quote": "Tên: A",
            }
        ],
    }


def test_same_question_cannot_silently_get_two_answers():
    db = database()
    kwargs = dict(case=source_case(), layer="FACTS", scope="FULL_DOCUMENT", origin={})
    insert_answer(db, row=fact(), **kwargs)
    changed = {**fact(), "value": "B"}
    with pytest.raises(sqlite3.IntegrityError):
        insert_answer(db, row=changed, **kwargs)
    assert db.execute("SELECT count(*) FROM answers").fetchone()[0] == 1


def test_appendix_answer_does_not_complete_full_document_case():
    db = database()
    insert_answer(
        db,
        case=source_case(),
        layer="APPENDIX_LITERALS",
        scope="SYNTHETIC_TRANSACTION_APPENDIX_ONLY",
        row=fact(),
        origin={},
    )
    assert db.execute("SELECT full_case_status FROM cases").fetchone()[0] == "PENDING_ADJUDICATION"
    assert (
        db.execute("SELECT count(*) FROM benchmark_answers WHERE layer='FACTS'").fetchone()[0] == 0
    )


def test_appendix_omission_preserves_narrow_scope():
    row = dict(
        scope="SYNTHETIC_TRANSACTION_APPENDIX_ONLY",
        whole_document_absence_claim=False,
        annotation_quality="GOLD",
        status="NOT_PROVIDED_IN_AUTHORED_APPENDIX",
    )
    check_literal(row)
    with pytest.raises(GoldError, match="whole-document"):
        check_literal({**row, "whole_document_absence_claim": True})
    with pytest.raises(GoldError, match="status"):
        check_literal({**row, "status": "MISSING"})


def test_wrong_source_span_is_rejected_before_insertion():
    db = database()
    row = fact()
    row["evidence"][0]["quote"] = "Tên: B"
    with pytest.raises(GoldError, match="witness mismatch"):
        insert_answer(db, case=source_case(), layer="FACTS", scope="FULL", row=row, origin={})
    assert db.execute("SELECT count(*) FROM answers").fetchone()[0] == 0


def test_pending_annotation_never_becomes_correct_legal_unknown():
    db = database()
    insert_answer(
        db,
        case=source_case(),
        layer="FACTS",
        scope="FULL",
        row={"field": "x", "status": "UNKNOWN"},
        origin={},
        adjudicated=False,
    )
    assert db.execute("SELECT count(*) FROM benchmark_answers").fetchone()[0] == 0
    assert (
        db.execute("SELECT annotation_status FROM answers").fetchone()[0] == "PENDING_ADJUDICATION"
    )


def test_catalog_identity_is_not_citation_validity():
    doc = {"van_ban_id": "LAW1", "so_hieu": "1/2020/QH14"}
    kb = {"tables": {"van_ban_phap_ly": [doc]}}
    row = dict(
        identity="MATCH",
        document_id="LAW1",
        number="1/2020/QH14",
        catalog_record_sha256=canonical_sha(doc),
        knowledge_snapshot_sha256=canonical_sha(kb),
        temporal_and_domain_gold=False,
        overall_c09_status="UNJUDGED",
        annotation_quality="GOLD",
    )
    assert check_identity(row, kb)
    with pytest.raises(GoldError, match="validity"):
        check_identity({**row, "overall_c09_status": "VALID"}, kb)
    with pytest.raises(GoldError, match="uniquely"):
        check_identity({**row, "number": "2/2020/QH14"}, kb)


def test_declared_number_alias_keeps_original_mention_distinct_from_validity():
    doc = {"van_ban_id": "LAW1", "so_hieu": "99/2015/NĐ-CP"}
    kb = {"tables": {"van_ban_phap_ly": [doc]}}
    row = dict(
        identity="MATCH",
        document_id="LAW1",
        number="99/2015/ND-CP",
        catalog_record_sha256=canonical_sha(doc),
        knowledge_snapshot_sha256=canonical_sha(kb),
        temporal_and_domain_gold=False,
        overall_c09_status="UNJUDGED",
        annotation_quality="GOLD",
    )
    assert check_identity(row, kb)
    assert row["number"] == "99/2015/ND-CP"


def test_silver_literal_or_identity_cannot_be_promoted_by_import():
    with pytest.raises(GoldError, match="Unadjudicated"):
        check_literal(
            dict(
                scope="SYNTHETIC_TRANSACTION_APPENDIX_ONLY",
                whole_document_absence_claim=False,
                annotation_quality="SILVER",
            )
        )


def test_absent_pinned_catalog_entry_is_a_bounded_answer_not_a_legal_invalidity():
    kb = {"tables": {"van_ban_phap_ly": [{"van_ban_id": "LAW1", "so_hieu": "1/2020/QH14"}]}}
    row = dict(
        identity="NO_MATCH_IN_PINNED_CATALOG",
        document_id=None,
        catalog_record_sha256=None,
        number="2/2020/QH14",
        knowledge_snapshot_sha256=canonical_sha(kb),
        catalog_candidate_ids=[],
        exhaustive_catalog_membership_check=True,
        real_world_existence_claim=False,
        reason="No exact number in the complete pinned catalog; real-world identity unjudged.",
        temporal_and_domain_gold=False,
        overall_c09_status="UNJUDGED",
        annotation_quality="GOLD",
    )
    assert check_identity(row, kb)
    with pytest.raises(GoldError, match="empty catalog match"):
        check_identity({**row, "number": "1/2020/QH14"}, kb)
    with pytest.raises(GoldError, match="empty catalog match"):
        check_identity({**row, "real_world_existence_claim": True}, kb)
    with pytest.raises(GoldError, match="validity"):
        check_identity({**row, "overall_c09_status": "INVALID"}, kb)
    with pytest.raises(GoldError, match="empty catalog match"):
        check_identity({**row, "exhaustive_catalog_membership_check": False}, kb)


def test_test_answers_are_not_in_team_view():
    db = database()
    db.execute("UPDATE cases SET split='TEST'")
    insert_answer(db, case=source_case(), layer="FACTS", scope="FULL", row=fact(), origin={})
    assert db.execute("SELECT count(*) FROM dev_validation_answers").fetchone()[0] == 0
    assert db.execute("SELECT count(*) FROM test_answers_evaluator_only").fetchone()[0] == 1


def test_excluded_disposition_does_not_inflate_legal_unknown_accuracy():
    db = database()
    for ident, disposition in (("TC1", "ASSESSED"), ("TC2", "OUTSIDE_REVIEW_SCOPE")):
        insert_answer(
            db,
            case=source_case(),
            layer="CRITERIA",
            scope="FULL",
            row={"criterion_id": ident, "disposition": disposition, "finding": "UNKNOWN"},
            origin={},
        )
    assert db.execute("SELECT count(*) FROM criterion_finding_answers").fetchone()[0] == 1
