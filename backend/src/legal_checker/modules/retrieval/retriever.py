"""Candidate data returned by a search backend, before legal reasoning."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchCandidate:
    doan_id: str
    score: float
    index_version: str
