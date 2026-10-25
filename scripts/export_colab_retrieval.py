"""Package step-4 inputs and code into one zip for a GPU runtime without PostgreSQL (Colab).

The zip holds the retrieval code (`legal_checker`, pydantic only), `colab_retrieval.py`
and a bundle with, per case: context, chunks, reference C05 (input), reference C06 (for
Recall@K) and the criteria of the referenced versions. Run from repository root:

    python -m scripts.export_colab_retrieval --split DEV
"""

import argparse
import gzip
import json
import os
import zipfile
from pathlib import Path

from devtools.upstream_fixtures import list_cases, load_artifact, load_context, load_document
from dotenv import load_dotenv
from legal_checker.modules.legal_knowledge.repository import Knowledge
from legal_checker.modules.retrieval.repository import RetrievalDatasetRepository

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend/src/legal_checker"
# Modules the Colab runner imports; the rest of the backend (DB, API) is not needed there.
CODE = (
    "__init__.py",
    "shared",
    "modules/__init__.py",
    "modules/retrieval",
    "modules/legal_knowledge/__init__.py",
    "modules/legal_knowledge/models.py",
)


def export(database_url: str, split: str, limit: int | None, output: Path) -> None:
    knowledge = Knowledge(database_url)
    paths = RetrievalDatasetRepository(database_url)
    cases = list_cases(database_url, split)[:limit]
    bundle = output.with_suffix(".jsonl.gz")
    output.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(bundle, "wt", encoding="utf-8") as file:
        for number, ca_id in enumerate(cases, start=1):
            requirements = load_artifact(database_url, ca_id, "EXPECTED", "C05")
            document = load_document(database_url, ca_id)
            versions = {r["requirement_version_id"] for r in requirements} - {None}
            record = {
                "ca_id": ca_id,
                "context": load_context(database_url, ca_id, f"{ca_id}_B_COLAB").model_dump(
                    mode="json"
                ),
                "chunks": [c.model_dump(mode="json") for c in document.chunks],
                "section_paths": paths.section_paths(document.contract_profile.hop_dong_id),
                "fact_evidence": [
                    {"ten_truong": f.ten_truong, "doan_ids": list(f.doan_ids)}
                    for f in paths.fact_evidence(document.contract_profile.hop_dong_id)
                ],
                "requirements": requirements,
                "reference": load_artifact(database_url, ca_id, "EXPECTED", "C06"),
                "criteria": {
                    v: [
                        {
                            k: c[k]
                            for k in ("tieu_chi_id", "noi_dung", "thu_tu", "requirement_version_id")
                        }
                        for c in knowledge.criteria_for(v)
                    ]
                    for v in sorted(versions)
                },
            }
            file.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
            if number % 20 == 0:
                print(f"  {number}/{len(cases)} cases")

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(bundle, f"bundle_{split}.jsonl.gz")
        archive.write(ROOT / "scripts/colab_retrieval.py", "colab_retrieval.py")
        pool = ROOT / "data/private/eval/goldset_pool_DEV.json"
        labels = ROOT / "data/private/eval/goldset_labels_DEV.json"
        if split == "DEV" and pool.exists() and labels.exists():
            # Independent relevance labels so the GPU run is scored like the local one.
            goldset = {
                "pool": json.loads(pool.read_text(encoding="utf-8")),
                "labels": json.loads(labels.read_text(encoding="utf-8")),
            }
            archive.writestr("goldset_DEV.json", json.dumps(goldset, ensure_ascii=False))
        for entry in CODE:
            path = PACKAGE / entry
            files = [path] if path.is_file() else sorted(path.rglob("*.py"))
            for item in files:
                archive.write(item, Path("legal_checker") / item.relative_to(PACKAGE))
    bundle.unlink()
    print(f"Wrote {output} ({output.stat().st_size / 2**20:.1f} MB) with {len(cases)} cases")


def main() -> None:
    load_dotenv(ROOT / ".env", override=False)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--split", default="DEV", choices=["DEV", "VALIDATION"])
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    output = ROOT / "data/private/colab" / f"colab_retrieval_{args.split}.zip"
    export(args.database_url, args.split, args.limit, output)


if __name__ == "__main__":
    main()
