"""Integrity checks for multipart Excel QA artifacts; no legal-accuracy claims."""

import hashlib
import json
from collections import defaultdict

from devtools.database_seed import SeedError
from devtools.qa_schema import QA_TABLES


def join_artifacts(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row["case_id"], row["role"], row["contract_name"], row["record_id"])].append(row)
    results = {}
    for key, parts in groups.items():
        parts.sort(key=lambda r: r["part_number"])
        if [r["part_number"] for r in parts] != list(range(1, len(parts) + 1)) or any(
            r["part_count"] != len(parts) or r["payload_sha256"] != parts[0]["payload_sha256"]
            for r in parts
        ):
            raise SeedError(f"Incomplete or inconsistent QA artifact: {key}")
        raw = "".join(r["content"] for r in parts)
        if hashlib.sha256(raw.encode()).hexdigest() != parts[0]["payload_sha256"]:
            raise SeedError(f"QA artifact checksum mismatch: {key}")
        results[key] = json.loads(raw)
    return results


def validate_qa(seed):
    for table in QA_TABLES:
        rows = seed.qa_tables.get(table.name, [])
        ids = [r[table.primary_key] for r in rows]
        if any(not v for v in ids) or len(ids) != len(set(ids)):
            raise SeedError(f"Empty or duplicate QA key in {table.name}")
    cases = {r["case_id"]: r for r in seed.qa_tables.get("case_manifest", [])}
    runtime = {r["ca_id"]: r["hop_dong_id"] for r in seed.tables["ca_danh_gia"]}
    splits = {}
    for row in cases.values():
        if row["split"] not in ("DEV", "VALIDATION", "TEST", "REGRESSION"):
            raise SeedError("Invalid QA split")
        if row["case_kind"] not in ("CORPUS", "CONTROLLED"):
            raise SeedError("Invalid QA case_kind")
        if row["label_quality"] not in ("SILVER_GUARD_REFERENCE", "SYNTHETIC_SPEC"):
            raise SeedError("Invalid QA label_quality")
        if row["case_kind"] == "CORPUS" and runtime.get(row["case_id"]) != row["hop_dong_id"]:
            raise SeedError("QA corpus case references a foreign runtime contract")
        if row["group_id"] in splits and splits[row["group_id"]] != row["split"]:
            raise SeedError("A document family crosses QA splits")
        splits[row["group_id"]] = row["split"]
    for table in ("artifacts", "controlled_assertions"):
        if any(r["case_id"] not in cases for r in seed.qa_tables.get(table, [])):
            raise SeedError("QA record references an unknown case")
    if any(
        r["role"] not in ("INPUT", "EXPECTED", "PROPOSAL")
        for r in seed.qa_tables.get("artifacts", [])
    ):
        raise SeedError("Invalid QA artifact role")
    # Validate one payload at a time: large workbooks need not retain every decoded DTO.
    groups = defaultdict(list)
    for row in seed.qa_tables.get("artifacts", []):
        groups[(row["case_id"], row["role"], row["contract_name"], row["record_id"])].append(row)
    for parts in groups.values():
        join_artifacts(parts)
