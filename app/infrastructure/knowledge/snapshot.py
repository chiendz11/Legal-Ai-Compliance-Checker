import hashlib
import json
from pathlib import Path
from typing import Any

DEFAULT_KNOWLEDGE = Path(__file__).resolve().parents[3] / "data" / "knowledge.json"


class Knowledge:
    """Immutable, checksummed knowledge snapshot, separate from runtime fixtures."""

    def __init__(self, path: Path = DEFAULT_KNOWLEDGE):
        content = path.read_bytes()
        self.sha256 = hashlib.sha256(content).hexdigest()
        snapshot = json.loads(content)
        if snapshot["schema_version"] != "v7.3.2":
            raise ValueError("Unsupported knowledge schema")
        self.tables = snapshot["tables"]
        self.criteria = self.index("tieu_chi_danh_gia", "tieu_chi_id")
        self.versions = self.index("phien_ban_yeu_cau", "requirement_version_id")
        self.risks = self.index("danh_muc_rui_ro", "rui_ro_id")
        self.recommendations = self.index("danh_muc_khuyen_nghi", "khuyen_nghi_id")
        self.aggregations = self.index("quy_tac_tong_hop", "quy_tac_tong_hop_id")
        self.articles = self.index("dieu_khoan_phap_ly", "dieu_khoan_id")
        self.documents = self.index("van_ban_phap_ly", "van_ban_id")

    def index(self, table: str, key: str) -> dict[str, dict[str, Any]]:
        result = {}
        for row in self.tables[table]:
            if not row[key] or row[key] in result:
                raise ValueError(f"Invalid or duplicate {table}.{key}")
            result[row[key]] = row
        return result

    def criteria_for(self, version_id: str | None):
        return sorted(
            [r for r in self.criteria.values() if r["requirement_version_id"] == version_id],
            key=lambda r: (r["thu_tu"] or 0, r["tieu_chi_id"]),
        )

    def decision(self, criterion_id: str, finding: str):
        matches = [
            r
            for r in self.tables["quy_tac_quyet_dinh"]
            if r["tieu_chi_id"] == criterion_id and r["finding"] == finding
        ]
        if len(matches) != 1:
            raise ValueError(f"Expected one decision rule for {criterion_id}/{finding}")
        return matches[0]

    def legal_basis(self, criterion):
        article_id = criterion.get("source_dieu_khoan_id")
        version_id = criterion["requirement_version_id"]
        version = self.versions[version_id]
        document_id = version["source_van_ban_id"]
        if article_id not in self.articles or document_id not in self.documents:
            return []
        return [version_id, article_id, document_id]
