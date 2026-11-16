"""Reproducible additive catalog revision; never rewrite a run's knowledge snapshot."""

import hashlib
import json
from copy import deepcopy

from psycopg.types.json import Jsonb

from legal_checker.core.postgres import connect_postgres
from legal_checker.modules.legal_knowledge.repository import canonical

BASE_SHA = "39d823fb72b886d88d55367e928f96a39218d16e4287899fc1a163d25458bc4d"
REVISION = "V750_RUNTIME_ALIGNMENT_20261108"
HISTORICAL = {
    "FAM_GYC048": ("FAM_TEMPLATE_REGISTRATION", ["ANNEX_VB_QD02_2012_DANH_MUC", "ART_VBPL008_19"]),
    "FAM_MAINTENANCE_ACCOUNT": ("FAM_APT_MAINTENANCE_ACCOUNT", ["ART_VB_ND99_2015_36"]),
}


def revised_content(base):
    if hashlib.sha256(canonical(base).encode()).hexdigest() != BASE_SHA:
        raise ValueError("Runtime alignment requires the exact TEAM 20261107 base snapshot")
    result = deepcopy(base)
    tables = result["tables"]
    articles = {r["dieu_khoan_id"] for r in tables["dieu_khoan_phap_ly"]}
    for family, (legacy, basis) in HISTORICAL.items():
        if not set(basis) <= articles:
            raise ValueError("Historical coverage lacks registered legal sources")
        versions = [v for v in tables["phien_ban_yeu_cau"] if v["requirement_id"] == family]
        if not versions or not any(
            v["requirement_id"] == legacy for v in tables["phien_ban_yeu_cau"]
        ):
            raise ValueError("Historical coverage family missing")
        for version in versions:
            policy = json.loads(version["quy_tac_chuyen_tiep"])
            policy.update(
                historical_equivalent_family_id=legacy, historical_basis_article_ids=basis
            )
            version["quy_tac_chuyen_tiep"] = canonical(policy)
    scopes = [s for s in tables["pham_vi_ap_dung"] if s["requirement_id"] == "FAM_APT_DEPOSIT"]
    if not scopes:
        raise ValueError("Deposit scope missing")
    for scope in scopes:
        value = scope["dieu_kien_json"]
        value = json.loads(value) if isinstance(value, str) else value
        value["all"].append({"field": "co_thoa_thuan_dat_coc", "op": "EQ", "value": True})
        scope["dieu_kien_json"] = value
    result["catalog_revision"] = REVISION
    result["base_snapshot_sha256"] = BASE_SHA
    return result


def apply_revision(database_url):
    with connect_postgres(database_url) as conn:
        row = conn.execute(
            "SELECT content FROM knowledge.knowledge_snapshots WHERE sha256=%s", (BASE_SHA,)
        ).fetchone()
        if not row:
            raise ValueError("Seed the TEAM 20261107 dataset before applying this revision")
        content = revised_content(row["content"])
        sha = hashlib.sha256(canonical(content).encode()).hexdigest()
        conn.execute(
            "INSERT INTO knowledge.knowledge_snapshots "
            "(sha256,schema_version,content,review_status) VALUES (%s,%s,%s,%s) "
            "ON CONFLICT (sha256) DO NOTHING",
            (sha, content["schema_version"], Jsonb(content), "SOURCE_CHECKED"),
        )
    return {
        "revision": REVISION,
        "base_sha256": BASE_SHA,
        "knowledge_snapshot_sha256": sha,
        "review_status": "SOURCE_CHECKED",
        "old_snapshots_preserved": True,
    }
