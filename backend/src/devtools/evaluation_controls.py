"""Independent behavior specifications on synthetic contracts, not legal gold labels."""

from copy import deepcopy

from legal_checker.shared.contracts.pipeline import PipelineRequest
from legal_checker.workflows.steps_5_7 import evaluate


def base_request(knowledge, case_id, version_id="PV_GYC005", finding="SATISFIED"):
    version = knowledge.versions[version_id]
    text = "TÌNH HUỐNG GIẢ LẬP KIỂM THỬ. Bên bán Công ty A, bên mua Ông B; điều khoản kiểm thử."
    criteria = knowledge.criteria_for(version_id)
    context = {
        "ca_id": case_id,
        "phien_ban_id": "QA_SYNTHETIC_V750_R1",
        "rule_version": "CAN_HO_SEED_RULES_20261007",
        "legal_knowledge_version": "V749_LEGAL_KNOWLEDGE_PENDING_HUMAN",
        "knowledge_snapshot_sha256": knowledge.sha256,
        "run_id": case_id + "_RUN",
        "trace_id": case_id + "_TRACE",
    }
    requirement_id = case_id + "_REQ"
    chunk_id = case_id + "_CHUNK"
    requirement = {
        "yeu_cau_ca_id": requirement_id,
        "ca_id": case_id,
        "requirement_id": version["requirement_id"],
        "requirement_version_id": version_id,
        "scope_status": "MATCH",
        "version_status": "RESOLVED",
        "applicability_status": "CONFIRMED",
        "moc_ap_dung": "2024-09-01",
        "phien_ban_id": context["phien_ban_id"],
        "profile_snapshot_json": {"synthetic_spec": True, "all_gates_are_test_assumptions": True},
    }
    observations = []
    retrieval = []
    for i, criterion in enumerate(criteria):
        cid = criterion["tieu_chi_id"]
        observations.append(
            {
                "tieu_chi_id": cid,
                "proposed_finding": finding,
                "giai_thich": "Synthetic specification; gate values are explicit test assumptions.",
                "gates": {
                    k: True
                    for k in (
                        "coverage_complete",
                        "absence_verified",
                        "evidence_validated",
                        "source_verified",
                        "scope_confirmed",
                        "version_resolved",
                        "exceptions_resolved",
                    )
                },
                "evidence": [
                    {
                        "doan_id": chunk_id,
                        "trich_dan": text,
                        "ky_tu_bat_dau": 0,
                        "ky_tu_ket_thuc": len(text),
                    }
                ],
                "local_applicability": "MATCH",
                "mandatory_confirmed": True,
                "all_pages_readable": True,
                "all_related_documents_received": True,
                "model_version": "SYNTHETIC_SPEC_NOT_LLM",
                "prompt_version": "NOT_USED",
            }
        )
        retrieval.append(
            {
                "truy_xuat_id": case_id + f"_RET_{i}",
                "yeu_cau_ca_id": requirement_id,
                "tieu_chi_id": cid,
                "doan_id": chunk_id,
                "thu_hang": 1,
                "duoc_chon": True,
                "retrieval_version": "SYNTHETIC_SPEC",
                "index_version": "SYNTHETIC_SPEC",
                "lan_chay_id": context["run_id"],
            }
        )
    return {
        **context,
        "payload": {
            "hop_dong_id": case_id + "_DOC",
            "requirements": [requirement],
            "chunks": [
                {
                    "doan_id": chunk_id,
                    "hop_dong_id": case_id + "_DOC",
                    "noi_dung": text,
                    "page_start": 1,
                    "page_end": 1,
                }
            ],
            "retrieval": retrieval,
            "observations": observations,
            "citations": [],
        },
    }


