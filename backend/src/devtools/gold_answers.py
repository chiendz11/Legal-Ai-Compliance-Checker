"""Source-grounded project Gold contracts, independent of business engines.

Gold authoring must read original PDFs and the pinned knowledge, not predictions
from the pipeline being scored. AI adjudication never asserts human legal signoff.
"""

import hashlib
import json
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GoldError(ValueError):
    pass


class GoldModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class GoldSpan(GoldModel):
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    ref: str
    page: int = Field(ge=1)
    start: int = Field(ge=0)
    end: int = Field(ge=1)
    quote: str = Field(min_length=1)

    @model_validator(mode="after")
    def ordered(self):
        if self.end <= self.start:
            raise ValueError("Gold evidence needs a nonempty source interval")
        return self


class GoldFact(GoldModel):
    field: str
    status: Literal["KNOWN", "UNKNOWN", "CONFLICT", "NOT_APPLICABLE"]
    value: Any = None
    alternatives: list[Any] = Field(default_factory=list)
    evidence: list[GoldSpan] = Field(default_factory=list)
    reason: str = Field(min_length=1)
    annotation_quality: Literal["GOLD", "PENDING_ADJUDICATION"] | None = None

    @model_validator(mode="after")
    def supported(self):
        if self.status == "KNOWN" and (self.value is None or not self.evidence):
            raise ValueError("Known Gold fact requires a value and source witness")
        if self.status != "KNOWN" and self.value is not None:
            raise ValueError("Unknown/conflicting Gold fact cannot pick one value")
        if self.status == "CONFLICT":
            distinct = {
                json.dumps(v, sort_keys=True, ensure_ascii=False) for v in self.alternatives
            }
            if len(distinct) < 2 or len(self.evidence) < 2:
                raise ValueError("Conflict needs distinct alternatives and source evidence")
        return self


class GoldCriterion(GoldModel):
    criterion_id: str
    requirement_id: str
    requirement_version_id: str
    finding: Literal["SATISFIED", "VIOLATED", "MISSING", "UNKNOWN"]
    disposition: Literal[
        "ASSESSED", "OUTSIDE_REVIEW_SCOPE", "NOT_TRIGGERED", "SCOPE_UNRESOLVED"
    ] = "ASSESSED"
    reason_code: str
    reason: str = Field(min_length=1)
    legal_article_ids: list[str] = Field(min_length=1)
    evidence: list[GoldSpan] = Field(default_factory=list)
    negative_source_review: dict[str, Any] | None = None
    annotation_quality: Literal["GOLD", "PENDING_ADJUDICATION"]
    adjudication_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def witness_or_negative_review(self):
        if self.disposition != "ASSESSED" and self.finding != "UNKNOWN":
            raise ValueError("Excluded/unresolved target preserves UNKNOWN in C07 projection")
        if self.annotation_quality == "GOLD":
            if not self.adjudication_ids:
                raise ValueError("Gold decision needs a completed adjudication record")
            if self.finding == "VIOLATED" and not self.evidence:
                raise ValueError("Violation needs a positive source witness")
            if self.finding == "MISSING" and not self.negative_source_review:
                raise ValueError("Missing needs a scoped, complete negative source review")
            if self.finding == "SATISFIED" and not (self.evidence or self.negative_source_review):
                raise ValueError("Satisfied needs evidence, a default rule, or absence review")
            if self.reason_code in {"MODEL_UNCERTAIN", "ADJUDICATION_FAILED", "NOT_IMPLEMENTED"}:
                raise ValueError("Annotation uncertainty cannot become a Gold case label")
        return self


