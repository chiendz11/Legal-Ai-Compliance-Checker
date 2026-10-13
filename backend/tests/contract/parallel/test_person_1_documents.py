import hashlib
import io
import json
from xml.etree import ElementTree
from zipfile import ZipFile

import pytest
from devtools.parallel import SCENARIOS, json_text
from legal_checker.shared.contracts.document_intelligence import ProfileFields
from legal_checker.workflows.handoffs import validate_document
from pydantic import ValidationError


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_document_handoff_has_a_real_source_and_traceable_facts(
    parallel_packs, knowledge, scenario
):
    pack = parallel_packs[scenario]
    output = pack.reference_output(1, knowledge)
    content = pack.read_source(pack.handoffs.document_input.case.source)
    assert hashlib.sha256(content).hexdigest() == pack.handoffs.document_input.case.source.sha256
    with ZipFile(io.BytesIO(content)) as archive:
        document = ElementTree.fromstring(archive.read("word/document.xml"))
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = [node.text for node in document.findall(".//w:t", namespace)]
    assert "\n".join(paragraphs) == output.chunks[0].noi_dung
    assert output.contract_profile.profile.ben_ban_co_von_nuoc_ngoai is None
    assert all(not fact.human_verified for fact in output.contract_profile.facts)
    pack.validate_output(1, json.loads(json_text(output)), knowledge)


@pytest.mark.parametrize(
    "change", ["foreign_chunk", "quote", "fact", "page", "duplicate", "provenance"]
)
def test_document_owner_can_detect_bad_output_without_running_legal(parallel_packs, change):
    pack = parallel_packs["satisfied"]
    output = pack.handoffs.document_output.model_copy(deep=True)
    if change == "foreign_chunk":
        output.chunks[0].hop_dong_id = "FOREIGN"
    elif change == "quote":
        output.contract_profile.evidence[0].trich_dan = "Fabricated quote"
    elif change == "fact":
        output.contract_profile.facts[0].evidence_ids = ["UNKNOWN_EVIDENCE"]
    elif change == "page":
        output.citations[0].evidence[0].page_end = 99
    elif change == "duplicate":
        output.chunks.append(output.chunks[0])
    else:
        output.contract_profile.facts.clear()
    with pytest.raises(ValueError):
        validate_document(pack.handoffs.document_input.case, output)


def test_unknown_boolean_is_not_silently_converted_to_false():
    assert ProfileFields(ben_ban_la_ca_nhan=None).ben_ban_la_ca_nhan is None
    with pytest.raises(ValidationError):
        ProfileFields(ben_ban_la_ca_nhan="UNKNOWN")
