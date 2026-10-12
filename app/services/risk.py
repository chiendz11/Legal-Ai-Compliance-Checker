"""Compatibility facade for the original risk call signatures."""

from app.modules.risk.service import aggregate_risks as _aggregate_risks
from app.modules.risk.service import citation_risks as _citation_risks
from app.modules.risk.service import compliance_risks as compliance_risks


def citation_risks(request, knowledge):
    return _citation_risks(request, knowledge, request.payload.citations)


def aggregate_risks(request, knowledge, criteria):
    return _aggregate_risks(request, knowledge, criteria, request.payload.citations)