class GoldCase(GoldModel):
    """Gold for the declared targets, never an assertion of whole-case coverage."""

    gold_version: str
    coverage: Literal["DECLARED_TARGETS_ONLY"] = "DECLARED_TARGETS_ONLY"
    case_id: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    knowledge_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    review_mode: Literal["DRAFT_REVIEW"]
    scope: Literal["PROVIDED_PDF_AND_PINNED_KNOWLEDGE"]
    facts: list[GoldFact]
    requirements: list[dict[str, Any]]
    criteria: list[GoldCriterion]
    citations: list[dict[str, Any]]
    requirements_aggregated: list[dict[str, Any]]
    adjudicator_type: Literal["AI_SOURCE_ADJUDICATED"]
    human_legal_signoff: Literal[False] = False
    production_outputs_used: Literal[False] = False
    status: Literal["GOLD", "PENDING_ADJUDICATION"]
    annotation_quality: Literal["GOLD", "PENDING_ADJUDICATION"] | None = None
    layer_receipts: dict[str, Any] | None = None
    pending_adjudications: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def no_partial_global_claim(self):
        for rows, key in [(self.facts, "field"), (self.criteria, "criterion_id")]:
            ids = [getattr(r, key) for r in rows]
            if len(ids) != len(set(ids)):
                raise ValueError("Duplicate Gold target identity")
        if self.status == "GOLD" and any(c.annotation_quality != "GOLD" for c in self.criteria):
            raise ValueError("A partially adjudicated case cannot claim full Gold")
        return self


