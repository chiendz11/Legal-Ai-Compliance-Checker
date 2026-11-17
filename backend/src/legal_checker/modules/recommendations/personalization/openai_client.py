"""C11 API adapter; personalization still passes the existing semantic validator."""

from legal_checker.modules.recommendations.personalization.client import C11ModelError
from legal_checker.modules.recommendations.personalization.prompt import (
    PROMPT_VERSION,
    SCHEMA_VERSION,
)
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.llm.config import OpenAISettings
from legal_checker.shared.llm.types import LlmClientError


class OpenAIRecommendationClient:
    def __init__(self, settings: OpenAISettings, audit, *, http_client=None):
        self.settings, self.audit, self.http_client = settings, audit, http_client

    def complete(self, context, payload, schema, instructions):
        from legal_checker.shared.llm.client import OpenAIResponsesClient

        # C11 passes its RecommendationRequest (a Context subclass carrying the payload);
        # the shared client accepts only the bare run identity.
        context = Context(**{name: getattr(context, name) for name in Context.model_fields})
        try:
            with OpenAIResponsesClient(
                self.settings, self.audit, http_client=self.http_client, module="C11"
            ) as client:
                result = client.complete(
                    context,
                    instructions=instructions,
                    payload=payload,
                    schema=schema,
                    prompt_version=PROMPT_VERSION,
                    schema_version=SCHEMA_VERSION,
                )
        except LlmClientError as error:
            raise C11ModelError("C11_" + error.code) from None
        return result.content, result.model_version
