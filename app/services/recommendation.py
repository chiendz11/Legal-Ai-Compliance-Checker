"""Compatibility facade for the original recommendation call signature."""

from app.modules.recommendation.service import recommend as _recommend


def recommend(request, knowledge, risks):
    return _recommend(request, knowledge, risks, request.payload.requirements)
