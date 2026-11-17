"""Adapt OpenAI structured output to the Documents proposal interface.

The cache identity identifies an API model/configuration, never downloaded weights.
Credentials stay out of the public cache options and extraction provenance.
"""

from dataclasses import dataclass

from legal_checker.modules.documents.ollama_client import DocumentModelError
from legal_checker.shared.llm.config import OpenAISettings
from legal_checker.shared.llm.types import LlmClientError


@dataclass(frozen=True)
class DocumentApiOptions:
    model: str
    base_url: str
    provider: str
    api_mode: str
    max_output_tokens: int


class OpenAIDocumentClient:
    fact_method = "API_LLM_EXACT_QUOTE_V1"

    def __init__(self, settings: OpenAISettings, audit, *, http_client=None):
        self.settings, self.audit, self.http_client = settings, audit, http_client
        self.options = DocumentApiOptions(
            settings.model,
            settings.base_url,
            settings.provider,
            settings.api_mode,
            settings.max_output_tokens,
        )

    def digest(self) -> str:
        """Compatibility name: this is an API model reference, not a weight digest."""
        return "API_MODEL:" + self.settings.provider + ":" + self.settings.model

    def complete(self, context, payload, schema, instructions):
        from legal_checker.shared.llm.client import OpenAIResponsesClient

        try:
            with OpenAIResponsesClient(
                self.settings,
                self.audit,
                http_client=self.http_client,
                module="DOCUMENT_INTELLIGENCE",
            ) as client:
                result = client.complete(
                    context,
                    instructions=instructions,
                    payload=payload,
                    schema=schema,
                    prompt_version="DI_SEMANTIC_V1",
                    schema_version="DI_FACT_PROPOSALS_V1",
                )
        except LlmClientError as error:
            if getattr(error, "__notes__", None):
                raise
            raise DocumentModelError("DOCUMENT_LLM_" + error.code) from None
        # Internal completion envelope consumed by SemanticDocumentExtractor.
        return {
            "model": self.options.model,
            "actual_model": result.model_version,
            "provider": self.settings.provider,
            "done": True,
            "done_reason": "stop",
            "message": {"content": result.content},
        }