def canonical_sha(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def _artifact_spans_match(value: Any, source: dict) -> bool:
    """Verify authored layer witnesses too, including judged retrieval controls."""
    blocks = {b["id"]: b for b in source["blocks"]}

    def visit(item):
        if isinstance(item, dict):
            if {"ref", "page", "start", "end", "quote"} <= item.keys():
                block = blocks.get(item["ref"])
                if (
                    not block
                    or item.get("source_sha256") != source["source_sha256"]
                    or item["page"] != block["page"]
                    or not isinstance(item["start"], int)
                    or not isinstance(item["end"], int)
                    or not 0 <= item["start"] < item["end"] <= len(block["text"])
                    or block["text"][item["start"] : item["end"]] != item["quote"]
                ):
                    return False
            return all(visit(v) for v in item.values())
        if isinstance(item, list):
            return all(visit(v) for v in item)
        return True

    return visit(value)


def validate_gold_case(answer: GoldCase, source: dict, snapshot: dict) -> dict:
    """Check exact provenance and target ownership, without generating any verdict."""
    if answer.case_id != source["case_id"] or answer.source_sha256 != source["source_sha256"]:
        raise GoldError("Gold belongs to another case/source")
    if canonical_sha(snapshot) != answer.knowledge_snapshot_sha256:
        raise GoldError("Gold belongs to another knowledge revision")
    tables = snapshot["tables"]
    criteria = {r["tieu_chi_id"]: r for r in tables["tieu_chi_danh_gia"]}
    versions = {r["requirement_version_id"]: r for r in tables["phien_ban_yeu_cau"]}
    articles = {r["dieu_khoan_id"] for r in tables["dieu_khoan_phap_ly"]}
    blocks = {r["id"]: r for r in source["blocks"]}
    spans = [e for f in answer.facts for e in f.evidence]
    spans.extend(e for c in answer.criteria for e in c.evidence)
    spans.extend(
        GoldSpan.model_validate(e)
        for citation in answer.citations
        for key in ("evidence", "context_evidence")
        for e in citation.get(key, [])
    )
    for span in spans:
        block = blocks.get(span.ref)
        if (
            span.source_sha256 != answer.source_sha256
            or not block
            or span.page != block["page"]
            or not 0 <= span.start < span.end <= len(block["text"])
            or block["text"][span.start : span.end] != span.quote
        ):
            raise GoldError("Gold quote differs from its source")
    for label in answer.criteria:
        criterion = criteria.get(label.criterion_id)
        version = versions.get(label.requirement_version_id)
        if (
            not criterion
            or not version
            or criterion["requirement_version_id"] != label.requirement_version_id
            or version["requirement_id"] != label.requirement_id
            or not set(label.legal_article_ids) <= articles
            or criterion.get("source_dieu_khoan_id") not in label.legal_article_ids
        ):
            raise GoldError("Gold criterion/version/legal basis ownership mismatch")
        if label.negative_source_review:
            receipt = label.negative_source_review
            if (
                receipt.get("source_sha256") != answer.source_sha256
                or set(receipt.get("reviewed_pages", [])) != set(range(1, source["page_count"] + 1))
                or source.get("text_sparse_pages")
                or receipt.get("scope") != "PROVIDED_PDF_ONLY"
            ):
                raise GoldError("Negative Gold finding lacks complete scoped source review")
    return {"status": "PASS", "case_id": answer.case_id, "spans_checked": len(spans)}


def validate_literal_gold(answer: dict, source: dict) -> dict:
    """Validate a narrow authored-appendix task, including scoped negative evidence.

    This task cannot establish that a fact is absent from the original contract,
    that an act occurred, or that a cited law is applicable or valid.
    """
    if (
        answer.get("case_id") != source["case_id"]
        or answer.get("source_sha256") != source["source_sha256"]
        or answer.get("scope") != "APPENDIX_LITERALS_AND_NUMBERED_MENTIONS"
        or answer.get("full_document_profile_gold") is not False
        or answer.get("full_document_legal_gold") is not False
        or answer.get("production_outputs_used") is not False
        or answer.get("human_legal_signoff") is not False
    ):
        raise GoldError("Scoped literal Gold cannot claim whole-document or human review")
    blocks = source["blocks"]
    by_id = {b["id"]: b for b in blocks}
    start = next(
        (
            i
            for i, b in enumerate(blocks)
            if " ".join(b["text"].split()) == "PHỤ LỤC 01 - THÔNG TIN GIAO DỊCH"
        ),
        None,
    )
    if start is None:
        raise GoldError("Authored appendix boundary is missing")
    end = next(
        (i for i in range(start + 1, len(blocks)) if "PHỤ LỤC 02" in blocks[i]["text"]),
        len(blocks),
    )
    selected = blocks[start:end]
    fields = answer.get("fields", [])
    identities = [f["field"] for f in fields]
    if not fields or len(identities) != len(set(identities)):
        raise GoldError("Literal Gold field set is empty or duplicated")

    def check_span(raw):
        span = GoldSpan.model_validate(raw)
        block = by_id.get(span.ref)
        if (
            span.source_sha256 != source["source_sha256"]
            or not block
            or span.page != block["page"]
            or not 0 <= span.start < span.end <= len(block["text"])
            or block["text"][span.start : span.end] != span.quote
        ):
            raise GoldError("Literal witness differs from the locked source")
        return span

    spans_checked = 0
    for fact in fields:
        if (
            fact.get("scope") != "SYNTHETIC_TRANSACTION_APPENDIX_ONLY"
            or fact.get("whole_document_absence_claim") is not False
            or fact.get("annotation_quality") != "GOLD"
        ):
            raise GoldError("Appendix label cannot become a global profile finding")
        status = fact["status"]
        evidence = [check_span(e) for e in fact.get("evidence", [])]
        spans_checked += len(evidence)
        if any(e.ref not in {b["id"] for b in selected} for e in evidence):
            raise GoldError("Appendix witness belongs to the contract body")
        if status == "KNOWN":
            if fact.get("value") is None or not evidence:
                raise GoldError("Known literal needs a source value and witness")
        elif status == "CONFLICT":
            alternatives = {canonical_sha(v) for v in fact.get("alternatives", [])}
            if fact.get("value") is not None or len(alternatives) < 2 or len(evidence) < 2:
                raise GoldError("Conflicting literal cannot select one convenient value")
        elif status == "NOT_PROVIDED_IN_AUTHORED_APPENDIX":
            if fact.get("value") is not None:
                raise GoldError("Absent appendix field cannot select a value")
            if evidence and not all(
                (fact["source_label"] + ": Chưa được cung cấp trong bộ hồ sơ dự thảo.") in e.quote
                for e in evidence
            ):
                raise GoldError("A populated field cannot be called absent")
            if not evidence:
                receipt = fact.get("negative_source_review", {})
                if (
                    receipt.get("source_sha256") != source["source_sha256"]
                    or receipt.get("scope") != "AUTHORED_APPENDIX_ONLY"
                    or receipt.get("reviewed_block_ids") != [b["id"] for b in selected]
                    or receipt.get("reviewed_pages") != sorted({b["page"] for b in selected})
                    or receipt.get("searched_label") != fact.get("source_label")
                    or set(source.get("text_sparse_pages", [])) & {b["page"] for b in selected}
                    or any(b["text"].startswith(fact["source_label"] + ": ") for b in selected)
                ):
                    raise GoldError("Appendix absence needs complete scoped source review")
        else:
            raise GoldError("Unsupported literal annotation state")
    for mention in answer.get("numbered_mentions", []):
        if (
            mention.get("scope") != "NUMBERED_MENTION_ONLY"
            or mention.get("identity_or_validity_claim") is not False
        ):
            raise GoldError("A numbered mention does not prove citation validity")
        span = check_span(mention["evidence"])
        if span.quote != mention["number"]:
            raise GoldError("Numbered mention differs from its witness")
        spans_checked += 1
    return {"status": "PASS", "case_id": answer["case_id"], "spans_checked": spans_checked}


def check_full_gold_coverage(
    sources: dict[str, dict],
    cases: dict[str, dict],
    snapshot: dict,
    *,
    artifacts: dict[str, dict] | None = None,
) -> dict:
    """Gate a full release from actual layer coverage, rather than a manual flag.

    This is a necessary structural gate. Source/legal adjudication receipts are
    still required; passing it is not a professional legal opinion.
    """
    errors = []
    tables = snapshot["tables"]
    expected_requirements = {r["requirement_id"] for r in tables["yeu_cau_phap_ly"]}
    versions = {r["requirement_version_id"]: r for r in tables["phien_ban_yeu_cau"]}
    criteria = {r["tieu_chi_id"]: r for r in tables["tieu_chi_danh_gia"]}
    snapshot_sha = canonical_sha(snapshot)
    cutoff = date(2024, 8, 1)
    for cid in sorted(set(cases) - set(sources)):
        errors.append({"case_id": cid, "reason": "UNREGISTERED_SOURCE"})
    for cid, source in sources.items():
        answer = cases.get(cid)
        if not answer:
            errors.append({"case_id": cid, "reason": "MISSING_CASE_GOLD"})
            continue

        def fail(reason, case_id=cid):
            errors.append({"case_id": case_id, "reason": reason})

        if (
            answer.get("annotation_quality") != "GOLD"
            or answer.get("source_sha256") != source["source_sha256"]
            or answer.get("knowledge_snapshot_sha256") != snapshot_sha
            or answer.get("human_legal_signoff") is not False
            or answer.get("production_outputs_used") is not False
        ):
            fail("GOLD_PROVENANCE_OR_STATUS_INVALID")
        req_rows = answer.get("requirements", [])
        req_ids = [r["requirement_id"] for r in req_rows]
        if set(req_ids) != expected_requirements or len(req_ids) != len(set(req_ids)):
            fail("INCOMPLETE_OR_DUPLICATE_C05")
        facts = {f["field"]: f for f in answer.get("facts", [])}
        expected_criteria = set()
        for req in req_rows:
            if (
                req.get("scope_status") not in {"MATCH", "NO_MATCH", "UNKNOWN"}
                or req.get("version_status") not in {"RESOLVED", "UNKNOWN"}
                or req.get("applicability_status") not in {"CONFIRMED", "NOT_APPLICABLE", "UNKNOWN"}
            ):
                fail("C05_INVALID_STATUS_ENUM:" + req["requirement_id"])
            if req.get("applicability_status") == "CONFIRMED" and (
                req.get("scope_status") != "MATCH"
                or req.get("version_status") != "RESOLVED"
                or not req.get("requirement_version_id")
                or not req.get("date_provenance")
            ):
                fail("C05_CONFIRMATION_WITHOUT_SCOPE_DATE_VERSION_PROVENANCE")
            vid = req.get("requirement_version_id")
            if not vid or req["applicability_status"] == "NOT_APPLICABLE":
                continue
            version = versions.get(vid)
            if not version or version["requirement_id"] != req["requirement_id"]:
                fail("C05_VERSION_OWNERSHIP_MISMATCH")
                continue
            expected_criteria.update(
                ident for ident, c in criteria.items() if c["requirement_version_id"] == vid
            )
            when = req.get("relevant_date") or req.get("moc_ap_dung")
            if not when or date.fromisoformat(str(when)) < cutoff:
                continue
            policy = version.get("quy_tac_chuyen_tiep", {})
            if isinstance(policy, str):
                policy = json.loads(policy)
            transition = policy.get("transition")
            future = facts.get("tinh_trang_tai_san", {}).get("value")
            social = facts.get("la_nha_o_xa_hoi", {}).get("value")
            field = None
            if transition == "KDBDS_83" and future == "HINH_THANH_TRONG_TUONG_LAI":
                field = "transition.future_sale_eligible_before_20240801"
            elif transition == "HOUSING_198" and social is True:
                field = "transition.housing_social_process_before_20240801"
            if field:
                fact = facts.get(field)
                if not fact or fact.get("annotation_quality") != "GOLD":
                    fail("TRANSITION_FACT_NOT_ADJUDICATED:" + field)
                elif fact.get("status") != "KNOWN" and req["applicability_status"] == "CONFIRMED":
                    fail("UNRESOLVED_TRANSITION_CANNOT_CONFIRM_C05")
                elif (
                    fact.get("value") is True
                    and policy.get("grandfathering") == "CASE_REVIEW"
                    and req["applicability_status"] == "CONFIRMED"
                    and not req.get("legal_transition_adjudication_id")
                ):
                    fail("CASE_SPECIFIC_TRANSITION_REVIEW_MISSING")
        judged = answer.get("criteria", [])
        judged_ids = [r["criterion_id"] for r in judged]
        if set(judged_ids) != expected_criteria or len(judged_ids) != len(set(judged_ids)):
            fail("INCOMPLETE_OR_DUPLICATE_C07")
        if any(
            r.get("annotation_quality") != "GOLD" or not r.get("adjudication_ids") for r in judged
        ):
            fail("CRITERION_ADJUDICATION_MISSING")
        req_by_id = {r["requirement_id"]: r for r in req_rows}
        for row in judged:
            req = req_by_id.get(row.get("requirement_id"), {})
            criterion = criteria.get(row.get("criterion_id"), {})
            if (
                row.get("finding") == "MISSING"
                and criterion.get("pham_vi_kiem_tra") == "CONDITIONAL_OR_EXTERNAL_FACTS"
                and criterion.get("noi_dung_bat_buoc_trong_hd") is False
                and str(criterion.get("missing_policy", "")).startswith("NO_MISSING_")
            ):
                fail("EXTERNAL_DUTY_IS_NOT_MISSING_CONTRACT_CONTENT:" + row["criterion_id"])
            if req.get("applicability_status") != "CONFIRMED" and row.get("finding") != "UNKNOWN":
                fail("C07_FINDING_REQUIRES_CONFIRMED_C05")
            reason = str(row.get("reason", "")).casefold()
            if any(
                marker in reason
                for marker in (
                    "chưa gọi ai",
                    "provider uncertainty",
                    "not implemented",
                    "verification_provider_not_configured",
                    "call_limit",
                )
            ):
                fail("PROCESSING_FAILURE_IS_NOT_LEGAL_GOLD:" + row["criterion_id"])
        layers = answer.get("layer_receipts", {})
        for name in [
            "FACTS",
            "SCOPE_TEMPORAL",
            "RETRIEVAL_JUDGED_POOL",
            "CRITERIA",
            "CITATION_OCCURRENCES",
            "AGGREGATION",
            "RISKS",
            "RECOMMENDATION_ASSERTIONS",
            "REVIEW_POLICY",
            "REPORT_ASSERTIONS",
        ]:
            receipt = layers.get(name, {})
            if (
                receipt.get("status") != "ADJUDICATED"
                or receipt.get("source_sha256") != source["source_sha256"]
                or receipt.get("knowledge_snapshot_sha256") != snapshot_sha
            ):
                fail("MISSING_OR_UNBOUND_LAYER:" + name)
                continue
            artifact_id = receipt.get("artifact_id")
            artifact = (artifacts or {}).get(artifact_id)
            if not artifact or receipt.get("artifact_sha256") != canonical_sha(artifact):
                fail("MISSING_OR_CHANGED_ADJUDICATION_ARTIFACT:" + name)
                continue
            if (
                artifact.get("case_id") != cid
                or artifact.get("layer") != name
                or artifact.get("source_sha256") != source["source_sha256"]
                or artifact.get("knowledge_snapshot_sha256") != snapshot_sha
                or artifact.get("production_outputs_used") is not False
                or artifact.get("adjudicator_type") != "AI_SOURCE_ADJUDICATED"
                or artifact.get("status") != "ADJUDICATED"
                or not isinstance(artifact.get("judgments"), list)
                or not artifact.get("review_method")
            ):
                fail("INVALID_ADJUDICATION_ARTIFACT:" + name)
                continue
            if not _artifact_spans_match(artifact, source):
                fail("ADJUDICATION_ARTIFACT_QUOTE_MISMATCH:" + name)
            if name == "CRITERIA":
                decisions = artifact["judgments"]
                expected = {
                    (r["criterion_id"], r["finding"], r.get("disposition", "ASSESSED"))
                    for r in judged
                }
                observed = {
                    (r.get("criterion_id"), r.get("finding"), r.get("disposition", "ASSESSED"))
                    for r in decisions
                }
                if (
                    observed != expected
                    or len(decisions) != len(judged)
                    or any(not r.get("reason") or not r.get("adjudication_ids") for r in decisions)
                ):
                    fail("CRITERION_ARTIFACT_DOES_NOT_COVER_LABELS")
            projection = {
                "FACTS": "facts",
                "SCOPE_TEMPORAL": "requirements",
                "AGGREGATION": "requirements_aggregated",
                "CITATION_OCCURRENCES": "citations",
            }.get(name)
            if projection and canonical_sha(artifact["judgments"]) != canonical_sha(
                answer.get(projection, [])
            ):
                fail("ARTIFACT_DIFFERS_FROM_CASE_PROJECTION:" + name)
            if name == "CITATION_OCCURRENCES":
                for citation in artifact["judgments"]:
                    if (
                        not citation.get("citation_id")
                        or citation.get("status") not in {"VALID", "STALE", "INVALID", "UNKNOWN"}
                        or citation.get("identity") not in {"RESOLVED", "UNKNOWN"}
                        or citation.get("domain") not in {"MATCH", "MISMATCH", "UNKNOWN"}
                        or not citation.get("reason")
                        or not citation.get("evidence")
                    ):
                        fail("C03_EXTRACTION_IS_NOT_C09_ADJUDICATION")
                        break
            if name == "RETRIEVAL_JUDGED_POOL" and (
                not artifact.get("pool_definition")
                or artifact.get("outside_pool") != "UNJUDGED"
                or (
                    not artifact["judgments"]
                    and (
                        any(r.get("disposition", "ASSESSED") == "ASSESSED" for r in judged)
                        or not artifact.get("empty_reason")
                    )
                )
            ):
                fail("RELEVANCE_POOL_NOT_JUDGED")
            if name == "RETRIEVAL_JUDGED_POOL" and any(
                r.get("criterion_id") not in expected_criteria
                or r.get("relevance") not in {0, 1, 2}
                or not r.get("reason")
                or not r.get("evidence")
                for r in artifact["judgments"]
            ):
                fail("INVALID_RELEVANCE_JUDGMENT")
        if answer.get("pending_adjudications"):
            fail("PENDING_ADJUDICATIONS_REMAIN")
    ready = bool(sources) and not errors
    return {
        "release_status": "GOLD" if ready else "INCOMPLETE",
        "full_e2e_gold_ready": ready,
        "expected_cases": len(sources),
        "provided_cases": len(cases),
        "errors": errors,
    }
