"""HTTP metrics per pod, plus aggregate LLM audit metrics from PostgreSQL.

No case/run/criterion IDs are metric labels. Worker calls live in DB, not a
process-local API counter. Database failure is observable and not rendered as zero.
"""

from time import perf_counter

from fastapi import Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)


def install_metrics(api):
    registry = CollectorRegistry()
    services = getattr(api.state, "services", None)
    settings = getattr(services, "settings", None)
    if settings and settings.database_url:
        registry.register(LlmAuditCollector(settings.database_url))
    requests = Counter(
        "legal_http_requests", "HTTP responses", ["method", "route", "status"], registry=registry
    )
    latency = Histogram(
        "legal_http_request_duration_seconds",
        "HTTP request latency",
        ["method", "route"],
        registry=registry,
    )

    @api.middleware("http")
    async def measure(request, call_next):
        started = perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            route = getattr(request.scope.get("route"), "path", "UNMATCHED")
            if route != "/metrics":
                requests.labels(request.method, route, str(status)).inc()
                latency.labels(request.method, route).observe(perf_counter() - started)

    @api.get("/metrics", include_in_schema=False)
    def metrics():
        return Response(generate_latest(registry), headers={"Content-Type": CONTENT_TYPE_LATEST})


class LlmAuditCollector:
    """Aggregate persisted calls across workers; cumulative DB counters, no input text.

    LLM metric values are shared DB totals: dashboards must use max across API pods,
    not sum the same series from each pod. Scrape failures have their own gauge.
    """

    def __init__(self, database_url):
        self.database_url = database_url

    def collect(self):
        from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily

        from legal_checker.core.postgres import connect_postgres

        healthy = GaugeMetricFamily("legal_llm_audit_scrape_success", "LLM audit DB readable")
        try:
            with connect_postgres(self.database_url) as connection:
                rows = connection.execute(
                    "SELECT CASE WHEN provider IN ('OPENAI','GROQ','GEMINI') "
                    "THEN provider ELSE 'OTHER' END AS provider, trang_thai, count(*) AS calls, "
                    "sum(latency_ms)/1000.0 AS duration, sum(input_tokens) AS inputs, "
                    "sum(output_tokens) AS outputs FROM runtime.nhat_ky_goi_llm "
                    "WHERE loai_du_lieu='LIVE_LLM_CALL' GROUP BY 1, 2"
                ).fetchall()
        except Exception:
            healthy.add_metric([], 0)
            yield healthy
            return
        healthy.add_metric([], 1)
        yield healthy
        calls = CounterMetricFamily(
            "legal_llm_calls", "Persisted LLM calls", labels=["provider", "status"]
        )
        duration = CounterMetricFamily(
            "legal_llm_duration_seconds", "Persisted LLM duration", labels=["provider", "status"]
        )
        tokens = CounterMetricFamily(
            "legal_llm_tokens",
            "Reported LLM tokens (unknown omitted)",
            labels=["provider", "status", "direction"],
        )
        for row in rows:
            # Provider values are a small registered set. Avoid arbitrary high-cardinality labels.
            provider = (
                row["provider"] if row["provider"] in {"OPENAI", "GROQ", "GEMINI"} else "OTHER"
            )
            labels = [provider, row["trang_thai"]]
            calls.add_metric(labels, row["calls"])
            duration.add_metric(labels, float(row["duration"] or 0))
            for key, direction in (("inputs", "input"), ("outputs", "output")):
                if row[key] is not None:
                    tokens.add_metric(labels + [direction], row[key])
        yield calls
        yield duration
        yield tokens
