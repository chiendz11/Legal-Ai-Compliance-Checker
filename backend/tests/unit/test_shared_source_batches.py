"""Lossless batching and item-local permissions, including adversarial ownership."""

import json
from copy import deepcopy

import pytest
from legal_checker.modules.compliance.batching import (
    complete_batch,
    pack_batches,
    shared_source_payload,
)
from legal_checker.shared.llm.types import LlmClientError, LlmResponse


def package(criterion="C1", text="Nghĩa vụ bên bán.\n\nx\nNghĩa vụ bên bán.\n"):
    return {
        "criterion": {"tieu_chi_id": criterion},
        "context": {"run_id": "RUN_A"},
        "contract_id": "HD_A",
        "unverified_profile_context": {},
        "external_registry_metadata_only": [],
        "source_text_representation": "ORDERED_QUOTE_LINES_V1",
        "selected_contract_evidence": [{"doan_id": "D1"}],
        "quote_catalog": [
            {
                "doan_id": "D1",
                "quotes": [
                    ["Q1", "Nghĩa vụ bên bán.\n"],
                    [None, "\n"],
                    [None, "x\n"],
                    ["Q2", "Nghĩa vụ bên bán.\n"],
                ],
            }
        ],
    }


def test_shared_text_is_lossless_with_blank_short_repeated_unicode_lines():
    items = [package(), package("C2")]
    before = deepcopy(items)
    result = shared_source_payload(items)
    assert len(result["source_catalog"]) == 1
    assert "".join(line[1] for line in result["source_catalog"][0]["lines"]) == (
        "Nghĩa vụ bên bán.\n\nx\nNghĩa vụ bên bán.\n"
    )
    assert result["criteria"][0]["quote_catalog"][0]["quotes"] == [["Q1", "L1"], ["Q2", "L4"]]
    assert items == before


def test_same_chunk_id_cannot_hide_conflicting_source_text():
    a, b = package(), package("C2")
    b["quote_catalog"][0]["quotes"][0][1] = "Một nội dung khác.\n"
    with pytest.raises(ValueError, match="Conflicting source"):
        shared_source_payload([a, b])


def test_joint_budget_partitions_without_dropping_criteria():
    items = [(str(i), package(str(i))) for i in range(9)]
    limit = len(json.dumps(shared_source_payload([p for _, p in items[:2]]), ensure_ascii=False))
    batches = list(pack_batches(items, max_items=8, max_chars=limit))
    assert [key for group in batches for key, _ in group] == [key for key, _ in items]
    assert all(
        len(json.dumps(shared_source_payload([p for _, p in g]), ensure_ascii=False)) <= limit
        for g in batches
    )


def test_shared_document_does_not_grant_foreign_quote_permission():
    first, second = package("C1"), package("C2")
    first["quote_catalog"][0]["quotes"][-1][0] = None

    class Client:
        def complete(self, context, **kwargs):
            return LlmResponse(
                json.dumps(
                    {
                        "proposals": [
                            {
                                "item_id": item["item_id"],
                                "proposed_finding": "SATISFIED",
                                "giai_thich": "Attempt a quote not permitted to the first item",
                                "missing_conditions": [],
                                "verification_requirements": [],
                                "quote_ids": ["Q2"],
                                "external_ids": [],
                            }
                            for item in kwargs["payload"]["criteria"]
                        ]
                    }
                ),
                "OFFLINE_TEST",
            )

    result = complete_batch(
        Client(),
        None,
        [first, second],
        instructions="TEST",
        prompt_version="TEST",
        schema_version="TEST",
    )
    assert isinstance(result["C1"], LlmClientError)
    assert result["C1"].code == "FOREIGN_QUOTE_ID"
    assert not isinstance(result["C2"], LlmClientError)


def test_single_item_over_joint_limit_does_not_call_provider():
    class Client:
        def complete(self, *args, **kwargs):
            raise AssertionError("Oversized transport must not call provider")

    result = complete_batch(
        Client(),
        None,
        [package()],
        instructions="TEST",
        prompt_version="TEST",
        schema_version="TEST",
        max_chars=1,
    )
    assert result["C1"].code == "CONTEXT_LIMIT"
