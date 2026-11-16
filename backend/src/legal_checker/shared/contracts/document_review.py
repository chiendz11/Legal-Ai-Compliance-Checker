"""Backend-owned coverage proof; provider output cannot set verification gates."""

import json
from typing import Literal

from pydantic import Field, model_validator

from legal_checker.shared.contracts.common import Context, Model


class DocumentReviewCheck(Model):
    tieu_chi_id: str
    assessment: Literal["PRESENT", "ABSENT", "UNCERTAIN"]
    candidate_chunk_ids: list[str] = Field(default_factory=list)
    explanation: str = Field(min_length=1)


class DocumentReviewPart(Model):
    batch_id: str
    read_chunk_ids: list[str] = Field(min_length=1)
    checks: list[DocumentReviewCheck] = Field(min_length=1)


class DocumentReviewArtifact(Context):
    hop_dong_id: str
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    extraction_version: str
    criterion_ids: list[str] = Field(min_length=1)
    chunk_manifest: dict[str, str] = Field(min_length=1)
    parts: list[DocumentReviewPart] = Field(min_length=1)
    model_versions: list[str] = Field(min_length=1)
    prompt_version: str
    conclusion_text: dict[str, str]
    review_kind: Literal["MACHINE_FULL_TEXT"] = "MACHINE_FULL_TEXT"

    @model_validator(mode="after")
    def complete_matrix(self):
        if len(self.criterion_ids) != len(set(self.criterion_ids)):
            raise ValueError("Duplicate document-review criterion")
        seen = set()
        batch_ids = set()
        for part in self.parts:
            ids = part.read_chunk_ids
            if part.batch_id in batch_ids or len(ids) != len(set(ids)):
                raise ValueError("Duplicate document-review batch/chunk")
            batch_ids.add(part.batch_id)
            if not set(ids) <= self.chunk_manifest.keys():
                raise ValueError("Foreign review chunk")
            checks = [c.tieu_chi_id for c in part.checks]
            if len(checks) != len(set(checks)) or set(checks) != set(self.criterion_ids):
                raise ValueError("Incomplete criterion review matrix")
            for check in part.checks:
                if not set(check.candidate_chunk_ids) <= set(ids):
                    raise ValueError("Review evidence outside the read batch")
                if check.assessment == "PRESENT" and not check.candidate_chunk_ids:
                    raise ValueError("Presence needs attributable source material")
                if check.assessment == "ABSENT" and check.candidate_chunk_ids:
                    raise ValueError("Absence cannot carry a positive candidate")
            seen.update(ids)
        if seen != self.chunk_manifest.keys():
            raise ValueError("Full-document review omitted active chunks")
        if set(self.conclusion_text) != set(self.criterion_ids):
            raise ValueError("Missing literal document-review excerpt")
        for key, text in self.conclusion_text.items():
            value = json.loads(text)
            checks = [next(c for c in p.checks if c.tieu_chi_id == key) for p in self.parts]
            status = (
                "PRESENT"
                if any(c.assessment == "PRESENT" for c in checks)
                else ("UNCERTAIN" if any(c.assessment == "UNCERTAIN" for c in checks) else "ABSENT")
            )
            if (
                value.get("criterion_id") != key
                or value.get("source_sha256") != self.source_sha256
                or value.get("assessment") != status
                or value.get("active_chunks_reviewed") != len(self.chunk_manifest)
                or value.get("batch_count") != len(self.parts)
            ):
                raise ValueError("Document-review conclusion differs from the checked matrix")
        return self
