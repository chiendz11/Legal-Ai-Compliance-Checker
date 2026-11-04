"""JSON operational events: no request bodies, provider keys, prompts or SQL DSNs."""

import json
import logging
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record):
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("trace_id", "ca_id", "run_id", "stage", "status", "duration_seconds"):
            if hasattr(record, key):
                event[key] = getattr(record, key)
        # Avoid rendering exception text: URLs/headers may contain credentials.
        if record.exc_info and record.exc_info[0]:
            event["error_type"] = record.exc_info[0].__name__
        return json.dumps(event, ensure_ascii=False, default=str)


def configure_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger("legal_checker")
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    root.propagate = False