def controlled_cases(knowledge):
    """Expected labels are specified here before invoking any engine."""
    cases = []

    def add(
        name,
        finding="SATISFIED",
        status="COMPLIANT",
        version="PV_GYC005",
        mutate=None,
        expected_findings=None,
        error=None,
        legal=None,
        citation_rule=None,
    ):
        raw = base_request(knowledge, "QA_" + name, version, finding)
        if mutate:
            mutate(raw)
        expected = {
            "requirement_statuses": [status] if status else [],
            "criterion_findings": (
                expected_findings
                if expected_findings is not None
                else [finding] * len(raw["payload"]["observations"])
            ),
        }
        if error:
            expected = {"error_contains": error}
        if citation_rule is not None:
            expected["citation_rules"] = citation_rule
        cases.append(
            {
                "case_id": raw["ca_id"],
                "input": raw,
                "expected": expected,
                "rationale": name,
                "legal_review_id": legal,
            }
        )

    add("CONTENT_SATISFIED")
    add("CONTENT_MISSING", "MISSING", "NON_COMPLIANT")
    add("CONTENT_VIOLATED", "VIOLATED", "NON_COMPLIANT")
    add("CONTENT_UNKNOWN", "UNKNOWN", "INSUFFICIENT")
    for gate in (
        "source_verified",
        "scope_confirmed",
        "version_resolved",
        "evidence_validated",
        "exceptions_resolved",
    ):
        add(
            "GATE_" + gate.upper(),
            status="INSUFFICIENT",
            mutate=lambda r, g=gate: [
                o["gates"].update({g: False}) for o in r["payload"]["observations"]
            ],
            expected_findings=["UNKNOWN"] * len(knowledge.criteria_for("PV_GYC005")),
        )
    add(
        "MISSING_NO_ABSENCE_PROOF",
        "MISSING",
        "INSUFFICIENT",
        mutate=lambda r: [
            o["gates"].update(absence_verified=False) for o in r["payload"]["observations"]
        ],
        expected_findings=["UNKNOWN"] * len(knowledge.criteria_for("PV_GYC005")),
    )
    add(
        "MIXED_PARTIAL",
        status="PARTIAL",
        mutate=lambda r: r["payload"]["observations"][0].update(proposed_finding="MISSING"),
        expected_findings=["MISSING"]
        + ["SATISFIED"] * (len(knowledge.criteria_for("PV_GYC005")) - 1),
    )

    def no_scope(r):
        r["payload"]["requirements"][0].update(
            scope_status="UNKNOWN",
            version_status="UNKNOWN",
            applicability_status="UNKNOWN",
            moc_ap_dung=None,
        )

    add(
        "UNRESOLVED_SCOPE",
        status="INSUFFICIENT",
        mutate=no_scope,
        expected_findings=["UNKNOWN"] * len(knowledge.criteria_for("PV_GYC005")),
    )

    def not_applicable(r):
        r["payload"]["requirements"][0].update(
            scope_status="NO_MATCH", applicability_status="NOT_APPLICABLE"
        )

    add("NOT_APPLICABLE", status=None, mutate=not_applicable, expected_findings=[])
    add(
        "FOREIGN_CHUNK",
        mutate=lambda r: r["payload"]["chunks"][0].update(hop_dong_id="OTHER_DOC"),
        error="Chunk belongs to a different contract",
    )
    add(
        "FOREIGN_RETRIEVAL_RUN",
        mutate=lambda r: r["payload"]["retrieval"][0].update(lan_chay_id="OTHER_RUN"),
        error="Retrieval run does not match envelope",
    )
    numeric_specs = [
        (
            "FIRST_30_BOUNDARY",
            "PV_GYC062",
            {
                "contract_price": "100",
                "first_payment": "20",
                "deposit": "10",
                "deposit_included_in_first_payment": False,
            },
            "SATISFIED",
        ),
        (
            "FIRST_30_EXCEEDED",
            "PV_GYC062",
            {
                "contract_price": "100",
                "first_payment": "30.0001",
                "deposit": "0",
                "deposit_included_in_first_payment": False,
            },
            "VIOLATED",
        ),
        (
            "DEPOSIT_ALREADY_INCLUDED",
            "PV_GYC062",
            {
                "contract_price": "100",
                "first_payment": "30",
                "deposit": "10",
                "deposit_included_in_first_payment": True,
            },
            "SATISFIED",
        ),
        (
            "DEPOSIT_INCLUSION_UNKNOWN",
            "PV_GYC062",
            {"contract_price": "100", "first_payment": "20", "deposit": "10"},
            "UNKNOWN",
        ),
        (
            "INVALID_PRICE_ZERO",
            "PV_GYC062",
            {
                "contract_price": "0",
                "first_payment": "20",
                "deposit": "0",
                "deposit_included_in_first_payment": False,
            },
            "UNKNOWN",
        ),
        (
            "DOMESTIC_70_BOUNDARY",
            "PV_GYC064",
            {
                "contract_price": "100",
                "prehandover_cumulative": "70",
                "foreign_seller_art10_4": False,
            },
            "SATISFIED",
        ),
        (
            "DOMESTIC_70_EXCEEDED",
            "PV_GYC064",
            {
                "contract_price": "100",
                "prehandover_cumulative": "70.01",
                "foreign_seller_art10_4": False,
            },
            "VIOLATED",
        ),
        (
            "FOREIGN_50_BOUNDARY",
            "PV_GYC064",
            {
                "contract_price": "100",
                "prehandover_cumulative": "50",
                "foreign_seller_art10_4": True,
            },
            "SATISFIED",
        ),
        (
            "FOREIGN_50_EXCEEDED",
            "PV_GYC064",
            {
                "contract_price": "100",
                "prehandover_cumulative": "50.01",
                "foreign_seller_art10_4": True,
            },
            "VIOLATED",
        ),
        (
            "CERTIFICATE_95_BOUNDARY",
            "PV_GYC065",
            {"contract_price": "100", "before_certificate_cumulative": "95"},
            "SATISFIED",
        ),
        (
            "CERTIFICATE_95_EXCEEDED",
            "PV_GYC065",
            {"contract_price": "100", "before_certificate_cumulative": "95.01"},
            "VIOLATED",
        ),
    ]
    for name, version, facts, expected in numeric_specs:
        facts = {"scope": "FUTURE_COMMERCIAL", **facts}

        def update(r, f=facts):
            for obs in r["payload"]["observations"]:
                obs.update(facts=f, facts_verified=True)

        add(
            name,
            status={
                "SATISFIED": "COMPLIANT",
                "VIOLATED": "NON_COMPLIANT",
                "UNKNOWN": "INSUFFICIENT",
            }[expected],
            version=version,
            mutate=update,
            expected_findings=[expected],
            legal="LEGAL_ART25_2024",
        )
    for status, domain, verified, rule in [
        ("VALID", "MATCH", True, []),
        ("STALE", "MATCH", True, ["RULE_CITATION_STALE"]),
        ("INVALID", "MATCH", True, ["RULE_CITATION_INVALID"]),
        ("INVALID", "MISMATCH", True, ["RULE_CITATION_DOMAIN_MISMATCH"]),
        ("UNKNOWN", "UNKNOWN", False, ["RULE_CITATION_UNKNOWN"]),
        ("STALE", "MATCH", False, ["RULE_CITATION_UNKNOWN"]),
    ]:

        def append_citation(r, s=status, d=domain, v=verified):
            r["payload"]["citations"] = [
                {
                    "finding_id": r["ca_id"] + "_CF",
                    "ca_id": r["ca_id"],
                    "vien_dan_id": r["ca_id"] + "_CIT",
                    "normalized_van_ban_id": "VBPL001",
                    "relevant_date": "2024-09-01",
                    "status": s,
                    "reason_code": "DOMAIN_MISMATCH" if d == "MISMATCH" else "SYNTHETIC_SPEC",
                    "ly_do": "Synthetic citation finding; temporal/identity facts assumed.",
                    "domain_status": d,
                    "finding_verified": v,
                    "current_status": "REPEALED",
                    "source_snapshot_json": {
                        k: True
                        for k in (
                            "reviewed_knowledge",
                            "identity_confirmed",
                            "temporal_source_complete",
                            "transition_context_resolved",
                            "official_evidence_required",
                            "identity_or_context_invalidity_proven",
                            "context_mismatch_proven",
                        )
                    },
                    "lan_chay_id": r["run_id"],
                    "knowledge_version": r["legal_knowledge_version"],
                }
            ]

        add(
            "CITATION_" + status + "_" + domain + ("_UNVERIFIED" if not verified else ""),
            mutate=append_citation,
            citation_rule=rule,
        )
    return cases


def verify_control(case, knowledge):
    expected = case["expected"]
    try:
        response = evaluate(PipelineRequest.model_validate(deepcopy(case["input"])), knowledge)
    except ValueError as error:
        if expected.get("error_contains") and expected["error_contains"] in str(error):
            return None
        raise
    if "error_contains" in expected:
        raise AssertionError("Expected rejection: " + case["case_id"])
    actual = response.payload
    assert [r.status for r in actual.requirement_results] == expected["requirement_statuses"], case[
        "case_id"
    ]
    assert [r.finding for r in actual.criterion_results] == expected["criterion_findings"], case[
        "case_id"
    ]
    if "citation_rules" in expected:
        assert [r.quy_tac_id for r in actual.risks if r.source.citation_finding_id] == expected[
            "citation_rules"
        ]
    return response
