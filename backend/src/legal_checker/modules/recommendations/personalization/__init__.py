"""Optional local Qwen phrasing personalization for C11 recommendations."""

from legal_checker.modules.recommendations.personalization.client import (
    C11ModelError,
    OllamaRecommendationClient,
)
from legal_checker.modules.recommendations.personalization.config import (
    C11OllamaOptions,
    C11PersonalizationOptions,
)
from legal_checker.modules.recommendations.personalization.contracts import (
    PersonalizationResult,
    PersonalizationStatus,
    PersonalizedRecommendation,
    RecommendationPersonalizer,
)
from legal_checker.modules.recommendations.personalization.prompt import (
    INSTRUCTIONS,
    PROMPT_VERSION,
    SCHEMA_VERSION,
    build_personalization_payload,
)
from legal_checker.modules.recommendations.personalization.service import (
    RecommendationPersonalizationService,
)
from legal_checker.modules.recommendations.personalization.validator import (
    PersonalizationValidationError,
    validate_personalized_output,
)

__all__ = [
    "C11ModelError",
    "C11OllamaOptions",
    "C11PersonalizationOptions",
    "INSTRUCTIONS",
    "OllamaRecommendationClient",
    "PROMPT_VERSION",
    "PersonalizationResult",
    "PersonalizationStatus",
    "PersonalizationValidationError",
    "PersonalizedRecommendation",
    "RecommendationPersonalizationService",
    "RecommendationPersonalizer",
    "SCHEMA_VERSION",
    "build_personalization_payload",
    "validate_personalized_output",
]
