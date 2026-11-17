"""Lossless shared-source batches; item-local evidence permissions stay independent."""

import json
import re
from copy import deepcopy

from pydantic import ValidationError

from legal_checker.modules.compliance.decision_rules import parse_json_object
from legal_checker.modules.compliance.llm_contracts import SemanticProposal
from legal_checker.shared.llm.types import LlmClientError, LlmResponse


def shared_source_payload(packages):
    """Send original source text once per batch; keep item-local quote IDs/permissions.

    No summarisation/truncation. The model sees labelled lines, not offset arithmetic.
    Responses are checked against original packages, never against this view.
    """
    sources, rows, common = {}, [], {}
    for index, original in enumerate(packages, 1):
        row = deepcopy(original)
        compact = row.get("source_text_representation") == "ORDERED_QUOTE_LINES_V1"
        raw = {c["doan_id"]: c.get("noi_dung") for c in row["selected_contract_evidence"]}
        catalogs = []
        for group in row["quote_catalog"]:
            chunk_id = group["doan_id"]
            text = "".join(q[1] for q in group["quotes"]) if compact else raw[chunk_id]
            if not isinstance(text, str):
                raise ValueError("Missing original source text")
            if chunk_id in sources and sources[chunk_id]["text"] != text:
                raise ValueError("Conflicting source text under the same chunk ID")
            if chunk_id not in sources:
                lines = [
                    (m.start(), m.group())
                    for m in re.finditer(r"[^\n]*(?:\n|$)", text)
                    if m.end() > m.start()
                ]
                sources[chunk_id] = {
                    "source_ref": f"S{len(sources) + 1}",
                    "doan_id": chunk_id,
                    "text": text,
                    "lines": [[f"L{i}", value] for i, (_, value) in enumerate(lines, 1)],
                    "positions": {start: f"L{i}" for i, (start, _) in enumerate(lines, 1)},
                }
            cursor, spans = 0, []
            for quote in group["quotes"]:
                quote_id, value = quote if compact else (quote["quote_id"], quote["text"])
                start = cursor if compact else text.find(value, cursor)
                if start < 0 or text[start : start + len(value)] != value:
                    raise ValueError("Quote does not match its original source")
                cursor = start + len(value)
                if quote_id is not None:
                    spans.append([quote_id, sources[chunk_id]["positions"][start]])
            catalogs.append({"source_ref": sources[chunk_id]["source_ref"], "quotes": spans})
        row["quote_catalog"] = catalogs
        row["selected_contract_evidence"] = [
            {
                **{k: v for k, v in c.items() if k != "noi_dung"},
                "source_ref": sources[c["doan_id"]]["source_ref"],
            }
            for c in row["selected_contract_evidence"]
        ]
        row["source_text_representation"] = "SHARED_SOURCE_QUOTE_LINES_V1"
        rows.append({"item_id": f"C{index}", **row})
    for name in ("context", "contract_id", "unverified_profile_context"):
        if rows and all(r.get(name) == rows[0].get(name) for r in rows):
            common[name] = rows[0].get(name)
            for r in rows:
                r.pop(name, None)
    return {
        "shared_context": common,
        "source_catalog": [
            {k: v for k, v in s.items() if k not in {"text", "positions"}} for s in sources.values()
        ],
        "criteria": rows,
    }


def pack_batches(items, *, max_items, max_chars):
    """Bound the serialized joint request, not just each item independently."""
    group = []
    for item in items:
        proposed = [*group, item]
        size = len(json.dumps(shared_source_payload([p for _, p in proposed]), ensure_ascii=False))
        if group and (len(proposed) > max_items or size > max_chars):
            yield group
            group = [item]
        else:
            group = proposed
    if group:
        yield group


