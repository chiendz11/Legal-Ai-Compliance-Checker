"""Assign new run identities without altering the frozen QA input."""

from legal_checker.shared.contracts.pipeline import PipelineRequest


def new_run(raw, run_id):
    request = PipelineRequest.model_validate(raw)
    request.run_id = run_id
    request.trace_id = request.ca_id + "/" + run_id
    for row in request.payload.retrieval:
        row.truy_xuat_id = request.ca_id + "/" + run_id + "/" + row.truy_xuat_id
        row.lan_chay_id = run_id
    for row in request.payload.citations:
        row.finding_id = request.ca_id + "/" + run_id + "/" + row.finding_id
        row.lan_chay_id = run_id
    return request
