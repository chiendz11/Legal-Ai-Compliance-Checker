# LLM provider adapters

Implement `CriterionProposalProvider` from `app/modules/compliance_reasoning/ports.py` here.
Return structured findings/explanations/quotes; trusted source/scope/absence/coverage gates belong to backend validation, not provider output.

No provider or API key is selected in this skeleton. Real requests must record X02 through `LlmAuditSink`; never emit synthetic provider-call logs for deterministic rules. Timeouts/schema errors must keep uncertainty visible.
