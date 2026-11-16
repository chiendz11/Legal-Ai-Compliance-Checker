"""Packaging must preserve the source denominator and never overwrite a release."""

import json

import pytest
from devtools.build_complete_gold import build_gold_release
from devtools.gold_answers import GoldError


def arguments(tmp_path):
    snapshot = tmp_path / "knowledge.json"
    snapshot.write_text(json.dumps({"tables": {}}))
    index = tmp_path / "index.json"
    index.write_text(json.dumps([{"case_id": "ONLY_ONE"}]))
    return dict(
        curated_root=tmp_path / "curated",
        sources_root=tmp_path / "sources",
        pdf_root=tmp_path / "pdfs",
        snapshot_path=snapshot,
        source_index_path=index,
        output=tmp_path / "output",
    )


def test_small_subset_cannot_be_published_as_complete_360_case_release(tmp_path):
    args = arguments(tmp_path)
    with pytest.raises(GoldError, match="denominator"):
        build_gold_release(**args)
    assert not args["output"].exists()


def test_existing_release_is_preserved(tmp_path):
    args = arguments(tmp_path)
    args["output"].mkdir()
    existing = args["output"] / "precious.json"
    existing.write_text("KEEP")
    with pytest.raises(GoldError, match="preserve previous"):
        build_gold_release(**args)
    assert existing.read_text() == "KEEP"
