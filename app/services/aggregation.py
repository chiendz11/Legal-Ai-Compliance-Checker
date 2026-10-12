"""Compatibility facade for the original aggregation call signature."""

from app.modules.rule_aggregation.service import aggregate as _aggregate


def aggregate(request, knowledge, criteria):
    return _aggregate(request, knowledge, criteria, request.payload.requirements)
