# Audit and observability adapters

Implement LlmAuditSink from app.workflows.interfaces.llm_audit. X02 logs cover actual provider calls with input/output hashes, model/prompt/schema versions, trace IDs, latency, usage and errors. Runtime rule evaluation does not generate fake LLM calls. Provider output and document content require appropriate redaction/retention.

Skeleton only; no adapter/UI implementation is provided here.
