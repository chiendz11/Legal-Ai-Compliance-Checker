"""Validated C11 generation with optional guarded local-Qwen personalization."""

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.modules.recommendations.generator import recommend
from legal_checker.modules.recommendations.personalization.contracts import (
    RecommendationPersonalizer,
)
from legal_checker.modules.recommendations.personalization.prompt import PROMPT_VERSION
from legal_checker.modules.risks.policy import Diagnostics
from legal_checker.shared.contracts.modules import RecommendationRequest
from legal_checker.shared.contracts.recommendation import Recommendation


def _apply_personalization(
    request: RecommendationRequest,
    base: list[Recommendation],
    personalizer: RecommendationPersonalizer,
    diagnostics: Diagnostics,
) -> list[Recommendation]:
    results: list[Recommendation] = []
    for rec in base:
        try:
            outcome = personalizer.personalize(request, rec)
        except Exception:
            snapshot = {
                **rec.template_snapshot_json,
                "personalization": {
                    "status": "FALLBACK",
                    "error_code": "C11_MODEL_UNAVAILABLE",
                },
            }
            if diagnostics is not None:
                diagnostics.append(
                    {
                        "module": "C11",
                        "code": "C11_PERSONALIZATION_FALLBACK",
                        "khuyen_nghi_ca_id": rec.khuyen_nghi_ca_id,
                        "model_version": "TEMPLATE_ENGINE_FALLBACK",
                        "status": "FALLBACK",
                        "error_code": "C11_MODEL_UNAVAILABLE",
                    }
                )
            results.append(
                rec.model_copy(
                    update={
                        "model_version": "TEMPLATE_ENGINE_FALLBACK",
                        "prompt_version": PROMPT_VERSION,
                        "template_snapshot_json": snapshot,
                    }
                )
            )
            continue

        if diagnostics is not None and outcome.diagnostics:
            diagnostics.extend(outcome.diagnostics)

        if outcome.status == "NOT_REQUESTED" and not outcome.applied:
            results.append(rec)
            continue

        personalization_meta = {
            "status": outcome.status,
            "model_version": outcome.model_version,
            "prompt_version": outcome.prompt_version,
            **({"error_code": outcome.error_code} if outcome.error_code else {}),
            **({"latency_ms": outcome.latency_ms} if outcome.latency_ms is not None else {}),
            "deterministic_text": rec.noi_dung,
        }
        snapshot = {**rec.template_snapshot_json, "personalization": personalization_meta}
        next_text = (
            outcome.personalized_text
            if outcome.applied and outcome.personalized_text
            else rec.noi_dung
        )
        results.append(
            rec.model_copy(
                update={
                    "noi_dung": next_text,
                    "model_version": outcome.model_version,
                    "prompt_version": outcome.prompt_version,
                    "template_snapshot_json": snapshot,
                }
            )
        )
    return results


def generate_recommendations(
    request: RecommendationRequest,
    knowledge: KnowledgeSnapshot,
    *,
    diagnostics: Diagnostics = None,
    personalizer: RecommendationPersonalizer | None = None,
) -> list[Recommendation]:
    request = RecommendationRequest.model_validate(request.model_dump())
    base = recommend(
        request,
        knowledge,
        request.payload.risks,
        request.payload.requirements,
        diagnostics=diagnostics,
    )
    if personalizer is None or not base:
        return base
    return _apply_personalization(request, base, personalizer, diagnostics)
