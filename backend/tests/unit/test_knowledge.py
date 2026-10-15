import json


def test_snapshot_relationships_and_disabled_rules(knowledge):
    assert len(knowledge.criteria) == 9
    for row in knowledge.criteria.values():
        assert row["requirement_version_id"] in knowledge.versions
        assert knowledge.decision(row["tieu_chi_id"], "UNKNOWN")
    for rule in knowledge.tables["quy_tac_rui_ro"]:
        assert rule["rui_ro_id"] in knowledge.risks
        if rule["nhanh"] == "COMPLIANCE":
            assert rule["tieu_chi_id"] in knowledge.criteria
        assert isinstance(json.loads(rule["trigger_json"]), dict)
    for link in knowledge.tables["rui_ro_khuyen_nghi"]:
        assert link["rui_ro_id"] in knowledge.risks
        assert link["khuyen_nghi_id"] in knowledge.recommendations
    assert "doan_hop_dong" not in knowledge.tables
    assert "ca_danh_gia" not in knowledge.tables