def complete_batch(
    client, context, packages, *, instructions, prompt_version, schema_version, max_chars=None
):
    """Model returns short aliases; backend restores real IDs and exact source quotes."""
    by_alias = {f"C{index}": p for index, p in enumerate(packages, 1)}
    by_id = {p["criterion"]["tieu_chi_id"]: p for p in packages}
    payload = shared_source_payload(packages)
    if max_chars is not None and len(json.dumps(payload, ensure_ascii=False)) > max_chars:
        return {key: LlmClientError("CONTEXT_LIMIT") for key in by_id}
    all_quote_ids = sorted(
        {
            q_id
            for p in packages
            for group in p.get("quote_catalog", [])
            for q in group.get("quotes", [])
            if (
                q_id := (
                    q[0]
                    if p.get("source_text_representation") == "ORDERED_QUOTE_LINES_V1"
                    else q["quote_id"]
                )
            )
            is not None
        }
    )
    all_external_aliases = sorted(
        {
            item["external_alias"]
            for p in packages
            for item in p.get("external_registry_metadata_only", [])
            if "external_alias" in item
        }
    )
    properties: dict = {
        "item_id": {"type": "string", "enum": list(by_alias)},
        "proposed_finding": {
            "type": "string",
            "enum": ["SATISFIED", "VIOLATED", "MISSING", "UNKNOWN"],
        },
        "giai_thich": {"type": "string"},
        "missing_conditions": {"type": "array", "items": {"type": "string"}},
        "verification_requirements": {"type": "array", "items": {"type": "string"}},
        "quote_ids": (
            {"type": "array", "items": {"type": "string", "enum": all_quote_ids}}
            if all_quote_ids
            else {"type": "array", "items": {"type": "string"}}
        ),
    }
    if all_external_aliases:
        properties["external_ids"] = {
            "type": "array",
            "items": {"type": "string", "enum": all_external_aliases},
        }
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["proposals"],
        "properties": {
            "proposals": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": list(properties),
                    "properties": properties,
                },
            }
        },
    }
    response = client.complete(
        context,
        instructions=instructions + "\nSchema batch dùng item_id C1/C2/... thay criterion ID dài. "
        'Trả {"proposals":[...]} đúng một proposal cho MỖI item_id được cung cấp. '
        "Mỗi quote_id Q1/Q2/... phải có trong quote_catalog của CHÍNH item đó. "
        "Không trả tieu_chi_id, doan_id, quote text, offsets hoặc candidate_facts. "
        "external_ids dùng external_alias E1/E2/... trong metadata của CHÍNH item; "
        "nếu dựa trên chứng từ ngoài phải điền alias tương ứng. Không dùng evidence "
        "chéo item. Backend tự gắn criterion/chunk IDs và phục hồi text/offsets. "
        "source_catalog chứa nguyên văn dùng chung. quote_catalog của mỗi item chứa "
        "[quote_id, line_id] trỏ tới dòng nguyên văn trong source_ref; "
        "chỉ được chọn quote_ids thuộc chính item, dù source_ref được chia sẻ.",
        payload=payload,
        schema=schema,
        prompt_version=prompt_version,
        schema_version=schema_version + "_BATCH_SHARED_SOURCE_V3",
    )
    try:
        data = parse_json_object(response.content)
        rows = data["proposals"]
        alias_mode = bool(rows and "item_id" in rows[0])
        key = "item_id" if alias_mode else "tieu_chi_id"
        owners = by_alias if alias_mode else by_id
        actual = [r[key] for r in rows]
        if (
            set(data) != {"proposals"}
            or len(actual) != len(set(actual))
            or set(actual) != set(owners)
        ):
            raise ValueError("Batch ownership mismatch")
    except (KeyError, TypeError, ValueError):
        raise LlmClientError("INVALID_BATCH_RESPONSE") from None
    results = {}
    for row in rows:
        package = owners[row[key]]
        criterion_id = package["criterion"]["tieu_chi_id"]
        try:
            if "quote_ids" in row:
                quotes = {
                    quote_id: group["doan_id"]
                    for group in package["quote_catalog"]
                    for q in group["quotes"]
                    if (
                        quote_id := q[0]
                        if package.get("source_text_representation") == "ORDERED_QUOTE_LINES_V1"
                        else q["quote_id"]
                    )
                    is not None
                }
                if not isinstance(row["quote_ids"], list) or any(
                    q not in quotes for q in row["quote_ids"]
                ):
                    raise LlmClientError("FOREIGN_QUOTE_ID")
                allowed = {}
                for item in package["external_registry_metadata_only"]:
                    allowed[item["bang_chung_id"]] = item["bang_chung_id"]
                    allowed[item["external_alias"]] = item["bang_chung_id"]
                external_ids = row.get("external_ids", [])
                if not isinstance(external_ids, list) or any(
                    e not in allowed for e in external_ids
                ):
                    raise LlmClientError("UNREGISTERED_EXTERNAL_ID")
                row = {
                    "tieu_chi_id": criterion_id,
                    **{
                        name: row[name]
                        for name in (
                            "proposed_finding",
                            "giai_thich",
                            "missing_conditions",
                            "verification_requirements",
                        )
                    },
                    "checked_conditions": [],
                    "candidate_facts": [],
                    "evidence": [
                        {
                            "doan_id": quotes[q],
                            "trich_dan": "",
                            "ky_tu_bat_dau": None,
                            "quote_id": q,
                        }
                        for q in row["quote_ids"]
                    ],
                    "external_evidence_ids": [allowed[e] for e in external_ids],
                }
            proposal = SemanticProposal.model_validate(row)
            verification = package.get("backend_verification") or {}
            if (
                proposal.proposed_finding in {"SATISFIED", "VIOLATED"}
                and not proposal.evidence
                and not proposal.external_evidence_ids
                and verification.get("local_applicability") != "NO_MATCH"
            ):
                raise LlmClientError("MISSING_SUPPORTING_EVIDENCE")
            results[criterion_id] = LlmResponse(
                proposal.model_dump_json(), response.model_version, response.request_id, None, None
            )
        except LlmClientError as error:
            results[criterion_id] = error
        except (KeyError, TypeError, ValueError, ValidationError):
            results[criterion_id] = LlmClientError("INVALID_SCHEMA")
    return results
