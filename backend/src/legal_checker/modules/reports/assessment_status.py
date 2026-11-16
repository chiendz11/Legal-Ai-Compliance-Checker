"""Present a stored disposition without relabelling its pinned legal C08 finding."""


def requirement_display_status(row):
    disposition = row.requirement_snapshot_json.get("assessment_disposition")
    if disposition in {"NOT_TRIGGERED", "OUTSIDE_REVIEW_SCOPE"}:
        return disposition
    return row.status


def criterion_display_status(row):
    if row.excluded and (row.exclusion_reason or "").startswith("REVIEW_SCOPE_EXCLUDED:"):
        return "OUTSIDE_REVIEW_SCOPE"
    return "EXCLUDED" if row.excluded else row.finding
